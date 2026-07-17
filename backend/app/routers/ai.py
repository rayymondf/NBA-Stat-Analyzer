import json
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from ..ai import orchestrator

router = APIRouter(prefix="/api/ai", tags=["ai"])


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    mode: Literal["auto", "player", "claim", "compare", "game"] = "auto"
    context: dict | None = None

    @field_validator("context")
    @classmethod
    def context_must_be_small(cls, value: dict | None) -> dict | None:
        if value is not None and len(json.dumps(value, default=str)) > 2000:
            raise ValueError("context is too large")
        return value


@router.post("/ask")
def ask(req: AskRequest):
    try:
        return orchestrator.ask(req.question, req.mode, req.context)
    except orchestrator.AiRateLimited as err:
        raise HTTPException(status_code=429, detail=str(err))
    except orchestrator.AiUnavailable as err:
        raise HTTPException(status_code=503, detail=str(err))
    except Exception as err:  # surface real cause to the UI
        raise HTTPException(status_code=502, detail=f"AI request failed: {err}")
