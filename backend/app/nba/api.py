"""Typed wrappers for every nba_api endpoint the app uses.

Each function returns plain dicts/lists (already cached + rate-limited by
client.fetch). Services turn these into pandas frames and computed stats.
"""
import re

from nba_api.stats.endpoints import (
    boxscoretraditionalv3,
    commonplayerinfo,
    leaguedashplayerstats,
    leaguedashteamstats,
    leaguegamefinder,
    playbyplayv3,
    playerprofilev2,
    playerdashboardbyclutch,
    playerdashboardbygamesplits,
    playerdashboardbygeneralsplits,
    playergamelogs,
    playerindex,
    shotchartdetail,
    teamplayeronoffdetails,
)

from .client import fetch

REGULAR = "Regular Season"
PLAYOFFS = "Playoffs"


def player_game_logs(player_id: int, season: str, season_type: str = REGULAR,
                     measure: str | None = None) -> list[dict]:
    data = fetch(
        playergamelogs.PlayerGameLogs,
        player_id_nullable=player_id,
        season_nullable=season,
        season_type_nullable=season_type,
        measure_type_player_game_logs_nullable=measure,
    )
    return data.get("PlayerGameLogs", [])


def league_player_stats(season: str, per_mode: str = "PerGame",
                        measure: str = "Base",
                        season_type: str = REGULAR) -> list[dict]:
    data = fetch(
        leaguedashplayerstats.LeagueDashPlayerStats,
        season=season,
        per_mode_detailed=per_mode,
        measure_type_detailed_defense=measure,
        season_type_all_star=season_type,
    )
    return data.get("LeagueDashPlayerStats", [])


def player_index(season: str) -> list[dict]:
    data = fetch(playerindex.PlayerIndex, season=season, league_id="00")
    return data.get("PlayerIndex", [])


def active_player_index(season: str) -> list[dict]:
    """Official active roster index, including players with zero games."""
    data = fetch(
        playerindex.PlayerIndex,
        season=season,
        league_id="00",
        active_nullable="1",
        historical_nullable="0",
        ttl=12 * 3600,
    )
    return data.get("PlayerIndex", [])


def common_player_info(player_id: int) -> dict:
    data = fetch(commonplayerinfo.CommonPlayerInfo, player_id=player_id)
    rows = data.get("CommonPlayerInfo", [])
    return rows[0] if rows else {}


def career_stats(player_id: int, per_mode: str = "PerGame") -> dict:
    # PlayerCareerStats currently returns empty season rows; PlayerProfileV2
    # carries the same result sets and works.
    return fetch(playerprofilev2.PlayerProfileV2, player_id=player_id,
                 per_mode36=per_mode, ttl=12 * 3600)


def shot_chart(player_id: int, season: str, season_type: str = REGULAR,
               opponent_team_id: int = 0, game_id: str | None = None,
               context_measure: str = "FGA") -> dict:
    return fetch(
        shotchartdetail.ShotChartDetail,
        team_id=0,
        player_id=player_id,
        season_nullable=season,
        season_type_all_star=season_type,
        opponent_team_id=opponent_team_id,
        game_id_nullable=game_id,
        context_measure_simple=context_measure,
    )


def general_splits(player_id: int, season: str, season_type: str = REGULAR,
                   measure: str = "Base", per_mode: str = "PerGame") -> dict:
    return fetch(
        playerdashboardbygeneralsplits.PlayerDashboardByGeneralSplits,
        player_id=player_id,
        season=season,
        season_type_playoffs=season_type,
        measure_type_detailed=measure,
        per_mode_detailed=per_mode,
    )


def game_splits(player_id: int, season: str, season_type: str = REGULAR,
                per_mode: str = "Totals") -> dict:
    return fetch(
        playerdashboardbygamesplits.PlayerDashboardByGameSplits,
        player_id=player_id,
        season=season,
        season_type_playoffs=season_type,
        per_mode_detailed=per_mode,
    )


def clutch_dashboard(player_id: int, season: str,
                     season_type: str = REGULAR) -> dict:
    return fetch(
        playerdashboardbyclutch.PlayerDashboardByClutch,
        player_id=player_id,
        season=season,
        season_type_playoffs=season_type,
    )


def team_player_on_off(team_id: int, season: str,
                       season_type: str = REGULAR) -> dict:
    return fetch(
        teamplayeronoffdetails.TeamPlayerOnOffDetails,
        team_id=team_id,
        season=season,
        season_type_all_star=season_type,
        measure_type_detailed_defense="Advanced",
    )


def league_team_stats(season: str, measure: str = "Advanced",
                      season_type: str = REGULAR) -> list[dict]:
    data = fetch(
        leaguedashteamstats.LeagueDashTeamStats,
        season=season,
        measure_type_detailed_defense=measure,
        season_type_all_star=season_type,
    )
    return data.get("LeagueDashTeamStats", [])


def starter_game_ids(player_id: int, season: str,
                     season_type: str = REGULAR) -> set[str]:
    """Game IDs in which the player was in the starting lineup."""
    data = fetch(
        leaguegamefinder.LeagueGameFinder,
        player_or_team_abbreviation="P",
        player_id_nullable=player_id,
        season_nullable=season,
        season_type_nullable=season_type,
        starter_bench_nullable="Starters",
    )
    rows = data.get("LeagueGameFinderResults", [])
    return {r["GAME_ID"] for r in rows}


def minutes_float(value) -> float:
    """Parse V3 minute strings: 'PT36M10.00S', '36:10', 36.2, or ''."""
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    m = re.match(r"PT(\d+)M([\d.]+)S", str(value))
    if m:
        return round(int(m.group(1)) + float(m.group(2)) / 60, 2)
    if ":" in str(value):
        mins, secs = str(value).split(":")
        return round(int(mins) + int(secs) / 60, 2)
    try:
        return float(value)
    except ValueError:
        return 0.0


def boxscore_traditional(game_id: str) -> dict:
    """V3 boxscore: {homeTeam: {...players, statistics, starters, bench},
    awayTeam: {...}} — V2 returns empty rows for recent seasons."""
    data = fetch(boxscoretraditionalv3.BoxScoreTraditionalV3,
                 game_id=game_id, ttl=None, raw=True)
    return data.get("boxScoreTraditional", {})


def play_by_play(game_id: str) -> list[dict]:
    """V3 play-by-play action list (actionType/subType/scoreHome/scoreAway)."""
    data = fetch(playbyplayv3.PlayByPlayV3, game_id=game_id, ttl=None, raw=True)
    return data.get("game", {}).get("actions", [])


def find_team_games(season: str, season_type: str = REGULAR) -> list[dict]:
    """All team-game rows for a season (two rows per game, one per team)."""
    data = fetch(
        leaguegamefinder.LeagueGameFinder,
        player_or_team_abbreviation="T",
        season_nullable=season,
        season_type_nullable=season_type,
        league_id_nullable="00",
    )
    return data.get("LeagueGameFinderResults", [])
