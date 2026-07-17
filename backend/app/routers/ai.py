from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..ai import orchestrator

router = APIRouter(prefix="/api/ai", tags=["ai"])


class AskRequest(BaseModel):
    question: str
    mode: str = "auto"  # auto | player | claim | compare | game
    context: dict | None = None


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
