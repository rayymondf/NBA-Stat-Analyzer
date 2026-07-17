"""Foul profile. Season-wide counts come from game logs; foul *types*
(offensive / shooting / technical) are parsed from play-by-play for the most
recent games only, since each game costs one API call (cached permanently)."""
import pandas as pd

from ..nba import api
from . import frames

def _classify(sub_type: str, desc: str) -> str:
    s = (sub_type or "").lower()
    d = (desc or "").lower()
    if "technical" in s or "technical" in d:
        return "technical"
    if "offensive" in s or "charge" in s:
        return "offensive"
    if "shooting" in s:
        return "shooting"
    if "loose ball" in s:
        return "loose_ball"
    if "personal" in s:
        return "personal"
    return "other"


def foul_types_from_pbp(player_id: int, player_name: str,
                        game_ids: list[str]) -> dict:
    counts = {"personal": 0, "shooting": 0, "offensive": 0, "technical": 0,
              "loose_ball": 0, "other": 0}
    ft_from_fouls = 0
    analyzed = 0
    for gid in game_ids:
        try:
            actions = api.play_by_play(gid)
        except RuntimeError:
            continue
        analyzed += 1
        for a in actions:
            if a.get("actionType") != "Foul":
                continue
            if a.get("personId") != player_id:
                continue
            kind = _classify(a.get("subType"), a.get("description"))
            counts[kind] += 1
            if kind == "shooting":
                # V3 descriptions omit the FT count; ~2.1 FTs per shooting foul
                ft_from_fouls += 2
    return {"counts": counts,
            "opponent_fta_from_shooting_fouls_estimate": ft_from_fouls,
            "games_analyzed": analyzed}


def fouls(player_id: int, season: str, season_type: str = "Regular Season",
          pbp_games: int = 10) -> dict:
    df = frames.merged_logs(player_id, season, season_type)
    if df.empty:
        return {"games": 0, "season": season, "season_type": season_type}

    gp = len(df)
    total_pf = float(df["PF"].sum())
    total_min = float(df["MIN"].sum())

    foul_trouble = df[df["PF"] >= 5]
    normal = df[df["PF"] < 5]

    recent_ids = list(df.tail(pbp_games)["GAME_ID"])
    name = str(df["PLAYER_NAME"].iloc[0]) if "PLAYER_NAME" in df else ""
    types = foul_types_from_pbp(player_id, name, recent_ids)

    per_game_series = [{
        "date": r["GAME_DATE"].strftime("%Y-%m-%d"),
        "pf": int(r["PF"]),
        "min": round(float(r["MIN"]), 1),
    } for _, r in df.iterrows()]

    return {
        "season": season,
        "season_type": season_type,
        "games": gp,
        "pf_per_game": round(total_pf / gp, 2),
        "pf_per_36": round(total_pf / total_min * 36, 2) if total_min else None,
        "pf_total": int(total_pf),
        "fouls_drawn_per_game": round(float(df["PFD"].mean()), 2) if "PFD" in df else None,
        "games_5_fouls": int((df["PF"] == 5).sum()),
        "games_6_fouls": int((df["PF"] >= 6).sum()),
        "foul_trouble_rate": round(len(foul_trouble) / gp, 3),
        "avg_min_foul_trouble": round(float(foul_trouble["MIN"].mean()), 1) if len(foul_trouble) else None,
        "avg_min_normal": round(float(normal["MIN"].mean()), 1) if len(normal) else None,
        "series": per_game_series,
        "foul_types_recent": types,
        "note": (f"Foul types are parsed from play-by-play for the last "
                 f"{types['games_analyzed']} games only."),
    }
