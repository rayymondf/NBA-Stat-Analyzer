from fastapi import APIRouter, HTTPException

from ..nba.seasons import current_season
from ..services import game_investigation

router = APIRouter(prefix="/api/games", tags=["games"])


@router.get("")
def list_games(season: str | None = None,
               season_type: str = "Regular Season",
               team: str | None = None, limit: int = 100):
    return game_investigation.list_games(season or current_season(),
                                         season_type, team, limit)


@router.get("/{game_id}/investigate")
def investigate(game_id: str):
    try:
        return game_investigation.investigate(game_id)
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except RuntimeError as err:
        raise HTTPException(status_code=502, detail=str(err))
