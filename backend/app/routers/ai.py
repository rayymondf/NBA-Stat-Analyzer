import json
import re
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from ..ai import orchestrator
from ..exceptions import UpstreamServiceError
from ..nba.seasons import current_season
from ..schemas import JsonObject

router = APIRouter(prefix="/ai", tags=["ai"])
_SEASON_RE = re.compile(r"^(\d{4})-(\d{2})$")
_SEASON_TYPES = {"Pre Season", "Regular Season", "Playoffs"}


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    mode: Literal["auto", "player", "claim", "compare", "game"] = "auto"
    context: dict[str, object] | None = None

    @field_validator("context")
    @classmethod
    def context_must_be_small(cls, value: dict[str, object] | None) -> dict[str, object] | None:
        if value is not None and len(json.dumps(value, default=str)) > 2000:
            raise ValueError("context is too large")
        if value is None:
            return value
        player_id = value.get("player_id")
        if player_id is not None and (
            isinstance(player_id, bool) or not isinstance(player_id, int)
            or not 1 <= player_id <= 9_999_999_999
        ):
            raise ValueError("context.player_id must be a positive integer")
        season = value.get("season")
        if season is not None:
            if not isinstance(season, str) or not (match := _SEASON_RE.fullmatch(season)):
                raise ValueError("context.season must use YYYY-YY format")
            start_year = int(match.group(1))
            if int(match.group(2)) != (start_year + 1) % 100:
                raise ValueError("context.season end year must follow its start year")
            if start_year > int(current_season()[:4]):
                raise ValueError("context.season cannot be in the future")
        season_type = value.get("season_type")
        if season_type is not None and season_type not in _SEASON_TYPES:
            raise ValueError(f"context.season_type must be one of {sorted(_SEASON_TYPES)}")
        return value


@router.post("/ask", response_model=JsonObject)
def ask(req: AskRequest):
    try:
        return orchestrator.ask(req.question, req.mode, req.context)
    except orchestrator.AiRateLimited as err:
        raise HTTPException(status_code=429, detail=str(err)) from err
    except orchestrator.AiUnavailable as err:
        raise HTTPException(status_code=503, detail=str(err)) from err
    except Exception as err:
        raise UpstreamServiceError("Google Gemini", "AI report generation failed.") from err
