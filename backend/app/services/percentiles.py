"""Position-based percentile rankings from league-wide stats.

Pool: players at the same position group (G/F/C) with >= 10 GP and >= 15 MPG.
Lower-is-better stats (turnovers, fouls) are inverted so 90th percentile always
means "good".
"""
import pandas as pd

from ..nba import api

LOWER_IS_BETTER = {"TOV", "PF", "TM_TOV_PCT", "DEF_RATING"}

MIN_GP = 10
MIN_MPG = 15


def _position_group(position: str | None) -> str:
    if not position:
        return "F"
    return position.strip()[0].upper()  # "G-F" -> "G"


def position_map(season: str) -> dict[int, str]:
    """player_id -> position group. Past-season player indexes are sparse,
    so backfill from the current season's index."""
    from ..nba.seasons import current_season

    mapping: dict[int, str] = {}
    if season != current_season():
        for r in api.player_index(current_season()):
            mapping[r["PERSON_ID"]] = _position_group(r.get("POSITION"))
    for r in api.player_index(season):
        if r.get("POSITION"):
            mapping[r["PERSON_ID"]] = _position_group(r.get("POSITION"))
    return mapping


def league_pool(season: str, season_type: str = "Regular Season",
                measure: str = "Base", per_mode: str = "PerGame") -> pd.DataFrame:
    rows = api.league_player_stats(season, per_mode=per_mode, measure=measure,
                                   season_type=season_type)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    positions = position_map(season)
    df["POS_GROUP"] = df["PLAYER_ID"].map(positions).fillna("F")
    return df


def qualified(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "GP" not in df.columns:
        return df
    out = df[df["GP"] >= MIN_GP]
    if "MIN" in df.columns:
        out = out[out["MIN"] >= MIN_MPG]
    return out


def percentile_of(pool: pd.Series, value: float, invert: bool = False) -> int:
    pool = pool.dropna()
    if len(pool) < 5:
        return 50
    pct = (pool < value).mean() * 100
    if invert:
        pct = 100 - pct
    return int(round(pct))


def player_percentiles(player_id: int, season: str,
                       season_type: str = "Regular Season",
                       stats: list[str] | None = None) -> dict:
    """Percentiles for a player's per-game stats vs same-position peers."""
    base = qualified(league_pool(season, season_type, "Base"))
    adv = qualified(league_pool(season, season_type, "Advanced"))

    result: dict[str, dict] = {}
    for df in (base, adv):
        if df.empty:
            continue
        me = df[df["PLAYER_ID"] == player_id]
        if me.empty:
            continue
        me = me.iloc[0]
        peers = df[df["POS_GROUP"] == me["POS_GROUP"]]
        cols = stats or [c for c in df.columns
                         if df[c].dtype != object and c not in
                         ("PLAYER_ID", "TEAM_ID", "AGE", "GP", "W", "L")]
        for col in cols:
            if col in result or col not in df.columns:
                continue
            val = me[col]
            if pd.isna(val):
                continue
            result[col] = {
                "value": float(val),
                "percentile": percentile_of(peers[col], val,
                                            invert=col in LOWER_IS_BETTER),
                "position_group": me["POS_GROUP"],
                "pool_size": int(len(peers)),
            }
    return result
