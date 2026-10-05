"""Player search, bio, summary card, and filtered stat bundles."""
import copy
import difflib
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager

import pandas as pd
from nba_api.stats.static import players as static_players

from ..nba import api
from ..nba.seasons import current_season, forward_roster_season, is_current_or_future_season
from . import frames, percentiles

HEADSHOT_URL = "https://cdn.nba.com/headshots/nba/latest/1040x760/{pid}.png"

POSITION_LABEL = {"G": "guards", "F": "forwards", "C": "centers"}

# The NBA client already coalesces individual upstream calls.  These small
# process-local caches avoid repeating the dataframe assembly and roster merge
# for the hot search and summary paths. Current-season derived values last at
# most five minutes, so they cannot extend the NBA client's 12-hour freshness
# window (or hide its bounded stale-if-error result).
_runtime_lock = threading.Lock()
_key_locks_guard = threading.Lock()
_key_locks: dict[object, tuple[threading.Lock, int]] = {}
_lookup_cache: dict[str, tuple[float | None, list[dict]]] = {}
_summary_cache: dict[tuple[int, str, str], tuple[float | None, dict]] = {}
_MAX_RUNTIME_CACHE_ENTRIES = 256
DERIVED_CURRENT_SEASON_TTL = 5 * 60


def _expires_at(season: str) -> float | None:
    return time.monotonic() + DERIVED_CURRENT_SEASON_TTL if is_current_or_future_season(season) else None


def _cached_value(store: dict, key: object) -> object | None:
    with _runtime_lock:
        entry = store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if expires_at is not None and time.monotonic() >= expires_at:
            store.pop(key, None)
            return None
        return copy.deepcopy(value)


def _store_value(store: dict, key: object, season: str, value: object) -> None:
    if key not in store and len(store) >= _MAX_RUNTIME_CACHE_ENTRIES:
        store.pop(next(iter(store)))
    store[key] = (_expires_at(season), copy.deepcopy(value))


@contextmanager
def _runtime_key_lock(key: object) -> Iterator[None]:
    """Coalesce one derived result without serializing unrelated players."""
    with _key_locks_guard:
        lock, users = _key_locks.get(key, (threading.Lock(), 0))
        _key_locks[key] = (lock, users + 1)
    lock.acquire()
    try:
        yield
    finally:
        lock.release()
        with _key_locks_guard:
            active_lock, users = _key_locks.get(key, (lock, 1))
            if active_lock is lock and users <= 1:
                _key_locks.pop(key, None)
            elif active_lock is lock:
                _key_locks[key] = (lock, users - 1)


def clear_runtime_caches() -> None:
    """Clear derived caches; used by tests and application maintenance."""
    with _runtime_lock:
        _lookup_cache.clear()
        _summary_cache.clear()


def player_lookup_index(season: str | None = None) -> list[dict]:
    """Season participants plus current players with zero season appearances.

    The season index supplies real season stats. The bundled current-player
    registry ensures a fully injured/inactive player remains searchable. During
    the offseason transition, the next-season NBA roster index fills in current
    team, position and jersey data and includes newly added players.
    """
    season = season or current_season()
    if (cached := _cached_value(_lookup_cache, season)) is not None:
        return cached  # type: ignore[return-value]

    # Serialize only cache misses. This gives concurrent type-ahead requests
    # one roster merge and one upstream index request instead of a stampede.
    with _runtime_key_lock(("lookup", season)):
        if (cached := _cached_value(_lookup_cache, season)) is not None:
            return cached  # type: ignore[return-value]
        result = _build_player_lookup_index(season)
        with _runtime_lock:
            _store_value(_lookup_cache, season, season, result)
        return result


def _build_player_lookup_index(season: str) -> list[dict]:
    merged: dict[int, dict] = {}
    for row in api.player_index(season):
        item = dict(row)
        item["_HAS_SEASON_STATS"] = True
        item["_CURRENT_ROSTER"] = False
        item["_LOOKUP_SEASON"] = season
        merged[item["PERSON_ID"]] = item

    roster_season = forward_roster_season()
    if roster_season:
        for row in api.active_player_index(roster_season):
            player_id = row["PERSON_ID"]
            if player_id in merged:
                # Preserve 2025-26 averages but show the latest roster details.
                item = merged[player_id]
                for key in (
                    "TEAM_ID", "TEAM_SLUG", "TEAM_CITY", "TEAM_NAME",
                    "TEAM_ABBREVIATION", "JERSEY_NUMBER", "POSITION",
                    "HEIGHT", "WEIGHT",
                ):
                    if row.get(key) not in (None, ""):
                        item[key] = row[key]
                item["_CURRENT_ROSTER"] = True
            else:
                item = dict(row)
                item["_HAS_SEASON_STATS"] = False
                item["_CURRENT_ROSTER"] = True
                item["_LOOKUP_SEASON"] = season
                merged[player_id] = item

    # This local registry covers zero-game active players even before the NBA
    # begins publishing the next-season roster endpoint.
    for row in static_players.get_active_players():
        player_id = row["id"]
        if player_id in merged:
            merged[player_id]["_CURRENT_ROSTER"] = True
            continue
        merged[player_id] = {
            "PERSON_ID": player_id,
            "PLAYER_FIRST_NAME": row["first_name"],
            "PLAYER_LAST_NAME": row["last_name"],
            "TEAM_ID": 0,
            "TEAM_ABBREVIATION": None,
            "TEAM_CITY": None,
            "TEAM_NAME": None,
            "POSITION": None,
            "JERSEY_NUMBER": None,
            "PTS": None,
            "REB": None,
            "AST": None,
            "_HAS_SEASON_STATS": False,
            "_CURRENT_ROSTER": True,
            "_LOOKUP_SEASON": season,
        }
    return list(merged.values())


def search(query: str, limit: int = 12) -> list[dict]:
    """Search season participants + current roster players by name."""
    season = current_season()
    idx = player_lookup_index(season)
    q = query.lower().strip()
    scored = []
    for r in idx:
        full = f"{r['PLAYER_FIRST_NAME']} {r['PLAYER_LAST_NAME']}".strip()
        low = full.lower()
        if q in low or all(part in low for part in q.split()):
            starts = low.startswith(q)
            scored.append((0 if starts else 1, full, r))
    if not scored:
        # Typo tolerance: "daminion lilard" should still find Damian Lillard.
        by_name: dict[str, tuple[str, dict]] = {}
        for r in idx:
            full = f"{r['PLAYER_FIRST_NAME']} {r['PLAYER_LAST_NAME']}".strip()
            by_name.setdefault(full.lower(), (full, r))
        close = difflib.get_close_matches(q, by_name.keys(), n=limit, cutoff=0.6)
        if not close and len(q.split()) > 1:
            # Match on last name alone ("lilard" -> Lillard)
            last = q.split()[-1]
            last_map: dict[str, list[str]] = {}
            for low, (_full, _row) in by_name.items():
                last_map.setdefault(low.split()[-1], []).append(low)
            for hit in difflib.get_close_matches(last, last_map.keys(), n=3,
                                                 cutoff=0.7):
                close.extend(last_map[hit])
        scored = [(2, by_name[c][0], by_name[c][1])
                  for c in dict.fromkeys(close)]
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
            "lookup_season": r.get("_LOOKUP_SEASON", season),
            "has_season_stats": bool(r.get("_HAS_SEASON_STATS", True)),
            "current_roster": bool(r.get("_CURRENT_ROSTER", False)),
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
        parts.append(f"and is one of the highest-volume scorers among {pos}")
    return " ".join(parts) + "."


def summary(player_id: int, season: str | None = None,
            season_type: str = "Regular Season") -> dict:
    season = season or current_season()
    cache_key = (player_id, season, season_type)
    if (cached := _cached_value(_summary_cache, cache_key)) is not None:
        return cached  # type: ignore[return-value]

    with _runtime_key_lock(("summary", cache_key)):
        if (cached := _cached_value(_summary_cache, cache_key)) is not None:
            return cached  # type: ignore[return-value]
        result = _build_summary(player_id, season, season_type)
        with _runtime_lock:
            _store_value(_summary_cache, cache_key, season, result)
        return result


def _build_summary(player_id: int, season: str, season_type: str) -> dict:
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
        "season_games": len(df),
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
