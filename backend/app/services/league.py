"""League-wide queries: leaders, improvers, similar players, team defense."""
import numpy as np
import pandas as pd

from ..nba import api
from ..nba.seasons import previous_season
from .percentiles import league_pool, qualified


def leaders(season: str, stat: str = "PTS", per_mode: str = "PerGame",
            measure: str = "Base", season_type: str = "Regular Season",
            limit: int = 15) -> list[dict]:
    df = qualified(league_pool(season, season_type, measure, per_mode))
    if df.empty or stat not in df.columns:
        return []
    top = df.nlargest(limit, stat)
    return [{
        "player_id": int(r["PLAYER_ID"]),
        "name": r["PLAYER_NAME"],
        "team": r.get("TEAM_ABBREVIATION"),
        "gp": int(r["GP"]),
        "min": float(r["MIN"]),
        "value": float(r[stat]),
        "stat": stat,
    } for _, r in top.iterrows()]


def improvers(season: str, metric: str = "TS_PCT",
              season_type: str = "Regular Season", limit: int = 15) -> list[dict]:
    prev = previous_season(season)
    cur = qualified(league_pool(season, season_type, "Advanced"))
    old = qualified(league_pool(prev, season_type, "Advanced"))
    if cur.empty or old.empty or metric not in cur.columns:
        return []
    merged = cur.merge(old[["PLAYER_ID", metric, "MIN", "GP"]],
                       on="PLAYER_ID", suffixes=("", "_prev"))
    merged["delta"] = merged[metric] - merged[f"{metric}_prev"]
    top = merged.nlargest(limit, "delta")
    return [{
        "player_id": int(r["PLAYER_ID"]),
        "name": r["PLAYER_NAME"],
        "team": r.get("TEAM_ABBREVIATION"),
        "current": float(r[metric]),
        "previous": float(r[f"{metric}_prev"]),
        "delta": round(float(r["delta"]), 4),
        "metric": metric,
        "seasons": [prev, season],
    } for _, r in top.iterrows()]


SIMILARITY_FEATURES_BASE = ["PTS", "REB", "AST", "STL", "BLK", "TOV", "FGA", "FG3A", "FTA"]
SIMILARITY_FEATURES_ADV = ["TS_PCT", "USG_PCT", "AST_PCT", "REB_PCT"]


def similar_players(player_id: int, season: str,
                    season_type: str = "Regular Season",
                    limit: int = 8) -> dict:
    base = qualified(league_pool(season, season_type, "Base", "Per100Possessions"))
    adv = qualified(league_pool(season, season_type, "Advanced"))
    if base.empty or adv.empty:
        return {"target": None, "matches": []}

    feats = base[["PLAYER_ID", "PLAYER_NAME", "TEAM_ABBREVIATION"] +
                 [c for c in SIMILARITY_FEATURES_BASE if c in base.columns]]
    feats = feats.merge(
        adv[["PLAYER_ID"] + [c for c in SIMILARITY_FEATURES_ADV if c in adv.columns]],
        on="PLAYER_ID")

    cols = [c for c in SIMILARITY_FEATURES_BASE + SIMILARITY_FEATURES_ADV
            if c in feats.columns]
    z = (feats[cols] - feats[cols].mean()) / feats[cols].std().replace(0, 1)

    target_rows = feats.index[feats["PLAYER_ID"] == player_id]
    if len(target_rows) == 0:
        return {"target": None, "matches": []}
    t = target_rows[0]
    dist = np.sqrt(((z - z.loc[t]) ** 2).sum(axis=1))
    feats = feats.assign(distance=dist).sort_values("distance")

    matches = feats[feats["PLAYER_ID"] != player_id].head(limit)
    return {
        "target": {"player_id": player_id,
                   "profile": {c: float(feats.loc[t, c]) for c in cols}},
        "features": cols,
        "matches": [{
            "player_id": int(r["PLAYER_ID"]),
            "name": r["PLAYER_NAME"],
            "team": r.get("TEAM_ABBREVIATION"),
            "distance": round(float(r["distance"]), 2),
            "profile": {c: float(r[c]) for c in cols},
        } for _, r in matches.iterrows()],
        "method": ("Euclidean distance over z-scored per-100-possession box "
                   "stats plus usage/efficiency, qualified players only."),
    }


def low_minutes_efficient(season: str, season_type: str = "Regular Season",
                          max_mpg: float = 24, limit: int = 15) -> list[dict]:
    adv = league_pool(season, season_type, "Advanced")
    base = league_pool(season, season_type, "Base")
    if adv.empty or base.empty:
        return []
    adv = adv[(adv["GP"] >= 10) & (adv["MIN"] < max_mpg) & (adv["MIN"] >= 10)]
    # the Advanced pool also carries FGA/PTS columns, so suffix them away
    merged = adv.merge(base[["PLAYER_ID", "PTS", "FGA"]], on="PLAYER_ID",
                       suffixes=("_adv", ""))
    merged = merged[merged["FGA"] >= 4]  # real shot volume only
    top = merged.nlargest(limit, "TS_PCT")
    return [{
        "player_id": int(r["PLAYER_ID"]),
        "name": r["PLAYER_NAME"],
        "team": r.get("TEAM_ABBREVIATION"),
        "mpg": float(r["MIN"]),
        "ppg": float(r["PTS"]),
        "ts_pct": float(r["TS_PCT"]),
        "usg_pct": float(r["USG_PCT"]),
        "gp": int(r["GP"]),
    } for _, r in top.iterrows()]


def team_defense(season: str, season_type: str = "Regular Season") -> list[dict]:
    rows = api.league_team_stats(season, "Advanced", season_type)
    df = pd.DataFrame(rows)
    if df.empty:
        return []
    df = df.sort_values("DEF_RATING")
    return [{
        "team_id": int(r["TEAM_ID"]),
        "team": r["TEAM_NAME"],
        "def_rating": float(r["DEF_RATING"]),
        "net_rating": float(r["NET_RATING"]),
        "rank": i + 1,
    } for i, (_, r) in enumerate(df.iterrows())]
