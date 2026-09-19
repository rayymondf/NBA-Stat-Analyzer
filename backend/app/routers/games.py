from fastapi import APIRouter, HTTPException, Query

from ..nba.seasons import current_season
from ..routing import GameId, Season, SeasonType, TeamAbbreviation
from ..schemas import JsonObject, JsonObjectList
from ..services import game_investigation

router = APIRouter(prefix="/games", tags=["games"])


@router.get("", response_model=JsonObjectList)
def list_games(season: Season | None = None,
               season_type: SeasonType = SeasonType.REGULAR,
               team: TeamAbbreviation | None = None,
               limit: int = Query(default=100, ge=1, le=1500)):
    return game_investigation.list_games(season or current_season(),
                                         str(season_type), team, limit)


@router.get("/{game_id}/investigate", response_model=JsonObject)
def investigate(game_id: GameId):
    try:
        return game_investigation.investigate(game_id)
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err
