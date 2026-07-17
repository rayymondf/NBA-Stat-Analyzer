"""Efficiency dashboard: advanced metrics + percentile context."""
from ..nba import api
from . import frames, percentiles


def efficiency(player_id: int, season: str,
               season_type: str = "Regular Season") -> dict:
    adv_rows = api.league_player_stats(season, per_mode="PerGame",
                                       measure="Advanced",
                                       season_type=season_type)
    me = next((r for r in adv_rows if r["PLAYER_ID"] == player_id), None)

    df = frames.merged_logs(player_id, season, season_type)
    agg = frames.aggregate(df)
    sh = agg.get("shooting", {})

    metrics = {
        "ts_pct": (me or {}).get("TS_PCT", sh.get("TS_PCT")),
        "efg_pct": (me or {}).get("EFG_PCT", sh.get("EFG_PCT")),
        "usg_pct": (me or {}).get("USG_PCT", sh.get("USG_EST")),
        "ast_to": (me or {}).get("AST_TO", sh.get("AST_TO")),
        "ast_pct": (me or {}).get("AST_PCT"),
        "tov_pct": (me or {}).get("TM_TOV_PCT", sh.get("TOV_PCT")),
        "ft_rate": sh.get("FT_RATE"),
        "pts_per_poss": sh.get("PTS_PER_POSS"),
        "off_rating": (me or {}).get("OFF_RATING", sh.get("OFF_RATING")),
        "def_rating": (me or {}).get("DEF_RATING", sh.get("DEF_RATING")),
        "net_rating": (me or {}).get("NET_RATING", sh.get("NET_RATING")),
        "pie": (me or {}).get("PIE"),
        "pace": (me or {}).get("PACE", sh.get("PACE")),
    }

    try:
        pcts = percentiles.player_percentiles(
            player_id, season, season_type,
            stats=["TS_PCT", "EFG_PCT", "USG_PCT", "AST_TO", "AST_PCT",
                   "TM_TOV_PCT", "OFF_RATING", "DEF_RATING", "NET_RATING",
                   "PIE"])
    except RuntimeError:
        pcts = {}

    return {
        "season": season,
        "season_type": season_type,
        "games": agg.get("games", 0),
        "metrics": metrics,
        "percentiles": pcts,
    }
