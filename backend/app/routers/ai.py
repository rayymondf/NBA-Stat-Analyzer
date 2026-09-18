import json
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from ..ai import orchestrator
from ..exceptions import UpstreamServiceError
from ..schemas import JsonObject

router = APIRouter(prefix="/ai", tags=["ai"])


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    mode: Literal["auto", "player", "claim", "compare", "game"] = "auto"
    context: dict[str, object] | None = None

    @field_validator("context")
    @classmethod
    def context_must_be_small(cls, value: dict[str, object] | None) -> dict[str, object] | None:
        if value is not None and len(json.dumps(value, default=str)) > 2000:
            raise ValueError("context is too large")
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
