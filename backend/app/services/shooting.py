"""Shot chart data, zone/distance breakdowns, and league-average comparison."""
import pandas as pd

from ..nba import api

ZONE_ORDER = [
    "Restricted Area", "In The Paint (Non-RA)", "Mid-Range",
    "Left Corner 3", "Right Corner 3", "Above the Break 3", "Backcourt",
]

DISTANCE_BINS = [(0, 4, "0-4 ft"), (4, 10, "4-10 ft"), (10, 16, "10-16 ft"),
                 (16, 24, "16 ft - 3PT"), (24, 99, "3PT and beyond")]


def shot_profile(player_id: int, season: str,
                 season_type: str = "Regular Season",
                 opponent_team_id: int = 0,
                 game_id: str | None = None) -> dict:
    data = api.shot_chart(player_id, season, season_type,
                          opponent_team_id=opponent_team_id, game_id=game_id)
    shots = pd.DataFrame(data.get("Shot_Chart_Detail", []))
    league = pd.DataFrame(data.get("LeagueAverages", []))

    if shots.empty:
        return {"points": [], "zones": [], "by_distance": [], "totals": {},
                "season": season, "season_type": season_type}

    points = [{
        "x": int(r["LOC_X"]),
        "y": int(r["LOC_Y"]),
        "made": bool(r["SHOT_MADE_FLAG"]),
        "value": 3 if "3PT" in str(r["SHOT_TYPE"]) else 2,
        "dist": int(r["SHOT_DISTANCE"]),
        "game_id": r["GAME_ID"],
        "date": str(r["GAME_DATE"]),
        "period": int(r["PERIOD"]),
        "action": r["ACTION_TYPE"],
        "zone": r["SHOT_ZONE_BASIC"],
        "vs": f"{r['HTM']} vs {r['VTM']}",
    } for _, r in shots.iterrows()]

    # Zone aggregates vs league average (league rows are per fine-grained zone,
    # so aggregate both to SHOT_ZONE_BASIC)
    zones = []
    grouped = shots.groupby("SHOT_ZONE_BASIC")
    lg_grouped = league.groupby("SHOT_ZONE_BASIC")[["FGA", "FGM"]].sum() if not league.empty else None
    for zone in ZONE_ORDER:
        if zone not in grouped.groups:
            continue
        g = grouped.get_group(zone)
        fga, fgm = len(g), int(g["SHOT_MADE_FLAG"].sum())
        lg_pct = None
        if lg_grouped is not None and zone in lg_grouped.index:
            lg = lg_grouped.loc[zone]
            lg_pct = round(float(lg["FGM"] / lg["FGA"]), 3) if lg["FGA"] else None
        zones.append({
            "zone": zone,
            "fga": fga,
            "fgm": fgm,
            "pct": round(fgm / fga, 3) if fga else None,
            "league_pct": lg_pct,
            "diff": round(fgm / fga - lg_pct, 3) if fga and lg_pct is not None else None,
            "freq": round(fga / len(shots), 3),
        })

    by_distance = []
    for lo, hi, label in DISTANCE_BINS:
        g = shots[(shots["SHOT_DISTANCE"] >= lo) & (shots["SHOT_DISTANCE"] < hi)]
        if len(g) == 0:
            continue
        fga, fgm = len(g), int(g["SHOT_MADE_FLAG"].sum())
        by_distance.append({
            "range": label, "fga": fga, "fgm": fgm,
            "pct": round(fgm / fga, 3),
            "freq": round(fga / len(shots), 3),
        })

    fga_total = len(shots)
    fgm_total = int(shots["SHOT_MADE_FLAG"].sum())
    threes = shots[shots["SHOT_TYPE"].str.contains("3PT")]
    made_pts = int((shots["SHOT_MADE_FLAG"] *
                    shots["SHOT_TYPE"].map(lambda t: 3 if "3PT" in str(t) else 2)).sum())

    return {
        "points": points,
        "zones": zones,
        "by_distance": by_distance,
        "totals": {
            "fga": fga_total,
            "fgm": fgm_total,
            "fg_pct": round(fgm_total / fga_total, 3) if fga_total else None,
            "fg3a": int(len(threes)),
            "fg3m": int(threes["SHOT_MADE_FLAG"].sum()),
            "pts_from_field": made_pts,
            "pts_per_shot": round(made_pts / fga_total, 2) if fga_total else None,
            "avg_distance": round(float(shots["SHOT_DISTANCE"].mean()), 1),
        },
        "season": season,
        "season_type": season_type,
    }


def scoring_breakdown(player_id: int, season: str,
                      season_type: str = "Regular Season") -> dict:
    """Assisted vs unassisted + where points come from (Scoring measure)."""
    rows = api.league_player_stats(season, per_mode="PerGame",
                                   measure="Scoring", season_type=season_type)
    me = next((r for r in rows if r["PLAYER_ID"] == player_id), None)
    if not me:
        return {}
    pick = {
        "pct_ast_2pm": "PCT_AST_2PM", "pct_uast_2pm": "PCT_UAST_2PM",
        "pct_ast_3pm": "PCT_AST_3PM", "pct_uast_3pm": "PCT_UAST_3PM",
        "pct_ast_fgm": "PCT_AST_FGM", "pct_uast_fgm": "PCT_UAST_FGM",
        "pct_pts_paint": "PCT_PTS_PAINT", "pct_pts_mid": "PCT_PTS_2PT_MR",
        "pct_pts_3pt": "PCT_PTS_3PT", "pct_pts_ft": "PCT_PTS_FT",
        "pct_pts_fastbreak": "PCT_PTS_FB", "pct_pts_off_tov": "PCT_PTS_OFF_TOV",
    }
    return {k: me.get(col) for k, col in pick.items() if me.get(col) is not None}
