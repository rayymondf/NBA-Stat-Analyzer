from datetime import date

from fastapi import APIRouter, HTTPException, Query

from ..nba.seasons import current_season
from ..routing import (
    GameId,
    Location,
    Outcome,
    PlayerId,
    SearchQuery,
    Season,
    SeasonType,
    TeamAbbreviation,
)
from ..schemas import JsonObject, JsonObjectList
from ..services import (
    efficiency,
    fouls,
    frames,
    gamelog,
    impact,
    ml,
    players,
    playtime,
    shooting,
    trends,
)

router = APIRouter(prefix="/players", tags=["players"])


def _filters(season: str | None, season_type: SeasonType, location: Location | None,
             outcome: Outcome | None, starter: bool | None, last_n: int | None,
             opponent: str | None, date_from: date | None,
             date_to: date | None) -> frames.LogFilters:
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must not be after date_to")
    return frames.LogFilters(
        season=season or current_season(),
        season_type=str(season_type),
        location=str(location) if location else None,
        outcome=str(outcome) if outcome else None,
        starter=starter,
        last_n=last_n,
        opponent=opponent,
        date_from=date_from.isoformat() if date_from else None,
        date_to=date_to.isoformat() if date_to else None,
    )


@router.get("/search", response_model=JsonObjectList)
def search(q: SearchQuery):
    return players.search(q)


@router.get("/{player_id}/summary", response_model=JsonObject)
def summary(player_id: PlayerId, season: Season | None = None,
            season_type: SeasonType = SeasonType.REGULAR):
    return players.summary(player_id, season, str(season_type))


@router.get("/{player_id}/overview", response_model=JsonObject)
def overview(player_id: PlayerId, season: Season | None = None,
             season_type: SeasonType = SeasonType.REGULAR,
             location: Location | None = None, outcome: Outcome | None = None,
             starter: bool | None = None,
             last_n: int | None = Query(default=None, ge=1, le=82),
             opponent: TeamAbbreviation | None = None,
             date_from: date | None = None, date_to: date | None = None):
    f = _filters(season, season_type, location, outcome, starter, last_n,
                 opponent, date_from, date_to)
    return players.overview(player_id, f)


@router.get("/{player_id}/shooting", response_model=JsonObject)
def shot_profile(player_id: PlayerId, season: Season | None = None,
                 season_type: SeasonType = SeasonType.REGULAR,
                 opponent_team_id: int = Query(default=0, ge=0),
                 game_id: str | None = Query(default=None, pattern=r"^\d{10}$")):
    season = season or current_season()
    profile = shooting.shot_profile(player_id, season, str(season_type),
                                    opponent_team_id, game_id)
    profile["scoring_breakdown"] = shooting.scoring_breakdown(
        player_id, season, str(season_type))
    return profile


@router.get("/{player_id}/shot-quality", response_model=JsonObject)
def shot_quality(player_id: PlayerId, season: Season | None = None,
                 season_type: SeasonType = SeasonType.REGULAR):
    return ml.shot_quality(player_id, season, str(season_type))


@router.get("/{player_id}/efficiency", response_model=JsonObject)
def efficiency_dashboard(player_id: PlayerId, season: Season | None = None,
                         season_type: SeasonType = SeasonType.REGULAR):
    return efficiency.efficiency(player_id, season or current_season(),
                                 str(season_type))


@router.get("/{player_id}/playtime", response_model=JsonObject)
def playtime_dashboard(player_id: PlayerId, season: Season | None = None,
                       season_type: SeasonType = SeasonType.REGULAR):
    return playtime.playtime(player_id, season or current_season(), str(season_type))


@router.get("/{player_id}/fouls", response_model=JsonObject)
def fouls_dashboard(player_id: PlayerId, season: Season | None = None,
                    season_type: SeasonType = SeasonType.REGULAR,
                    pbp_games: int = Query(default=10, ge=1, le=20)):
    return fouls.fouls(player_id, season or current_season(), str(season_type),
                       pbp_games)


@router.get("/{player_id}/gamelog", response_model=JsonObject)
def game_log(player_id: PlayerId, season: Season | None = None,
             season_type: SeasonType = SeasonType.REGULAR,
             location: Location | None = None, outcome: Outcome | None = None,
             starter: bool | None = None,
             last_n: int | None = Query(default=None, ge=1, le=82),
             opponent: TeamAbbreviation | None = None,
             date_from: date | None = None, date_to: date | None = None):
    f = _filters(season, season_type, location, outcome, starter, last_n,
                 opponent, date_from, date_to)
    return gamelog.game_log(player_id, f)


@router.get("/{player_id}/games/{game_id}", response_model=JsonObject)
def game_detail(player_id: PlayerId, game_id: GameId):
    return gamelog.game_detail(player_id, game_id)


@router.get("/{player_id}/trends", response_model=JsonObject)
def season_trends(player_id: PlayerId, season: Season | None = None,
                  season_type: SeasonType = SeasonType.REGULAR,
                  window: int = Query(default=10, ge=3, le=30)):
    return trends.season_trends(player_id, season or current_season(),
                                str(season_type), window)


@router.get("/{player_id}/career", response_model=JsonObject)
def career(player_id: PlayerId):
    return trends.career(player_id)


@router.get("/{player_id}/impact", response_model=JsonObject)
def impact_dashboard(player_id: PlayerId, season: Season | None = None,
                     season_type: SeasonType = SeasonType.REGULAR):
    info = players.bio(player_id)
    team_id = info.get("team_id")
    if not team_id:
        raise HTTPException(status_code=404, detail="Player has no current team")
    return impact.impact(player_id, team_id, season or current_season(),
                         str(season_type))
