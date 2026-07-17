"""Game-log DataFrame construction, filtering, and per-mode aggregation.

This is the app's core stats engine: every player stat shown in the UI (and
every number the AI cites) is computed here from official game logs, so the
same filters produce the same numbers everywhere.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..nba import api

ADV_COLS = [
    "GAME_ID", "OFF_RATING", "DEF_RATING", "NET_RATING", "TS_PCT", "EFG_PCT",
    "USG_PCT", "PACE", "POSS", "AST_PCT", "AST_TO", "AST_RATIO", "TM_TOV_PCT",
    "REB_PCT", "OREB_PCT", "DREB_PCT", "PIE",
]

SUM_COLS = [
    "MIN", "FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA", "OREB", "DREB", "REB",
    "AST", "TOV", "STL", "BLK", "BLKA", "PF", "PFD", "PTS", "PLUS_MINUS",
    "POSS", "DD2", "TD3",
]


@dataclass
class LogFilters:
    season: str
    season_type: str = "Regular Season"
    location: str | None = None      # "home" | "away"
    outcome: str | None = None       # "W" | "L"
    starter: bool | None = None      # True = starts, False = bench
    last_n: int | None = None        # most recent N games
    opponent: str | None = None      # team abbreviation, e.g. "BOS"
    date_from: str | None = None     # YYYY-MM-DD
    date_to: str | None = None


def merged_logs(player_id: int, season: str,
                season_type: str = "Regular Season") -> pd.DataFrame:
    """Base + Advanced game logs merged, sorted by date, with derived columns."""
    base = api.player_game_logs(player_id, season, season_type)
    if not base:
        return pd.DataFrame()
    df = pd.DataFrame(base)

    adv = api.player_game_logs(player_id, season, season_type, measure="Advanced")
    if adv:
        adv_df = pd.DataFrame(adv)
        keep = [c for c in ADV_COLS if c in adv_df.columns]
        df = df.merge(adv_df[keep], on="GAME_ID", how="left", suffixes=("", "_adv"))

    df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])
    df = df.sort_values("GAME_DATE").reset_index(drop=True)
    df["HOME"] = df["MATCHUP"].str.contains("vs.", regex=False)
    df["OPP"] = df["MATCHUP"].str.extract(r"(?:vs\.|@)\s*(\w+)")

    try:
        started = api.starter_game_ids(player_id, season, season_type)
        df["STARTED"] = df["GAME_ID"].isin(started)
    except RuntimeError:
        df["STARTED"] = None
    return df


def apply_filters(df: pd.DataFrame, f: LogFilters) -> pd.DataFrame:
    if df.empty:
        return df
    out = df
    if f.location == "home":
        out = out[out["HOME"]]
    elif f.location == "away":
        out = out[~out["HOME"]]
    if f.outcome in ("W", "L"):
        out = out[out["WL"] == f.outcome]
    if f.starter is True and out["STARTED"].notna().all():
        out = out[out["STARTED"] == True]  # noqa: E712
    elif f.starter is False and out["STARTED"].notna().all():
        out = out[out["STARTED"] == False]  # noqa: E712
    if f.opponent:
        out = out[out["OPP"] == f.opponent.upper()]
    if f.date_from:
        out = out[out["GAME_DATE"] >= pd.Timestamp(f.date_from)]
    if f.date_to:
        out = out[out["GAME_DATE"] <= pd.Timestamp(f.date_to)]
    if f.last_n:
        out = out.tail(f.last_n)
    return out


def _safe_div(a: float, b: float) -> float | None:
    return round(a / b, 4) if b else None


def _rates(sums: dict, denominator: float, scale: float) -> dict:
    """Counting stats scaled to a denominator (games, minutes, possessions)."""
    keys = ["PTS", "REB", "OREB", "DREB", "AST", "STL", "BLK", "TOV", "PF",
            "PFD", "FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA", "MIN",
            "PLUS_MINUS"]
    if not denominator:
        return {}
    return {k: round(sums.get(k, 0) * scale / denominator, 2) for k in keys}


def aggregate(df: pd.DataFrame) -> dict:
    """Totals + shooting percentages + per-game/36/100/75 rates for a set of games."""
    if df.empty:
        return {"games": 0}

    sums = {c: float(df[c].sum()) for c in SUM_COLS if c in df.columns}
    games = len(df)
    minutes = sums.get("MIN", 0.0)
    poss = sums.get("POSS", 0.0)
    # Fallback possession estimate if the Advanced log is missing
    if not poss:
        poss = sums.get("FGA", 0) + 0.44 * sums.get("FTA", 0) + sums.get("TOV", 0)

    fga, fgm = sums.get("FGA", 0), sums.get("FGM", 0)
    fg3a, fg3m = sums.get("FG3A", 0), sums.get("FG3M", 0)
    fta, ftm = sums.get("FTA", 0), sums.get("FTM", 0)
    pts, tov, ast = sums.get("PTS", 0), sums.get("TOV", 0), sums.get("AST", 0)
    tsa = fga + 0.44 * fta

    shooting = {
        "FG_PCT": _safe_div(fgm, fga),
        "FG3_PCT": _safe_div(fg3m, fg3a),
        "FT_PCT": _safe_div(ftm, fta),
        "TS_PCT": _safe_div(pts, 2 * tsa),
        "EFG_PCT": _safe_div(fgm + 0.5 * fg3m, fga),
        "FG2_PCT": _safe_div(fgm - fg3m, fga - fg3a),
        "FT_RATE": _safe_div(fta, fga),
        "FG3A_RATE": _safe_div(fg3a, fga),
        "PTS_PER_SHOT": _safe_div(pts - ftm, fga),
        "AST_TO": _safe_div(ast, tov),
        "USG_EST": _safe_div(fga + 0.44 * fta + tov, poss),
        # points per possession *used* (scoring attempts + turnovers)
        "PTS_PER_POSS": _safe_div(pts, fga + 0.44 * fta + tov),
        "TOV_PCT": _safe_div(tov, fga + 0.44 * fta + tov),
    }

    result = {
        "games": games,
        "wins": int((df["WL"] == "W").sum()) if "WL" in df else None,
        "losses": int((df["WL"] == "L").sum()) if "WL" in df else None,
        "starts": int(df["STARTED"].sum()) if df.get("STARTED") is not None and df["STARTED"].notna().all() else None,
        "totals": {k: round(v, 1) for k, v in sums.items()},
        "per_game": _rates(sums, games, 1),
        "per_36": _rates(sums, minutes, 36),
        "per_100": _rates(sums, poss, 100),
        "per_75": _rates(sums, poss, 75),
        "shooting": shooting,
        "possessions": round(poss, 1),
    }

    # Possession-weighted ratings from the advanced logs
    if "OFF_RATING" in df.columns and poss:
        w = df["POSS"].fillna(0)
        if w.sum() > 0:
            for col in ("OFF_RATING", "DEF_RATING", "NET_RATING", "PACE"):
                if col in df.columns:
                    vals = df[col].fillna(0)
                    result["shooting"][col] = round(float(np.average(vals, weights=w)), 1)
    return result


def game_rows(df: pd.DataFrame) -> list[dict]:
    """Rows for the game-log table (one dict per game, UI-friendly)."""
    if df.empty:
        return []
    rows = []
    for _, r in df.iterrows():
        fga, fta = r.get("FGA", 0), r.get("FTA", 0)
        tsa = fga + 0.44 * fta
        rows.append({
            "game_id": r["GAME_ID"],
            "date": r["GAME_DATE"].strftime("%Y-%m-%d"),
            "matchup": r["MATCHUP"],
            "opponent": r["OPP"],
            "home": bool(r["HOME"]),
            "wl": r.get("WL"),
            "started": None if pd.isna(r.get("STARTED")) else bool(r.get("STARTED")),
            "min": round(float(r.get("MIN", 0)), 1),
            "pts": int(r.get("PTS", 0)),
            "reb": int(r.get("REB", 0)),
            "ast": int(r.get("AST", 0)),
            "stl": int(r.get("STL", 0)),
            "blk": int(r.get("BLK", 0)),
            "tov": int(r.get("TOV", 0)),
            "pf": int(r.get("PF", 0)),
            "fgm": int(r.get("FGM", 0)),
            "fga": int(fga),
            "fg3m": int(r.get("FG3M", 0)),
            "fg3a": int(r.get("FG3A", 0)),
            "ftm": int(r.get("FTM", 0)),
            "fta": int(fta),
            "plus_minus": None if pd.isna(r.get("PLUS_MINUS")) else int(r.get("PLUS_MINUS")),
            "ts_pct": round(float(r.get("PTS", 0)) / (2 * tsa), 3) if tsa else None,
            "usg_pct": None if pd.isna(r.get("USG_PCT")) else float(r.get("USG_PCT")),
        })
    return rows
