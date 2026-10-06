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
            "fg3a": len(threes),
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


# Closest-defender buckets, ordered tightest -> most open. The NBA labels them
# e.g. "0-2 Feet - Very Tight"; we match on the leading distance range.
_DEF_DIST_ORDER = ["0-2 Feet", "2-4 Feet", "4-6 Feet", "6+ Feet"]
# "Tight" = defender within 4 ft; the contested-shot-making rating is built from
# these buckets only.
_TIGHT_RANGES = {"0-2 Feet", "2-4 Feet"}
_MIN_TIGHT_FGA = 30  # below this, report the rating as low-confidence


def _efg(fgm: float, fg3m: float, fga: float) -> float | None:
    return round((fgm + 0.5 * fg3m) / fga, 3) if fga else None


def _dist_key(label: str) -> str:
    """Map a NBA CLOSE_DEF_DIST_RANGE label to its leading distance bucket."""
    for key in _DEF_DIST_ORDER:
        if str(label).startswith(key):
            return key
    return str(label)


def contested_shooting(player_id: int, season: str,
                       season_type: str = "Regular Season") -> dict:
    """Descriptive shooting splits by closest-defender distance.

    Source: NBA public player-tracking summaries (playerdashptshots,
    ClosestDefenderShooting). These are per-player AGGREGATE buckets, not
    shot-level records, and describe how well THIS player shoots when guarded
    closely vs left open (an offensive trait). They are NOT a defensive rating
    and are NOT inputs to the xFG model.

    Returns normalized buckets (defender-distance range, FGA, frequency, FG%,
    eFG%) ordered tightest -> most open, plus a descriptive offensive
    "contested shot-making" rating with honest small-sample caveats.
    """
    data = api.player_pt_shots(player_id, season, season_type)
    rows = data.get("ClosestDefenderShooting", [])
    df = pd.DataFrame(rows)
    if df.empty:
        return {"available": False,
                "reason": f"No tracking shooting splits for this player in {season}."}

    buckets = []
    for _, r in df.iterrows():
        fga = float(r.get("FGA", 0) or 0)
        if fga <= 0:
            continue
        fgm = float(r.get("FGM", 0) or 0)
        fg3m = float(r.get("FG3M", 0) or 0)
        buckets.append({
            "range": _dist_key(r.get("CLOSE_DEF_DIST_RANGE", "")),
            "label": str(r.get("CLOSE_DEF_DIST_RANGE", "")),
            "fga": int(fga),
            "frequency": round(float(r.get("FGA_FREQUENCY", 0) or 0), 3),
            "fg_pct": round(float(r.get("FG_PCT", 0) or 0), 3),
            "efg_pct": _efg(fgm, fg3m, fga),
        })
    if not buckets:
        return {"available": False,
                "reason": f"No shot attempts recorded by defender distance in {season}."}

    order = {key: i for i, key in enumerate(_DEF_DIST_ORDER)}
    buckets.sort(key=lambda b: order.get(str(b["range"]), 99))

    rating = _contested_rating(buckets)
    return {
        "available": True,
        "season": season,
        "season_type": season_type,
        "buckets": buckets,
        "rating": rating,
        "source_note": (
            "NBA player-tracking splits (closest-defender distance). These are "
            "descriptive aggregate buckets of how this player shoots when guarded "
            "closely vs open — an offensive trait. They are not a defensive "
            "rating and are not inputs to the xFG shot-quality model."
        ),
    }


def _contested_rating(buckets: list[dict]) -> dict:
    """Descriptive offensive shot-making-under-contest rating from the buckets."""
    by_range = {b["range"]: b for b in buckets}
    tight = [by_range[k] for k in _TIGHT_RANGES if k in by_range]
    open_ = [by_range[k] for k in ("4-6 Feet", "6+ Feet") if k in by_range]

    def _blend(group: list[dict]) -> tuple[float | None, int]:
        fga = sum(b["fga"] for b in group)
        if not fga:
            return None, 0
        made = sum((b["fg_pct"] or 0) * b["fga"] for b in group)
        return round(made / fga, 3), fga

    tight_fg, tight_fga = _blend(tight)
    open_fg, open_fga = _blend(open_)
    drop = (round(open_fg - tight_fg, 3)
            if tight_fg is not None and open_fg is not None else None)

    if tight_fg is None:
        label = "insufficient data"
    elif tight_fga < _MIN_TIGHT_FGA:
        label = "low confidence (small sample)"
    elif tight_fg >= 0.50:
        label = "elite under tight coverage"
    elif tight_fg >= 0.45:
        label = "strong under tight coverage"
    elif tight_fg >= 0.40:
        label = "average under tight coverage"
    else:
        label = "struggles under tight coverage"

    return {
        "tight_fg_pct": tight_fg,          # defender within 4 ft
        "tight_fga": tight_fga,
        "open_fg_pct": open_fg,            # defender 4+ ft
        "open_fga": open_fga,
        "contest_drop": drop,              # open FG% minus tight FG% (>=0 usual)
        "label": label,
        "confidence": "low" if tight_fga < _MIN_TIGHT_FGA else "ok",
        "caveat": (
            "Descriptive offensive rating from NBA tracking buckets; small "
            "playoff/early-season samples are noisy. Not a defensive metric."
        ),
    }
