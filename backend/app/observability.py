"""Structured logging, request correlation, metrics, and local rate limiting."""
from __future__ import annotations

import json
import logging
import re
import time
import uuid
from collections import defaultdict, deque
from contextvars import ContextVar
from datetime import UTC, datetime
from threading import Lock

from fastapi import Request
from prometheus_client import Counter, Gauge, Histogram
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from .config import Settings

request_id_context: ContextVar[str] = ContextVar("request_id", default="-")
cache_status_context: ContextVar[list[str] | None] = ContextVar(
    "cache_status", default=None
)

HTTP_REQUESTS = Counter(
    "nba_http_requests_total", "HTTP requests", ("method", "route", "status")
)
HTTP_LATENCY = Histogram(
    "nba_http_request_duration_seconds", "HTTP request duration", ("method", "route")
)
RATE_LIMITED = Counter("nba_rate_limited_total", "Rate-limited requests", ("bucket",))
CACHE_EVENTS = Counter("nba_cache_events_total", "Cache outcomes", ("outcome",))
UPSTREAM_CALLS = Counter(
    "nba_upstream_calls_total", "Upstream request outcomes", ("endpoint", "outcome")
)
UPSTREAM_CIRCUIT = Gauge("nba_upstream_circuit_open", "Whether the NBA upstream circuit is open")
MODEL_INFO = Gauge("nba_model_info", "Loaded model identity", ("version", "dataset_version"))


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_context.get(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())


def problem(status: int, title: str, detail: str, request_id: str, *,
            problem_type: str = "about:blank", retryable: bool = False) -> dict:
    return {
        "type": problem_type,
        "title": title,
        "status": status,
        "detail": detail,
        "request_id": request_id,
        "retryable": retryable,
    }


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._events: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = Lock()
        self._calls = 0

    def allow(self, client: str, bucket: str, limit: int, now: float) -> bool:
        key = (client, bucket)
        cutoff = now - 60
        with self._lock:
            self._calls += 1
            if self._calls % 1_000 == 0:
                empty = [item for item, values in self._events.items()
                         if not values or values[-1] <= cutoff]
                for item in empty:
                    self._events.pop(item, None)
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                return False
            events.append(now)
            return True


_limiter = SlidingWindowLimiter()
_cache_status_lock = Lock()
_cache_status_priority = {"none": 0, "miss": 1, "hit": 2, "refreshed": 3, "stale": 4}


def record_cache_status(status: str) -> None:
    """Aggregate cache freshness across sync endpoint worker threads."""
    holder = cache_status_context.get()
    if holder is None:
        return
    with _cache_status_lock:
        current = holder[0]
        if _cache_status_priority.get(status, 0) > _cache_status_priority[current]:
            holder[0] = status


def _rate_bucket(path: str, settings: Settings) -> tuple[str, int]:
    if path.endswith("/ai/ask"):
        return "ai", settings.ai_rate_limit_per_minute
    expensive = (
        "/investigate" in path
        or path.endswith(("/dataset.csv", "/fouls", "/shooting", "/shot-quality", "/compare"))
        or "/league/similar/" in path
    )
    if expensive:
        return "expensive", settings.expensive_rate_limit_per_minute
    return "api", settings.api_rate_limit_per_minute


class ObservabilityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: Settings):
        super().__init__(app)
        self.settings = settings
        self.log = logging.getLogger("nba.http")

    async def _body_exceeds_limit(self, request: Request) -> bool:
        """Buffer a small request body while enforcing the cap on actual bytes.

        Setting ``_body`` lets Starlette's cached request replay the verified
        bytes to the downstream application. This also covers chunked bodies
        and false Content-Length headers.
        """
        if (
            request.method in {"GET", "HEAD", "OPTIONS"}
            and "content-length" not in request.headers
            and "transfer-encoding" not in request.headers
        ):
            return False
        chunks: list[bytes] = []
        total = 0
        async for chunk in request.stream():
            total += len(chunk)
            if total > self.settings.max_request_body_bytes:
                return True
            chunks.append(chunk)
        request._body = b"".join(chunks)
        return False

    @staticmethod
    def _body_rejection(request_id: str) -> JSONResponse:
        return JSONResponse(
            problem(
                413,
                "Content Too Large",
                "Request body exceeds the configured limit.",
                request_id,
            ),
            status_code=413,
            media_type="application/problem+json",
        )

    async def dispatch(self, request: Request, call_next) -> Response:
        supplied_request_id = request.headers.get("x-request-id", "")
        request_id = (
            supplied_request_id
            if re.fullmatch(r"[A-Za-z0-9._-]{1,64}", supplied_request_id)
            else str(uuid.uuid4())
        )
        token = request_id_context.set(request_id)
        cache_token = cache_status_context.set(["none"])
        started = time.perf_counter()
        path = request.url.path
        route_label = path
        try:
            content_length = request.headers.get("content-length")
            if content_length:
                try:
                    body_too_large = int(content_length) > self.settings.max_request_body_bytes
                except ValueError:
                    body_too_large = True
            else:
                body_too_large = False
            if body_too_large:
                route_label = "__body_rejected__"
                response = self._body_rejection(request_id)
            elif path.startswith("/api/") or path == "/metrics":
                bucket, limit = _rate_bucket(path, self.settings)
                if path == "/metrics":
                    bucket, limit = "metrics", 60
                client = request.client.host if request.client else "unknown"
                if not _limiter.allow(client, bucket, limit, time.monotonic()):
                    route_label = f"__rate_limited_{bucket}__"
                    RATE_LIMITED.labels(bucket=bucket).inc()
                    response = JSONResponse(
                        problem(429, "Too Many Requests", "Rate limit exceeded.", request_id,
                                problem_type="urn:nba-stat-analyzer:rate-limit", retryable=True),
                        status_code=429,
                        media_type="application/problem+json",
                        headers={"Retry-After": "60"},
                    )
                elif await self._body_exceeds_limit(request):
                    route_label = "__body_rejected__"
                    response = self._body_rejection(request_id)
                else:
                    response = await call_next(request)
            else:
                if await self._body_exceeds_limit(request):
                    route_label = "__body_rejected__"
                    response = self._body_rejection(request_id)
                else:
                    response = await call_next(request)
            route = request.scope.get("route")
            resolved_route = getattr(route, "path", None)
            if resolved_route:
                route_label = resolved_route
            elif route_label == path:
                route_label = "__unmatched_api__" if path.startswith("/api/") else "__unmatched__"
            return response
        finally:
            elapsed = time.perf_counter() - started
            status = getattr(locals().get("response"), "status_code", 500)
            HTTP_REQUESTS.labels(request.method, route_label, str(status)).inc()
            HTTP_LATENCY.labels(request.method, route_label).observe(elapsed)
            if "response" in locals():
                holder = cache_status_context.get()
                cache_status = holder[0] if holder else "none"
                response.headers["X-Request-ID"] = request_id
                response.headers["X-Data-Cache"] = cache_status
                if path.startswith("/api/"):
                    response.headers["X-API-Version"] = "v1"
                if cache_status == "stale":
                    response.headers["Warning"] = '110 - "Response is stale"'
                response.headers["X-Content-Type-Options"] = "nosniff"
                response.headers["X-Frame-Options"] = "DENY"
                response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
                response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
                if path.startswith("/assets/"):
                    response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
                elif not path.startswith(("/api/", "/health/", "/metrics")):
                    response.headers["Cache-Control"] = "no-cache"
            self.log.info("request method=%s route=%s status=%s duration_ms=%.1f",
                          request.method, route_label, status, elapsed * 1000)
            request_id_context.reset(token)
            cache_status_context.reset(cache_token)
