"""Gemini function tools. Every tool wraps a service that computes real
statistics — the model itself never calculates numbers. Outputs are trimmed
to keep token usage low on the free tier."""
from ..nba.seasons import current_season, previous_season
from ..services import (compare, efficiency, frames, game_investigation,
                        impact as impact_svc, league, players, shooting,
                        trends)


SMALL_SAMPLE_GAMES = 15


def _round(obj, nd=3):
    if isinstance(obj, float):
        return round(obj, nd)
    if isinstance(obj, dict):
        return {k: _round(v, nd) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_round(v, nd) for v in obj]
    return obj


def _small_sample_note(games: int | None, season: str) -> str | None:
    """Nudge the model to also pull the previous season when a season is young
    (e.g. right after the October rollover the current season has ~5 games)."""
    if games is not None and games < SMALL_SAMPLE_GAMES:
        g = f"{games} game" + ("" if games == 1 else "s")
        return (f"Only {g} in {season} — small sample. Also query season "
                f"{previous_season(season)} and label which season each number "
                f"comes from before concluding.")
    return None


def search_player(name: str) -> list[dict]:
    """Find NBA players by name. Returns player_id, team and position for the
    best matches — always call this first when you only have a name."""
    return [{k: r[k] for k in ("player_id", "name", "team", "position")}
            for r in players.search(name, limit=5)]


def get_player_stats(player_id: int, season: str = "", season_type: str = "Regular Season",
                     location: str = "", outcome: str = "", last_n: int = 0,
                     opponent: str = "") -> dict:
    """Aggregated stats for a player with optional filters.
    season like '2025-26' (empty = current). location: 'home'/'away'.
    outcome: 'W'/'L'. last_n: only the most recent N games. opponent: team
    abbreviation like 'BOS'. Returns totals, per-game, per-75 and shooting
    efficiency for the filtered games."""
    f = frames.LogFilters(
        season=season or current_season(), season_type=season_type,
        location=location or None, outcome=outcome or None,
        last_n=last_n or None, opponent=opponent or None,
    )
    b = players.stat_bundle(player_id, f)
    s = b["stats"]
    out = _round({
        "filters": b["filters"],
        "games": s.get("games"), "wins": s.get("wins"), "losses": s.get("losses"),
        "per_game": s.get("per_game"), "per_75": s.get("per_75"),
        "shooting": s.get("shooting"),
    })
    note = _small_sample_note(s.get("games"), f.season)
    if note and not last_n:  # last_n is an intentional small sample, don't warn
        out["note"] = note
    return out


def get_player_percentiles(player_id: int, season: str = "",
                           season_type: str = "Regular Season") -> dict:
    """Position percentiles (0-100, higher = better) plus advanced metrics for
    a player's season: scoring, efficiency, usage, ratings."""
    eff = efficiency.efficiency(player_id, season or current_season(), season_type)
    return _round({
        "games": eff.get("games"),
        "metrics": eff.get("metrics"),
        "percentiles": {k: {"value": v["value"], "percentile": v["percentile"]}
                        for k, v in (eff.get("percentiles") or {}).items()},
    })


def get_shot_profile(player_id: int, season: str = "",
                     season_type: str = "Regular Season") -> dict:
    """Shooting by court zone vs league average, by distance, and totals."""
    p = shooting.shot_profile(player_id, season or current_season(), season_type)
    return _round({
        "totals": p.get("totals"),
        "zones": p.get("zones"),
        "by_distance": p.get("by_distance"),
    })


def get_trends(player_id: int, season: str = "",
               season_type: str = "Regular Season") -> dict:
    """Recent form vs season baseline (points/TS%, incl. a z-score for how
    unusual the last 10 games are) and rolling trend endpoints."""
    resolved = season or current_season()
    t = trends.season_trends(player_id, resolved, season_type)
    series = t.get("series") or []
    out = _round({
        "games": t.get("games"),
        "recent_form": t.get("recent_form"),
        "latest_rolling": series[-1] if series else None,
        "mid_season_rolling": series[len(series) // 2] if len(series) > 4 else None,
    })
    note = _small_sample_note(t.get("games"), resolved)
    if note:
        out["note"] = note
    return out


def get_career(player_id: int) -> dict:
    """Season-by-season career averages (regular season + playoffs)."""
    c = trends.career(player_id)
    return _round({
        "regular_season": c.get("regular_season", [])[-12:],
        "playoffs": c.get("playoffs", [])[-6:],
    })


def compare_players(player_a: int, player_b: int, season: str = "",
                    season_type: str = "Regular Season") -> dict:
    """Side-by-side comparison: per-game, per-75, shooting efficiency,
    position percentiles and shot zones for two players."""
    c = compare.compare(player_a, player_b, season or current_season(), season_type)

    def trim(block: dict) -> dict:
        return {
            "name": block["info"].get("name"),
            "team": block["info"].get("team"),
            "position": block["info"].get("position"),
            "games": block["stats"].get("games"),
            "per_game": block["stats"].get("per_game"),
            "per_75": block["stats"].get("per_75"),
            "shooting": block["stats"].get("shooting"),
            "percentiles": {k: v["percentile"] for k, v in (block.get("percentiles") or {}).items()},
            "zones": block.get("zones"),
        }
    return _round({"season": c["season"], "a": trim(c["a"]), "b": trim(c["b"])})


def league_query(kind: str, season: str = "", stat: str = "PTS",
                 limit: int = 10) -> list[dict]:
    """League-wide queries. kind must be one of:
    'leaders' (top players by a stat, e.g. stat='PTS','AST','REB'),
    'improvers' (biggest TS% improvement vs last season),
    'low_minutes_efficient' (efficient scorers under 24 MPG),
    'team_defense' (team defensive-rating rankings, best first)."""
    season = season or current_season()
    if kind == "leaders":
        return _round(league.leaders(season, stat=stat, limit=limit))
    if kind == "improvers":
        return _round(league.improvers(season, limit=limit))
    if kind == "low_minutes_efficient":
        return _round(league.low_minutes_efficient(season, limit=limit))
    if kind == "team_defense":
        return _round(league.team_defense(season))
    return [{"error": f"unknown kind '{kind}'"}]


def find_similar_players(player_id: int, season: str = "") -> dict:
    """Statistically similar players (z-scored per-100 profile distance)."""
    s = league.similar_players(player_id, season or current_season())
    return _round({
        "features": s.get("features"),
        "matches": [{k: m[k] for k in ("player_id", "name", "team", "distance")}
                    for m in s.get("matches", [])],
        "method": s.get("method"),
    })


def list_games(team: str = "", season: str = "", limit: int = 10) -> list[dict]:
    """Recent completed games, newest first. team = abbreviation like 'NYK'.
    Use this to find a game_id before investigating a game."""
    games = game_investigation.list_games(season or current_season(),
                                          team=team or None, limit=limit)
    return [{
        "game_id": g["game_id"], "date": str(g["date"])[:10],
        "home": f"{g['home']['abbr']} {g['home']['pts']}",
        "away": f"{g['away']['abbr']} {g['away']['pts']}",
    } for g in games]


def investigate_game(game_id: str) -> dict:
    """Full why-did-they-win/lose investigation for a completed game:
    ranked explanations with evidence for and against, four factors, star
    performances vs season averages, scoring runs and Q4 execution."""
    inv = game_investigation.investigate(game_id)
    inv.pop("teams", None)
    # The detailed evidence_for arrays duplicate four_factors, star_lines, runs
    # and q4 below. Keep summaries and counterevidence while avoiding hundreds
    # of repeated input tokens on every game investigation.
    inv["explanations"] = [
        {key: explanation.get(key) for key in (
            "key", "title", "favored", "score", "summary", "evidence_against"
        )}
        for explanation in inv.get("explanations", [])
    ]
    return _round(inv)


def get_game_log(player_id: int, season: str = "",
                 season_type: str = "Regular Season", last_n: int = 10) -> list[dict]:
    """Recent game-by-game lines for a player (newest first)."""
    f = frames.LogFilters(season=season or current_season(),
                          season_type=season_type, last_n=last_n or None)
    df = frames.apply_filters(frames.merged_logs(player_id, f.season, f.season_type), f)
    rows = frames.game_rows(df)[::-1]
    return [{k: r[k] for k in ("game_id", "date", "matchup", "wl", "min", "pts",
                               "reb", "ast", "tov", "pf", "plus_minus", "ts_pct")}
            for r in rows]


def get_on_off_impact(player_id: int, season: str = "") -> dict:
    """On/off net-rating estimate: how the team performs with the player on
    vs off the court. Estimates only — noisy in small samples."""
    info = players.bio(player_id)
    if not info.get("team_id"):
        return {"error": "player has no current team"}
    r = impact_svc.impact(player_id, info["team_id"], season or current_season())
    return _round({"current": r.get("current"), "disclaimer": r.get("disclaimer")})


def get_previous_season(season: str) -> dict:
    """The season string before the given one (e.g. '2025-26' -> '2024-25')."""
    return {"previous_season": previous_season(season)}


ALL_TOOLS = [
    search_player, get_player_stats, get_player_percentiles, get_shot_profile,
    get_trends, get_career, compare_players, league_query,
    find_similar_players, list_games, investigate_game, get_game_log,
    get_on_off_impact, get_previous_season,
]
