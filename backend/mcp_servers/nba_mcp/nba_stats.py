#!/usr/bin/env python3
"""MCP server: ``nba_stats`` — read-only NBA statistics.

Every tool here is a thin MCP wrapper around a function in ``app.ai.tools``.
Those functions already:
  * validate inputs (season format, id ranges, team abbreviations, enums),
  * fetch from NBA.com through the project's cached, rate-limited, circuit-broken
    client, and
  * trim outputs to the fields that matter.

So this module adds only the MCP surface: flat, described, constrained
parameters (FastMCP flattens individual typed parameters into a clean tool
schema; a single Pydantic-model parameter would instead nest everything under
``params``, which clients find awkward), read-only annotations, and docstrings.
It does NOT recompute statistics — the model never sees a number this project
did not compute from NBA.com data.

Run locally over stdio:
    python -m nba_mcp.nba_stats
"""
from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field
from mcp.server.fastmcp import FastMCP

from ._common import ResponseFormat, ensure_app_importable, handle_tool_error, to_json

# Make the project's ``app`` package importable before importing it.
ensure_app_importable()
from app.ai import tools  # noqa: E402  (import after sys.path bootstrap)

mcp = FastMCP("nba_stats")

READ_ONLY = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,  # reaches out to NBA.com (through the cache)
}

# --- Reusable annotated parameter types (DRY across tools) ---------------------

PlayerId = Annotated[int, Field(description="NBA player id (from nba_search_player).", ge=1, le=9_999_999_999)]
Season = Annotated[str, Field(default="", description="Season 'YYYY-YY' (e.g. '2024-25'); '' = current.", max_length=7)]
SeasonType = Annotated[str, Field(default="Regular Season", description="'Regular Season', 'Playoffs', or 'Pre Season'.")]
Fmt = Annotated[ResponseFormat, Field(default=ResponseFormat.JSON, description="'json' (default) or 'markdown'.")]


def _result(payload: Any, response_format: ResponseFormat) -> str:
    """Serialize a backend result for return to the MCP client."""
    if response_format is ResponseFormat.MARKDOWN:
        return "```json\n" + to_json(payload) + "\n```"
    return to_json(payload)


@mcp.tool(name="nba_search_player", annotations={"title": "Search NBA Players", **READ_ONLY})
async def nba_search_player(
    name: Annotated[str, Field(description="Player name; minor misspellings tolerated.", min_length=2, max_length=80)],
    response_format: Fmt = ResponseFormat.JSON,
) -> str:
    """Find NBA players by name and return their ids. ALWAYS call this first when
    you only have a name — every other nba_* tool needs a numeric player_id.

    Returns: JSON list of up to 5 matches, each
    {player_id:int, name:str, team:str, position:str}. Empty list = no match.
    """
    try:
        return _result(tools.search_player(name), response_format)
    except Exception as exc:  # noqa: BLE001 - converted to actionable text
        return handle_tool_error(exc)


@mcp.tool(name="nba_get_player_stats", annotations={"title": "Player Stats (filtered)", **READ_ONLY})
async def nba_get_player_stats(
    player_id: PlayerId,
    season: Season = "",
    season_type: SeasonType = "Regular Season",
    location: Annotated[str, Field(description="'home', 'away', or '' for both.")] = "",
    outcome: Annotated[str, Field(description="'W', 'L', or '' for both.")] = "",
    last_n: Annotated[int, Field(description="Only most recent N games (0 = all).", ge=0, le=82)] = 0,
    opponent: Annotated[str, Field(description="Opponent abbreviation e.g. 'BOS' ('' = any).", max_length=4)] = "",
    response_format: Fmt = ResponseFormat.JSON,
) -> str:
    """Aggregated stats for a player with optional home/away, W/L, last-N and
    opponent filters. Returns JSON: {filters, games, wins, losses, per_game,
    per_75, shooting, note?}. 'note' appears on small samples.
    """
    try:
        return _result(
            tools.get_player_stats(player_id, season, season_type, location, outcome, last_n, opponent),
            response_format,
        )
    except Exception as exc:  # noqa: BLE001
        return handle_tool_error(exc)


@mcp.tool(name="nba_get_player_percentiles", annotations={"title": "Player Percentiles", **READ_ONLY})
async def nba_get_player_percentiles(
    player_id: PlayerId, season: Season = "", season_type: SeasonType = "Regular Season",
    response_format: Fmt = ResponseFormat.JSON,
) -> str:
    """Position percentiles (0-100, higher = better) plus advanced metrics for a
    player's season. Returns JSON: {games, metrics,
    percentiles:{metric:{value, percentile}}}.
    """
    try:
        return _result(tools.get_player_percentiles(player_id, season, season_type), response_format)
    except Exception as exc:  # noqa: BLE001
        return handle_tool_error(exc)


@mcp.tool(name="nba_get_shot_profile", annotations={"title": "Shot Profile by Zone", **READ_ONLY})
async def nba_get_shot_profile(
    player_id: PlayerId, season: Season = "", season_type: SeasonType = "Regular Season",
    response_format: Fmt = ResponseFormat.JSON,
) -> str:
    """Shooting by court zone (vs league average), by distance, and totals.
    Returns JSON: {totals, zones, by_distance}.
    """
    try:
        return _result(tools.get_shot_profile(player_id, season, season_type), response_format)
    except Exception as exc:  # noqa: BLE001
        return handle_tool_error(exc)


@mcp.tool(name="nba_get_trends", annotations={"title": "Recent Form / Trends", **READ_ONLY})
async def nba_get_trends(
    player_id: PlayerId, season: Season = "", season_type: SeasonType = "Regular Season",
    response_format: Fmt = ResponseFormat.JSON,
) -> str:
    """Recent form vs season baseline (points, TS%, z-score for how unusual the
    last 10 games are) and rolling-trend endpoints. Returns JSON:
    {games, recent_form, latest_rolling, mid_season_rolling, note?}.
    """
    try:
        return _result(tools.get_trends(player_id, season, season_type), response_format)
    except Exception as exc:  # noqa: BLE001
        return handle_tool_error(exc)


@mcp.tool(name="nba_get_career", annotations={"title": "Career by Season", **READ_ONLY})
async def nba_get_career(
    player_id: PlayerId, response_format: Fmt = ResponseFormat.JSON,
) -> str:
    """Season-by-season career averages (regular season + playoffs). Returns JSON:
    {regular_season:[...recent], playoffs:[...recent]}.
    """
    try:
        return _result(tools.get_career(player_id), response_format)
    except Exception as exc:  # noqa: BLE001
        return handle_tool_error(exc)


@mcp.tool(name="nba_compare_players", annotations={"title": "Compare Two Players", **READ_ONLY})
async def nba_compare_players(
    player_a: Annotated[int, Field(description="First player id.", ge=1, le=9_999_999_999)],
    player_b: Annotated[int, Field(description="Second player id.", ge=1, le=9_999_999_999)],
    season: Season = "",
    season_type: SeasonType = "Regular Season",
    response_format: Fmt = ResponseFormat.JSON,
) -> str:
    """Side-by-side comparison of two players: per-game, per-75, shooting
    efficiency, position percentiles and shot zones. Returns JSON:
    {season, a:{...}, b:{...}}. Resolve both ids with nba_search_player first.
    """
    try:
        return _result(tools.compare_players(player_a, player_b, season, season_type), response_format)
    except Exception as exc:  # noqa: BLE001
        return handle_tool_error(exc)


@mcp.tool(name="nba_league_query", annotations={"title": "League-wide Query", **READ_ONLY})
async def nba_league_query(
    kind: Annotated[str, Field(description="'leaders', 'improvers', 'low_minutes_efficient', or 'team_defense'.")],
    season: Season = "",
    stat: Annotated[str, Field(description="For 'leaders': 'PTS','AST','REB','FG3M','PLUS_MINUS', etc.")] = "PTS",
    limit: Annotated[int, Field(description="Max rows (1-25).", ge=1, le=25)] = 10,
    response_format: Fmt = ResponseFormat.JSON,
) -> str:
    """League-wide leaderboards/rankings. kind='leaders' (top by `stat`),
    'improvers' (biggest TS% gain vs last season), 'low_minutes_efficient'
    (efficient scorers under 24 MPG), 'team_defense' (defensive-rating ranking,
    best first). Returns a JSON list of rows.
    """
    try:
        return _result(tools.league_query(kind, season, stat, limit), response_format)
    except Exception as exc:  # noqa: BLE001
        return handle_tool_error(exc)


@mcp.tool(name="nba_find_similar_players", annotations={"title": "Similar Players", **READ_ONLY})
async def nba_find_similar_players(
    player_id: PlayerId, season: Season = "", response_format: Fmt = ResponseFormat.JSON,
) -> str:
    """Statistically similar players by z-scored per-100 profile distance.
    Returns JSON: {features, matches:[{player_id, name, team, distance}], method}.
    """
    try:
        return _result(tools.find_similar_players(player_id, season), response_format)
    except Exception as exc:  # noqa: BLE001
        return handle_tool_error(exc)


@mcp.tool(name="nba_list_games", annotations={"title": "List Recent Games", **READ_ONLY})
async def nba_list_games(
    team: Annotated[str, Field(description="Team abbreviation like 'NYK' ('' = all).", max_length=4)] = "",
    season: Season = "",
    limit: Annotated[int, Field(description="Max games, newest first (1-50).", ge=1, le=50)] = 10,
    response_format: Fmt = ResponseFormat.JSON,
) -> str:
    """Recent completed games (newest first). Use to find a game_id before
    nba_investigate_game. Returns JSON list of
    {game_id, date, home:'ABB pts', away:'ABB pts'}.
    """
    try:
        return _result(tools.list_games(team, season, limit), response_format)
    except Exception as exc:  # noqa: BLE001
        return handle_tool_error(exc)


@mcp.tool(name="nba_investigate_game", annotations={"title": "Investigate a Game", **READ_ONLY})
async def nba_investigate_game(
    game_id: Annotated[str, Field(description="10-digit NBA game id (from nba_list_games).", min_length=10, max_length=10)],
    response_format: Fmt = ResponseFormat.JSON,
) -> str:
    """Full why-did-they-win/lose breakdown for one completed game: ranked
    explanations with counterevidence, four factors, star performances vs season
    averages, scoring runs, Q4 execution. Returns a JSON object.
    """
    try:
        return _result(tools.investigate_game(game_id), response_format)
    except Exception as exc:  # noqa: BLE001
        return handle_tool_error(exc)


@mcp.tool(name="nba_get_game_log", annotations={"title": "Player Game Log", **READ_ONLY})
async def nba_get_game_log(
    player_id: PlayerId,
    season: Season = "",
    season_type: SeasonType = "Regular Season",
    last_n: Annotated[int, Field(description="Recent games to return, newest first (1-82).", ge=1, le=82)] = 10,
    response_format: Fmt = ResponseFormat.JSON,
) -> str:
    """Recent game-by-game lines for a player (newest first). Returns JSON list of
    {game_id, date, matchup, wl, min, pts, reb, ast, tov, pf, plus_minus, ts_pct}.
    """
    try:
        return _result(tools.get_game_log(player_id, season, season_type, last_n), response_format)
    except Exception as exc:  # noqa: BLE001
        return handle_tool_error(exc)


@mcp.tool(name="nba_get_on_off_impact", annotations={"title": "On/Off Impact", **READ_ONLY})
async def nba_get_on_off_impact(
    player_id: PlayerId, season: Season = "", response_format: Fmt = ResponseFormat.JSON,
) -> str:
    """On/off net-rating estimate: team performance with the player on vs off the
    court. Returns JSON {current, disclaimer} — estimates only, noisy in small
    samples; cite the disclaimer.
    """
    try:
        return _result(tools.get_on_off_impact(player_id, season), response_format)
    except Exception as exc:  # noqa: BLE001
        return handle_tool_error(exc)


@mcp.tool(name="nba_get_elimination_game_stats", annotations={"title": "Elimination-Game Stats", **READ_ONLY})
async def nba_get_elimination_game_stats(
    player_id: PlayerId,
    seasons_back: Annotated[int, Field(description="Recent playoff seasons to scan (1-20).", ge=1, le=20)] = 6,
    response_format: Fmt = ResponseFormat.JSON,
) -> str:
    """Playoff elimination-game analysis: how a player performs facing elimination
    (down 3 in a series) vs closeout games vs their playoff baseline, with the
    individual elimination-game lines as evidence. Use for 'is X good/bad in
    win-or-go-home games'. Returns a JSON object.
    """
    try:
        return _result(tools.get_elimination_game_stats(player_id, seasons_back), response_format)
    except Exception as exc:  # noqa: BLE001
        return handle_tool_error(exc)


@mcp.tool(name="nba_get_shot_quality", annotations={"title": "Shot Quality (xFG model)", **READ_ONLY})
async def nba_get_shot_quality(
    player_id: PlayerId, season: Season = "", season_type: SeasonType = "Regular Season",
    response_format: Fmt = ResponseFormat.JSON,
) -> str:
    """ML shot-quality (xFG) estimate: what an average NBA player would shoot from
    this player's exact shot locations vs what they actually shot. Positive delta
    = makes more than expected. Includes per-zone deltas and a league percentile.
    This is a TRAINED-MODEL ESTIMATE — label it as such when citing it. Returns a
    JSON object.
    """
    try:
        return _result(tools.get_shot_quality(player_id, season, season_type), response_format)
    except Exception as exc:  # noqa: BLE001
        return handle_tool_error(exc)


@mcp.tool(name="nba_get_previous_season",
          annotations={"title": "Previous Season String", **READ_ONLY, "openWorldHint": False})
async def nba_get_previous_season(
    season: Annotated[str, Field(description="Season 'YYYY-YY', e.g. '2025-26'.", min_length=7, max_length=7)],
    response_format: Fmt = ResponseFormat.JSON,
) -> str:
    """Return the season string before a given one (e.g. '2025-26' -> '2024-25').
    Pure string helper; does not contact NBA.com. Returns JSON {previous_season}.
    """
    try:
        return _result(tools.get_previous_season(season), response_format)
    except Exception as exc:  # noqa: BLE001
        return handle_tool_error(exc)


def main() -> None:
    """Console-script / module entrypoint. Runs the server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
