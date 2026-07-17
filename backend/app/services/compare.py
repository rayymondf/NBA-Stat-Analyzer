"""Two-player comparison bundles."""
from . import efficiency, frames, percentiles, players, shooting


def _player_block(player_id: int, season: str, season_type: str) -> dict:
    info = players.bio(player_id)
    df = frames.merged_logs(player_id, season, season_type)
    agg = frames.aggregate(df)
    try:
        pcts = percentiles.player_percentiles(
            player_id, season, season_type,
            stats=["PTS", "REB", "AST", "STL", "BLK", "TOV", "PF", "MIN",
                   "TS_PCT", "EFG_PCT", "USG_PCT", "AST_TO", "OFF_RATING",
                   "DEF_RATING", "NET_RATING"])
    except RuntimeError:
        pcts = {}
    shots = shooting.shot_profile(player_id, season, season_type)
    eff = efficiency.efficiency(player_id, season, season_type)
    return {
        "info": info,
        "stats": agg,
        "percentiles": pcts,
        "zones": shots.get("zones", []),
        "shot_points": shots.get("points", []),
        "efficiency": eff.get("metrics", {}),
    }


def compare(player_a: int, player_b: int, season: str,
            season_type: str = "Regular Season") -> dict:
    return {
        "season": season,
        "season_type": season_type,
        "a": _player_block(player_a, season, season_type),
        "b": _player_block(player_b, season, season_type),
    }
