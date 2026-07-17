"""Thin wrapper around nba_api endpoints: caching, retry, rate-limit spacing.

stats.nba.com is unofficial and throttles aggressive clients, so every call is
spaced ~0.65s apart, retried with backoff, and cached in SQLite (permanently
for completed seasons).
"""
import logging
import threading
import time

from . import cache
from .seasons import is_current_season

log = logging.getLogger(__name__)

REQUEST_SPACING_SECONDS = 0.65
TIMEOUT = 45
MAX_RETRIES = 3

_throttle_lock = threading.Lock()
_last_request_at = 0.0

def _throttle() -> None:
    global _last_request_at
    with _throttle_lock:
        wait = REQUEST_SPACING_SECONDS - (time.time() - _last_request_at)
        if wait > 0:
            time.sleep(wait)
        _last_request_at = time.time()


def ttl_for(params: dict) -> float | None:
    """Permanent cache unless any param references the current season."""
    for value in params.values():
        if isinstance(value, str) and is_current_season(value):
            return cache.CURRENT_SEASON_TTL
    return None


def fetch(endpoint_cls, ttl: float | None = "auto", raw: bool = False,
          **params) -> dict:
    """Call an nba_api endpoint class and return its parsed response.

    Default shape: {result_set_name: [row_dict, ...], ...} (normalized dict).
    raw=True returns the endpoint's raw JSON dict — required for V3 endpoints
    (boxscores, play-by-play), whose nested format normalizes to nothing.
    """
    key = f"{endpoint_cls.__name__}:{'raw:' if raw else ''}" + "&".join(
        f"{k}={params[k]}" for k in sorted(params)
    )
    hit = cache.get(key)
    if hit is not None:
        return hit

    if ttl == "auto":
        ttl = ttl_for(params)

    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            _throttle()
            # nba_api's bundled headers are the known-good fingerprint;
            # custom header sets get silently blackholed by stats.nba.com.
            endpoint = endpoint_cls(**params, timeout=TIMEOUT)
            data = endpoint.get_dict() if raw else endpoint.get_normalized_dict()
            cache.set(key, data, ttl)
            return data
        except Exception as err:  # noqa: BLE001 - nba_api raises broadly
            last_err = err
            backoff = 2.0 * (attempt + 1)
            log.warning(
                "NBA API call %s failed (attempt %d/%d): %s — retrying in %.0fs",
                endpoint_cls.__name__, attempt + 1, MAX_RETRIES, err, backoff,
            )
            time.sleep(backoff)
    raise RuntimeError(
        f"NBA stats request {endpoint_cls.__name__} failed after "
        f"{MAX_RETRIES} attempts: {last_err}"
    )
