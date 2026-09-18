from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from .config import get_settings  # noqa: E402
from .exceptions import UpstreamServiceError  # noqa: E402
from .observability import (  # noqa: E402
    MODEL_INFO,
    ObservabilityMiddleware,
    configure_logging,
    problem,
    request_id_context,
)
from .routers import ai, games, health, league, ml, players  # noqa: E402
from .schemas import ProblemDetails  # noqa: E402
from .services import ml as ml_service  # noqa: E402

settings = get_settings()
configure_logging(settings.log_level)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    bundle = ml_service.load_model()
    if bundle:
        ml_service.warm_model(bundle)
        meta = bundle.get("meta", {})
        MODEL_INFO.labels(
            version=str(meta.get("model_version", "unknown")),
            dataset_version=str(meta.get("dataset_version", "legacy")),
        ).set(1)
    elif settings.require_model:
        log.error("Required xFG model could not be loaded")
        raise RuntimeError("Required xFG model could not be loaded")
    yield


app = FastAPI(
    title="NBA Stat Analyzer API",
    version="1.0.0",
    description="Typed analytics and shot-quality model API.",
    docs_url="/docs" if settings.expose_docs else None,
    redoc_url="/redoc" if settings.expose_docs else None,
    lifespan=lifespan,
    responses={
        404: {"model": ProblemDetails},
        413: {"model": ProblemDetails},
        422: {"model": ProblemDetails},
        429: {"model": ProblemDetails},
        500: {"model": ProblemDetails},
        502: {"model": ProblemDetails},
        503: {"model": ProblemDetails},
    },
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.trusted_hosts))
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID", "X-API-Version", "X-Data-Cache", "Warning"],
)
app.add_middleware(ObservabilityMiddleware, settings=settings)


def _api_router(prefix: str, *, include_in_schema: bool) -> APIRouter:
    router = APIRouter(prefix=prefix)
    for child in (players.router, games.router, league.router, ml.router, ai.router):
        router.include_router(child, include_in_schema=include_in_schema)
    return router


app.include_router(_api_router("/api/v1", include_in_schema=True))
# One-release compatibility layer for existing bookmarks and older frontend builds.
app.include_router(_api_router("/api", include_in_schema=False))
app.include_router(health.router)


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    request_id = request_id_context.get()
    details = "; ".join(
        f"{'.'.join(str(p) for p in item['loc'])}: {item['msg']}" for item in exc.errors()
    )
    return JSONResponse(
        problem(422, "Validation Error", details, request_id,
                problem_type="urn:nba-stat-analyzer:validation"),
        status_code=422,
        media_type="application/problem+json",
    )


@app.exception_handler(StarletteHTTPException)
async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, str) else "Request could not be completed."
    return JSONResponse(
        problem(exc.status_code, "Request Error", detail, request_id_context.get(),
                retryable=exc.status_code in {429, 502, 503, 504}),
        status_code=exc.status_code,
        headers=exc.headers,
        media_type="application/problem+json",
    )


@app.exception_handler(UpstreamServiceError)
async def upstream_error(_: Request, exc: UpstreamServiceError) -> JSONResponse:
    log.warning("upstream service=%s error=%s", exc.service, exc)
    return JSONResponse(
        problem(502, "Upstream Service Unavailable",
                f"{exc.service} could not complete the request.", request_id_context.get(),
                problem_type="urn:nba-stat-analyzer:upstream", retryable=exc.retryable),
        status_code=502,
        media_type="application/problem+json",
    )


@app.exception_handler(Exception)
async def unexpected_error(_: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled request error", exc_info=exc)
    return JSONResponse(
        problem(500, "Internal Server Error", "An unexpected error occurred.",
                request_id_context.get(), retryable=False),
        status_code=500,
        media_type="application/problem+json",
    )


DIST = (Path(__file__).resolve().parents[2] / "frontend" / "dist").resolve()
if DIST.is_dir():
    assets = DIST / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API route not found")
        candidate = (DIST / path).resolve()
        try:
            candidate.relative_to(DIST)
        except ValueError:
            raise HTTPException(status_code=404, detail="File not found") from None
        if path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(DIST / "index.html")
