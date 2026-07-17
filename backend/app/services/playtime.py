"""Playing time, availability, foul-trouble impact, clutch/Q4 minutes."""
import pandas as pd

from ..nba import api
from . import frames

MINUTE_BUCKETS = [(0, 20, "Under 20 min"), (20, 28, "20-28 min"),
                  (28, 34, "28-34 min"), (34, 60, "34+ min")]


def _team_games_played(team_abbr: str, season: str, season_type: str) -> int | None:
    try:
        rows = api.find_team_games(season, season_type)
    except RuntimeError:
        return None
    return sum(1 for r in rows if r.get("TEAM_ABBREVIATION") == team_abbr) or None


def playtime(player_id: int, season: str,
             season_type: str = "Regular Season") -> dict:
    df = frames.merged_logs(player_id, season, season_type)
    if df.empty:
        return {"games": 0, "season": season, "season_type": season_type}

    gp = len(df)
    team_abbr = df["TEAM_ABBREVIATION"].iloc[-1] if "TEAM_ABBREVIATION" in df else None
    team_gp = _team_games_played(team_abbr, season, season_type) if team_abbr else None

    starts = int(df["STARTED"].sum()) if df["STARTED"].notna().all() else None

    timeline = [{
        "date": r["GAME_DATE"].strftime("%Y-%m-%d"),
        "game_id": r["GAME_ID"],
        "matchup": r["MATCHUP"],
        "min": round(float(r["MIN"]), 1),
        "pts": int(r["PTS"]),
        "pf": int(r["PF"]),
        "wl": r["WL"],
    } for _, r in df.iterrows()]

    by_minutes = []
    for lo, hi, label in MINUTE_BUCKETS:
        g = df[(df["MIN"] >= lo) & (df["MIN"] < hi)]
        if len(g) == 0:
            continue
        by_minutes.append({
            "bucket": label,
            "games": int(len(g)),
            "pts": round(float(g["PTS"].mean()), 1),
            "reb": round(float(g["REB"].mean()), 1),
            "ast": round(float(g["AST"].mean()), 1),
            "ts_pct": round(float(g["PTS"].sum()) /
                            (2 * (g["FGA"].sum() + 0.44 * g["FTA"].sum())), 3)
            if (g["FGA"].sum() + g["FTA"].sum()) > 0 else None,
        })

    foul_trouble = df[df["PF"] >= 5]
    normal = df[df["PF"] < 5]
    foul_impact = {
        "games_5plus_fouls": int(len(foul_trouble)),
        "avg_min_foul_trouble": round(float(foul_trouble["MIN"].mean()), 1) if len(foul_trouble) else None,
        "avg_min_normal": round(float(normal["MIN"].mean()), 1) if len(normal) else None,
    }

    # Fourth-quarter minutes/production (ByPeriod dashboard, totals)
    q4 = None
    try:
        gs = api.game_splits(player_id, season, season_type)
        for row in gs.get("ByPeriodPlayerDashboard", []):
            if row.get("GROUP_VALUE") == 4:
                q4 = {
                    "min_total": row.get("MIN"),
                    "min_per_game": round(row["MIN"] / gp, 1) if row.get("MIN") else None,
                    "pts_total": row.get("PTS"),
                    "fg_pct": row.get("FG_PCT"),
                }
    except RuntimeError:
        pass

    # Clutch: last 5 minutes, margin within 5
    clutch = None
    try:
        cl = api.clutch_dashboard(player_id, season, season_type)
        rows = cl.get("Last5Min5PointPlayerDashboard", [])
        if rows:
            r = rows[0]  # totals across clutch situations
            games = r.get("GP") or 0
            clutch = {
                "games": games,
                "min_total": round(r["MIN"], 1) if r.get("MIN") else None,
                "min_per_game": round(r["MIN"] / games, 1) if games and r.get("MIN") else None,
                "pts_total": r.get("PTS"),
                "pts_per_game": round(r["PTS"] / games, 1) if games and r.get("PTS") is not None else None,
                "fg_pct": r.get("FG_PCT"),
                "plus_minus": r.get("PLUS_MINUS"),
                "record": f"{r.get('W', 0)}-{r.get('L', 0)}",
            }
    except RuntimeError:
        pass

    return {
        "season": season,
        "season_type": season_type,
        "games": gp,
        "team_games": team_gp,
        "games_missed": (team_gp - gp) if team_gp else None,
        "starts": starts,
        "bench_games": (gp - starts) if starts is not None else None,
        "min_per_game": round(float(df["MIN"].mean()), 1),
        "min_total": round(float(df["MIN"].sum()), 0),
        "timeline": timeline,
        "by_minutes": by_minutes,
        "foul_impact": foul_impact,
        "q4": q4,
        "clutch": clutch,
    }
