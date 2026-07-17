"""Player search, bio, summary card, and filtered stat bundles."""
import pandas as pd

from ..nba import api
from ..nba.seasons import current_season
from . import frames, percentiles

HEADSHOT_URL = "https://cdn.nba.com/headshots/nba/latest/1040x760/{pid}.png"

POSITION_LABEL = {"G": "guards", "F": "forwards", "C": "centers"}


def search(query: str, limit: int = 12) -> list[dict]:
    """Search current + recent players by name (case/word-order insensitive)."""
    season = current_season()
    idx = api.player_index(season)
    q = query.lower().strip()
    scored = []
    for r in idx:
        full = f"{r['PLAYER_FIRST_NAME']} {r['PLAYER_LAST_NAME']}".strip()
        low = full.lower()
        if q in low or all(part in low for part in q.split()):
            starts = low.startswith(q)
            scored.append((0 if starts else 1, full, r))
    scored.sort(key=lambda t: (t[0], t[1]))
    out = []
    for _, full, r in scored[:limit]:
        out.append({
            "player_id": r["PERSON_ID"],
            "name": full,
            "team": r.get("TEAM_ABBREVIATION"),
            "team_name": f"{r.get('TEAM_CITY') or ''} {r.get('TEAM_NAME') or ''}".strip() or None,
            "position": r.get("POSITION"),
            "jersey": r.get("JERSEY_NUMBER"),
            "headshot": HEADSHOT_URL.format(pid=r["PERSON_ID"]),
            "ppg": r.get("PTS"),
            "rpg": r.get("REB"),
            "apg": r.get("AST"),
        })
    return out


def bio(player_id: int) -> dict:
    info = api.common_player_info(player_id)
    return {
        "player_id": player_id,
        "name": info.get("DISPLAY_FIRST_LAST"),
        "team": info.get("TEAM_ABBREVIATION"),
        "team_id": info.get("TEAM_ID"),
        "team_name": f"{info.get('TEAM_CITY') or ''} {info.get('TEAM_NAME') or ''}".strip() or None,
        "position": info.get("POSITION"),
        "jersey": info.get("JERSEY"),
        "height": info.get("HEIGHT"),
        "weight": info.get("WEIGHT"),
        "birthdate": (info.get("BIRTHDATE") or "")[:10] or None,
        "country": info.get("COUNTRY"),
        "experience": info.get("SEASON_EXP"),
        "draft": {
            "year": info.get("DRAFT_YEAR"),
            "round": info.get("DRAFT_ROUND"),
            "pick": info.get("DRAFT_NUMBER"),
        },
        "from_year": info.get("FROM_YEAR"),
        "to_year": info.get("TO_YEAR"),
        "headshot": HEADSHOT_URL.format(pid=player_id),
    }


def _age_from_birthdate(birthdate: str | None) -> int | None:
    if not birthdate:
        return None
    born = pd.Timestamp(birthdate)
    today = pd.Timestamp.today()
    return int((today - born).days // 365.25)


def _blurb(name: str, agg: dict, pcts: dict, pos_group: str) -> str:
    pg = agg.get("per_game", {})
    sh = agg.get("shooting", {})
    pos = POSITION_LABEL.get(pos_group, "players")
    parts = [
        f"{name} is averaging {pg.get('PTS', 0):.1f} points, "
        f"{pg.get('REB', 0):.1f} rebounds and {pg.get('AST', 0):.1f} assists "
        f"in {pg.get('MIN', 0):.1f} minutes per game"
    ]
    ts = sh.get("TS_PCT")
    if ts is not None:
        ts_pct_rank = pcts.get("TS_PCT", {}).get("percentile")
        desc = ""
        if ts_pct_rank is not None:
            if ts_pct_rank >= 80:
                desc = "elite efficiency"
            elif ts_pct_rank >= 60:
                desc = "strong efficiency"
            elif ts_pct_rank >= 40:
                desc = "league-average efficiency"
            else:
                desc = "below-average efficiency"
            parts.append(
                f"with {desc} ({ts * 100:.1f}% true shooting, "
                f"better than {ts_pct_rank}% of {pos})"
            )
        else:
            parts.append(f"on {ts * 100:.1f}% true shooting")
    scoring_rank = pcts.get("PTS", {}).get("percentile")
    if scoring_rank is not None and scoring_rank >= 85:
        parts.append(f"— one of the highest-volume scorers among {pos}")
    return " ".join(parts) + "."


def summary(player_id: int, season: str | None = None,
            season_type: str = "Regular Season") -> dict:
    season = season or current_season()
    info = bio(player_id)
    df = frames.merged_logs(player_id, season, season_type)
    agg = frames.aggregate(df)
    pcts = {}
    pos_group = percentiles._position_group(info.get("position"))
    if not df.empty:
        try:
            pcts = percentiles.player_percentiles(
                player_id, season, season_type,
                stats=["PTS", "REB", "AST", "TS_PCT", "USG_PCT", "MIN"])
        except RuntimeError:
            pcts = {}

    return {
        **info,
        "age": _age_from_birthdate(info.get("birthdate")),
        "season": season,
        "season_type": season_type,
        "stats": agg,
        "percentiles": pcts,
        "blurb": _blurb(info.get("name") or "This player", agg, pcts, pos_group)
        if agg.get("games") else f"No games played in {season} {season_type.lower()}.",
    }


def stat_bundle(player_id: int, f: frames.LogFilters) -> dict:
    """Aggregate stats for an arbitrary filter combination."""
    df = frames.merged_logs(player_id, f.season, f.season_type)
    filtered = frames.apply_filters(df, f)
    agg = frames.aggregate(filtered)
    return {
        "filters": f.__dict__,
        "season_games": int(len(df)),
        "stats": agg,
    }


def overview(player_id: int, f: frames.LogFilters) -> dict:
    """Performance Overview: headline stats + position percentiles."""
    bundle = stat_bundle(player_id, f)
    try:
        pcts = percentiles.player_percentiles(
            player_id, f.season, f.season_type,
            stats=["PTS", "REB", "AST", "STL", "BLK", "TOV", "PF", "MIN",
                   "PLUS_MINUS", "TS_PCT", "USG_PCT", "EFG_PCT", "AST_TO",
                   "OFF_RATING", "DEF_RATING", "NET_RATING"])
    except RuntimeError:
        pcts = {}
    bundle["percentiles"] = pcts
    return bundle
