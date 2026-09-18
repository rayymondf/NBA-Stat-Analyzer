from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.exceptions import UpstreamServiceError
from app.nba import cache, client


@pytest.fixture
def isolated_cache(tmp_path, monkeypatch):
    cache.close()
    monkeypatch.setattr(cache, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(cache, "DB_PATH", str(tmp_path / "cache.sqlite"))
    yield
    cache.close()


def test_cache_hit_expiry_and_bounded_stale(isolated_cache, monkeypatch):
    now = 1_000.0
    monkeypatch.setattr(cache.time, "time", lambda: now)
    cache.set("key", {"value": 1}, ttl=10)
    assert cache.get_with_status("key") == ({"value": 1}, "hit")

    now = 1_011.0
    assert cache.get_with_status("key") == (None, "miss")
    assert cache.get_with_status("key", allow_stale=True, max_stale_seconds=5) == (
        {"value": 1}, "stale",
    )

    now = 1_016.0
    assert cache.get_with_status("key", allow_stale=True, max_stale_seconds=5) == (None, "miss")


def test_cache_stats_health_and_prune(isolated_cache):
    for index in range(5):
        cache.set(str(index), {"payload": "x" * 1_000}, ttl=None)
    assert cache.healthcheck()
    assert cache.stats()["entries"] == 5
    removed = cache.prune(max_mb=1)
    assert removed == 0


def test_pipeline_cache_cleanup_is_narrow(isolated_cache):
    pipeline_key = (
        "ShotChartDetail:context_measure_simple=FGA&player_id=0&season_nullable=2024-25&"
        "team_id=1610612761"
    )
    cache.set(pipeline_key, {"shots": [1, 2]}, ttl=None)
    cache.set("ShotChartDetail:player_id=201939&season_nullable=2024-25", {"shots": [3]}, None)
    cache.set("PlayerGameLogs:player_id=201939", {"games": [1]}, None)

    assert cache.pipeline_payload_stats()["entries"] == 1
    removed = cache.prune_pipeline_payloads()

    assert removed["entries"] == 1
    assert cache.get(pipeline_key) is None
    assert cache.get("ShotChartDetail:player_id=201939&season_nullable=2024-25") is not None
    assert cache.get("PlayerGameLogs:player_id=201939") is not None


class SuccessfulEndpoint:
    calls = 0

    def __init__(self, **_kwargs):
        type(self).calls += 1

    def get_normalized_dict(self):
        return {"Rows": [{"ok": True}]}


class FailingEndpoint:
    def __init__(self, **_kwargs):
        raise TimeoutError("upstream timeout")


def test_client_caches_success(isolated_cache, monkeypatch):
    client.reset_runtime_state()
    SuccessfulEndpoint.calls = 0
    monkeypatch.setattr(client, "REQUEST_SPACING_SECONDS", 0)
    first = client.fetch(SuccessfulEndpoint, season="2024-25")
    second = client.fetch(SuccessfulEndpoint, season="2024-25")
    assert first == second
    assert SuccessfulEndpoint.calls == 1


def test_client_serves_stale_after_retries(isolated_cache, monkeypatch):
    client.reset_runtime_state()
    monkeypatch.setattr(client, "REQUEST_SPACING_SECONDS", 0)
    monkeypatch.setattr(client.time, "sleep", lambda _seconds: None)
    key = "FailingEndpoint:season=2025-26"
    cache.set(key, {"Rows": ["stale"]}, ttl=1)
    real_time = time.time
    monkeypatch.setattr(cache.time, "time", lambda: real_time() + 2)
    assert client.fetch(FailingEndpoint, season="2025-26") == {"Rows": ["stale"]}


def test_client_raises_safe_domain_error_without_stale(isolated_cache, monkeypatch):
    client.reset_runtime_state()
    monkeypatch.setattr(client, "REQUEST_SPACING_SECONDS", 0)
    monkeypatch.setattr(client.time, "sleep", lambda _seconds: None)
    with pytest.raises(UpstreamServiceError):
        client.fetch(FailingEndpoint, season="2024-25")


def test_single_flight_deduplicates_concurrent_miss(isolated_cache, monkeypatch):
    client.reset_runtime_state()
    SuccessfulEndpoint.calls = 0
    monkeypatch.setattr(client, "REQUEST_SPACING_SECONDS", 0)
    gate = threading.Barrier(4)

    def run():
        gate.wait()
        return client.fetch(SuccessfulEndpoint, season="2023-24")

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _index: run(), range(4)))
    assert all(result == results[0] for result in results)
    assert SuccessfulEndpoint.calls == 1
