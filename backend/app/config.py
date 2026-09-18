"""Environment-backed application configuration.

The object is intentionally dependency-light so command-line data jobs and the
API use the exact same paths and deployment settings.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path


def _flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _csv(name: str, default: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in os.getenv(name, default).split(",") if part.strip())


@dataclass(frozen=True, slots=True)
class Settings:
    environment: str = field(default_factory=lambda: os.getenv("APP_ENV", "development"))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    cors_origins: tuple[str, ...] = field(default_factory=lambda: _csv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ))
    trusted_hosts: tuple[str, ...] = field(default_factory=lambda: _csv(
        "TRUSTED_HOSTS", "localhost,127.0.0.1,testserver"
    ))
    require_model: bool = field(default_factory=lambda: _flag("REQUIRE_MODEL", False))
    expose_docs: bool = field(default_factory=lambda: _flag("EXPOSE_API_DOCS", True))
    cache_max_mb: int = field(default_factory=lambda: int(os.getenv("CACHE_MAX_MB", "768")))
    cache_memory_max_mb: int = field(
        default_factory=lambda: int(os.getenv("CACHE_MEMORY_MAX_MB", "64"))
    )
    cache_stale_seconds: int = field(
        default_factory=lambda: int(os.getenv("CACHE_STALE_SECONDS", str(7 * 24 * 3600)))
    )
    api_rate_limit_per_minute: int = field(
        default_factory=lambda: int(os.getenv("API_RATE_LIMIT_PER_MINUTE", "240"))
    )
    expensive_rate_limit_per_minute: int = field(
        default_factory=lambda: int(os.getenv("EXPENSIVE_RATE_LIMIT_PER_MINUTE", "30"))
    )
    ai_rate_limit_per_minute: int = field(
        default_factory=lambda: int(os.getenv("AI_RATE_LIMIT_PER_MINUTE", "6"))
    )
    max_request_body_bytes: int = field(
        default_factory=lambda: int(os.getenv("MAX_REQUEST_BODY_BYTES", "32768"))
    )
    nba_upstream_max_concurrency: int = field(
        default_factory=lambda: int(os.getenv("NBA_UPSTREAM_MAX_CONCURRENCY", "4"))
    )
    nba_upstream_queue_timeout_seconds: float = field(
        default_factory=lambda: float(os.getenv("NBA_UPSTREAM_QUEUE_TIMEOUT_SECONDS", "2"))
    )
    data_dir: Path = field(default_factory=lambda: Path(
        os.getenv("NBA_DATA_DIR", Path(__file__).resolve().parents[1] / "data")
    ).resolve())
    artifact_base_url: str | None = field(default_factory=lambda: os.getenv("ARTIFACT_BASE_URL"))
    artifact_expected_sha256: str | None = field(
        default_factory=lambda: os.getenv("ARTIFACT_EXPECTED_SHA256")
    )
    dataset_public_url: str | None = field(
        default_factory=lambda: os.getenv("DATASET_PUBLIC_URL")
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
