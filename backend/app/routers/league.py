from typing import Literal

from fastapi import APIRouter, Query

from ..nba.seasons import current_season, previous_season
from ..routing import PlayerId, Season, SeasonType
from ..schemas import JsonObject, JsonObjectList
from ..services import compare, game_investigation, league

router = APIRouter(tags=["league"])


def _latest_game_date(season: str) -> str | None:
    """Most recent completed game across playoffs + regular season."""
    for season_type in ("Playoffs", "Regular Season"):
        try:
            games = game_investigation.list_games(season, season_type, limit=1)
        except RuntimeError:
            continue
        if games:
            return str(games[0]["date"])[:10]
    return None


@router.get("/meta", response_model=JsonObject)
def meta():
    # Everything derived from today's date at request time, so the app rolls
    # into new NBA seasons automatically (October) without code changes.
    cur = current_season()
    seasons = [cur]
    for _ in range(9):
        seasons.append(previous_season(seasons[-1]))
    data_through = _latest_game_date(cur)
    return {
        "current_season": cur,
        "seasons": seasons,
        "default_seasons": [cur, previous_season(cur)],
        "season_types": ["Regular Season", "Playoffs"],
        "data_through": data_through,
        "player_lookup_note": (
            "Player search covers today's NBA players: everyone who has "
            f"played in {cur}, plus current roster players yet to appear "
            "this season (injured, inactive or newly signed). Retired "
            "players are not searchable."),
        "freshness_note": (
            f"Official NBA.com statistics for the {seasons[-1]} through "
            f"{cur} seasons. {cur} stats refresh every 12 hours during the "
            "season; earlier seasons are complete and will not change. The "
            "app rolls forward to each new NBA season automatically every "
            "October."),
    }


@router.get("/compare", response_model=JsonObject)
def compare_players(a: int = Query(gt=0), b: int = Query(gt=0),
                    season: Season | None = None,
                    season_type: SeasonType = SeasonType.REGULAR):
    return compare.compare(a, b, season or current_season(), str(season_type))


@router.get("/league/leaders", response_model=JsonObjectList)
def leaders(season: Season | None = None,
            stat: Literal[
                "PTS", "REB", "AST", "STL", "BLK", "TOV", "FGM", "FGA",
                "FG_PCT", "FG3M", "FG3A", "FG3_PCT", "FTM", "FTA", "FT_PCT",
                "OREB", "DREB", "PLUS_MINUS", "MIN", "TS_PCT", "USG_PCT",
                "OFF_RATING", "DEF_RATING", "NET_RATING", "PACE",
            ] = "PTS",
            per_mode: Literal["Totals", "PerGame", "Per36", "Per100Possessions"] = "PerGame",
            measure: Literal["Base", "Advanced"] = "Base",
            season_type: SeasonType = SeasonType.REGULAR,
            limit: int = Query(default=15, ge=1, le=100)):
    return league.leaders(season or current_season(), stat, per_mode, measure,
                          str(season_type), limit)


@router.get("/league/improvers", response_model=JsonObjectList)
def improvers(season: Season | None = None,
              metric: Literal[
                  "TS_PCT", "USG_PCT", "AST_PCT", "REB_PCT", "OFF_RATING",
                  "DEF_RATING", "NET_RATING", "PACE",
              ] = "TS_PCT",
              season_type: SeasonType = SeasonType.REGULAR,
              limit: int = Query(default=15, ge=1, le=100)):
    return league.improvers(season or current_season(), metric, str(season_type),
                            limit)


@router.get("/league/similar/{player_id}", response_model=JsonObject)
def similar(player_id: PlayerId, season: Season | None = None,
            season_type: SeasonType = SeasonType.REGULAR,
            limit: int = Query(default=8, ge=1, le=25)):
    return league.similar_players(player_id, season or current_season(),
                                  str(season_type), limit)


@router.get("/league/low-minutes-efficient", response_model=JsonObjectList)
def low_minutes(season: Season | None = None,
                season_type: SeasonType = SeasonType.REGULAR,
                max_mpg: float = Query(default=24, ge=10, le=35),
                limit: int = Query(default=15, ge=1, le=100)):
    return league.low_minutes_efficient(season or current_season(),
                                        str(season_type), max_mpg, limit)


@router.get("/league/team-defense", response_model=JsonObjectList)
def team_defense(season: Season | None = None,
                 season_type: SeasonType = SeasonType.REGULAR):
    return league.team_defense(season or current_season(), str(season_type))
