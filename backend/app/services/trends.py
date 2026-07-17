"""Rolling trends, recent-form analysis, and career development."""
import numpy as np
import pandas as pd

from ..nba import api
from . import frames


def _rolling_ts(df: pd.DataFrame, window: int) -> pd.Series:
    pts = df["PTS"].rolling(window).sum()
    tsa = (df["FGA"] + 0.44 * df["FTA"]).rolling(window).sum()
    return (pts / (2 * tsa)).round(3)


def season_trends(player_id: int, season: str,
                  season_type: str = "Regular Season",
                  window: int = 10) -> dict:
    df = frames.merged_logs(player_id, season, season_type)
    if df.empty or len(df) < 3:
        return {"games": int(len(df)), "series": [], "season": season}

    w = min(window, max(3, len(df) // 3))
    roll = pd.DataFrame({
        "date": df["GAME_DATE"].dt.strftime("%Y-%m-%d"),
        "game_id": df["GAME_ID"],
        "pts": df["PTS"],
        "min": df["MIN"].round(1),
        "pts_roll": df["PTS"].rolling(w).mean().round(1),
        "ts_roll": _rolling_ts(df, w),
        "min_roll": df["MIN"].rolling(w).mean().round(1),
        "fga_roll": df["FGA"].rolling(w).mean().round(1),
        "fg3a_rate_roll": (df["FG3A"].rolling(w).sum() /
                           df["FGA"].rolling(w).sum()).round(3),
    })
    if "USG_PCT" in df.columns:
        roll["usg_roll"] = df["USG_PCT"].rolling(w).mean().round(3)

    series = roll.replace({np.nan: None}).to_dict("records")

    # Recent form vs season baseline (last 10 games)
    last10 = df.tail(10)
    season_pts_mean = float(df["PTS"].mean())
    season_pts_std = float(df["PTS"].std()) or 1.0
    recent_pts = float(last10["PTS"].mean())
    tsa_all = float((df["FGA"] + 0.44 * df["FTA"]).sum())
    tsa_10 = float((last10["FGA"] + 0.44 * last10["FTA"]).sum())
    form = {
        "last_10_pts": round(recent_pts, 1),
        "season_pts": round(season_pts_mean, 1),
        "pts_z_score": round((recent_pts - season_pts_mean) /
                             (season_pts_std / np.sqrt(min(10, len(last10)))), 2),
        "last_10_ts": round(float(last10["PTS"].sum()) / (2 * tsa_10), 3) if tsa_10 else None,
        "season_ts": round(float(df["PTS"].sum()) / (2 * tsa_all), 3) if tsa_all else None,
    }

    return {
        "season": season,
        "season_type": season_type,
        "games": int(len(df)),
        "window": w,
        "series": series,
        "recent_form": form,
    }


def career(player_id: int) -> dict:
    data = api.career_stats(player_id, per_mode="PerGame")

    def clean(rows: list[dict]) -> list[dict]:
        return [{
            "season": r.get("SEASON_ID"),
            "team": r.get("TEAM_ABBREVIATION"),
            "age": r.get("PLAYER_AGE"),
            "gp": r.get("GP"),
            "gs": r.get("GS"),
            "min": r.get("MIN"),
            "pts": r.get("PTS"),
            "reb": r.get("REB"),
            "ast": r.get("AST"),
            "stl": r.get("STL"),
            "blk": r.get("BLK"),
            "tov": r.get("TOV"),
            "pf": r.get("PF"),
            "fg_pct": r.get("FG_PCT"),
            "fg3_pct": r.get("FG3_PCT"),
            "ft_pct": r.get("FT_PCT"),
            "fga": r.get("FGA"),
            "fg3a": r.get("FG3A"),
            "fta": r.get("FTA"),
        } for r in rows if r.get("TEAM_ABBREVIATION") != "TOT" or len(rows) == 1]

    reg = clean(data.get("SeasonTotalsRegularSeason", []))
    for r in reg:
        fga, fta, pts = r.get("fga") or 0, r.get("fta") or 0, r.get("pts") or 0
        tsa = fga + 0.44 * fta
        r["ts_pct"] = round(pts / (2 * tsa), 3) if tsa else None

    return {
        "regular_season": reg,
        "playoffs": clean(data.get("SeasonTotalsPostSeason", [])),
    }
