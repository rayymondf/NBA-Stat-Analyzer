"""NBA endpoint wrapper with cache, retries, single-flight, and circuit breaking."""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager

import requests

from ..config import get_settings
from ..exceptions import UpstreamServiceError
from ..observability import UPSTREAM_CALLS, UPSTREAM_CIRCUIT
from . import cache
from .seasons import is_current_season

log = logging.getLogger(__name__)

REQUEST_SPACING_SECONDS = 0.65
TIMEOUT = 15
MAX_RETRIES = 2
CIRCUIT_FAILURE_THRESHOLD = 5
CIRCUIT_COOLDOWN_SECONDS = 60.0

_throttle_lock = threading.Lock()
_last_request_at = 0.0
_key_locks_guard = threading.Lock()
_key_locks: dict[str, tuple[threading.Lock, int]] = {}
_circuit_lock = threading.Lock()
_consecutive_failures = 0
_circuit_open_until = 0.0
_half_open_inflight = False
_upstream_slots = threading.BoundedSemaphore(
    max(1, get_settings().nba_upstream_max_concurrency)
)


@contextmanager
def _key_lock(key: str) -> Iterator[None]:
    with _key_locks_guard:
        lock, users = _key_locks.get(key, (threading.Lock(), 0))
        _key_locks[key] = (lock, users + 1)
    lock.acquire()
    try:
        yield
    finally:
        lock.release()
        with _key_locks_guard:
            current_lock, users = _key_locks.get(key, (lock, 1))
            if current_lock is lock and users <= 1:
                _key_locks.pop(key, None)
            elif current_lock is lock:
                _key_locks[key] = (lock, users - 1)


def _upstream_allowed() -> bool:
    """Allow normal traffic or exactly one probe after circuit cooldown."""
    global _half_open_inflight
    with _circuit_lock:
        if _circuit_open_until == 0:
            return True
        if time.monotonic() < _circuit_open_until or _half_open_inflight:
            UPSTREAM_CIRCUIT.set(1)
            return False
        _half_open_inflight = True
        return True


def _record_success() -> None:
    global _consecutive_failures, _circuit_open_until, _half_open_inflight
    with _circuit_lock:
        _consecutive_failures = 0
        _circuit_open_until = 0.0
        _half_open_inflight = False
    UPSTREAM_CIRCUIT.set(0)


def _record_failure() -> None:
    global _consecutive_failures, _circuit_open_until, _half_open_inflight
    with _circuit_lock:
        _consecutive_failures += 1
        if _consecutive_failures >= CIRCUIT_FAILURE_THRESHOLD:
            _circuit_open_until = time.monotonic() + CIRCUIT_COOLDOWN_SECONDS
            UPSTREAM_CIRCUIT.set(1)
        _half_open_inflight = False


def _cancel_half_open_probe() -> None:
    global _half_open_inflight
    with _circuit_lock:
        if _circuit_open_until:
            _half_open_inflight = False


def _throttle() -> None:
    global _last_request_at
    with _throttle_lock:
        wait = REQUEST_SPACING_SECONDS - (time.monotonic() - _last_request_at)
        if wait > 0:
            time.sleep(wait)
        _last_request_at = time.monotonic()


def ttl_for(params: dict) -> float | None:
    """Use a bounded lifetime when any parameter references the live season."""
    for value in params.values():
        if isinstance(value, str) and is_current_season(value):
            return cache.CURRENT_SEASON_TTL
    return None


def fetch(
    endpoint_cls,
    ttl: float | None | str = "auto",
    raw: bool = False,
    persist_cache: bool = True,
    **params,
) -> dict:
    """Call an nba_api endpoint and return normalized or raw JSON data.

    Concurrent identical misses share one upstream call. When NBA.com fails,
    an expired value may be served within the configured stale window.
    """
    endpoint_name = endpoint_cls.__name__
    key = f"{endpoint_name}:{'raw:' if raw else ''}" + "&".join(
        f"{key}={params[key]}" for key in sorted(params)
    )
    if persist_cache:
        hit = cache.get(key)
        if hit is not None:
            return hit

    effective_ttl = ttl_for(params) if ttl == "auto" else ttl
    with _key_lock(key):
        if persist_cache:
            hit = cache.get(key)
            if hit is not None:
                return hit
        if not _upstream_allowed():
            stale = cache.get(key, allow_stale=True) if persist_cache else None
            if stale is not None:
                UPSTREAM_CALLS.labels(endpoint=endpoint_name, outcome="stale").inc()
                return stale
            raise UpstreamServiceError(
                "NBA.com", "The upstream circuit is open and no cached response is available."
            )
        if not _upstream_slots.acquire(
            timeout=max(0.0, get_settings().nba_upstream_queue_timeout_seconds)
        ):
            _cancel_half_open_probe()
            stale = cache.get(key, allow_stale=True) if persist_cache else None
            if stale is not None:
                UPSTREAM_CALLS.labels(endpoint=endpoint_name, outcome="stale").inc()
                return stale
            raise UpstreamServiceError(
                "NBA.com",
                "The upstream concurrency budget is busy and no cached response is available.",
            )
        last_err: Exception | None = None
        attempts = 0
        try:
            for attempt in range(MAX_RETRIES):
                attempts = attempt + 1
                try:
                    _throttle()
                    endpoint = endpoint_cls(**params, timeout=TIMEOUT)
                    data = endpoint.get_dict() if raw else endpoint.get_normalized_dict()
                    if persist_cache:
                        cache.set(key, data, effective_ttl)  # type: ignore[arg-type]
                    _record_success()
                    UPSTREAM_CALLS.labels(endpoint=endpoint_name, outcome="success").inc()
                    return data
                except Exception as err:  # nba_api raises several unrelated exception types
                    last_err = err
                    UPSTREAM_CALLS.labels(endpoint=endpoint_name, outcome="failure").inc()
                    transient = isinstance(
                        err,
                        (requests.RequestException, TimeoutError, ConnectionError),
                    )
                    if not transient:
                        break
                    if attempt + 1 < MAX_RETRIES:
                        backoff = float(attempt + 1)
                        log.warning(
                            "NBA API call %s failed (attempt %d/%d): %s; retrying in %.0fs",
                            endpoint_name, attempt + 1, MAX_RETRIES, err, backoff,
                        )
                        time.sleep(backoff)
        finally:
            _upstream_slots.release()

        _record_failure()
        stale = cache.get(key, allow_stale=True) if persist_cache else None
        if stale is not None:
            log.warning("Serving stale %s response after upstream failure", endpoint_name)
            UPSTREAM_CALLS.labels(endpoint=endpoint_name, outcome="stale").inc()
            return stale
        raise UpstreamServiceError(
            "NBA.com",
            f"Request {endpoint_name} failed after {attempts} attempt(s): {last_err}",
        )


def reset_runtime_state() -> None:
    """Reset circuit/throttle state for deterministic isolated tests."""
    global _last_request_at, _consecutive_failures, _circuit_open_until, _half_open_inflight
    with _throttle_lock:
        _last_request_at = 0.0
    with _circuit_lock:
        _consecutive_failures = 0
        _circuit_open_until = 0.0
        _half_open_inflight = False
    with _key_locks_guard:
        _key_locks.clear()
    UPSTREAM_CIRCUIT.set(0)
