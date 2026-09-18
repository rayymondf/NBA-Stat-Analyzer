from __future__ import annotations

from fastapi import APIRouter, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from ..config import get_settings
from ..nba import cache
from ..services import ml

router = APIRouter(tags=["operations"])


@router.get("/health/live", include_in_schema=False)
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready", include_in_schema=False)
def ready(response: Response) -> dict:
    settings = get_settings()
    model = ml.model_status()
    checks = {
        "cache": cache.healthcheck(),
        "model": bool(model["available"]),
        "model_error": model["error"],
    }
    okay = checks["cache"] and (checks["model"] or not settings.require_model)
    if not okay:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ready" if okay else "not_ready", "checks": checks}


@router.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
