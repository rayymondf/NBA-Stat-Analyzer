"""SQLite cache for NBA API responses.

Completed-season data never changes, so it is cached permanently (ttl=None).
Current-season data uses a 12h TTL so fresh games appear within half a day.
"""
import json
import os
import sqlite3
import threading
import time
from collections import OrderedDict
from pathlib import Path

from ..config import get_settings
from ..observability import CACHE_EVENTS, record_cache_status

DATA_DIR = str(get_settings().data_dir)
DB_PATH = str(Path(DATA_DIR) / "cache.sqlite")

CURRENT_SEASON_TTL = 12 * 3600
PIPELINE_SHOT_PATTERN = "ShotChartDetail:%player_id=0&%"

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None
_writes_since_prune = 0
_memory_cache: OrderedDict[str, tuple[object, float, float | None, int]] = OrderedDict()
_memory_bytes = 0


def _remember_locked(
    key: str, value: object, created_at: float, ttl: float | None, size: int
) -> None:
    global _memory_bytes
    previous = _memory_cache.pop(key, None)
    if previous:
        _memory_bytes -= previous[3]
    _memory_cache[key] = (value, created_at, ttl, size)
    _memory_bytes += size
    maximum = get_settings().cache_memory_max_mb * 1024 * 1024
    while _memory_bytes > maximum and _memory_cache:
        _, evicted = _memory_cache.popitem(last=False)
        _memory_bytes -= evicted[3]


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        os.makedirs(DATA_DIR, exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA synchronous=NORMAL")
        _conn.execute("PRAGMA busy_timeout=5000")
        _conn.execute(
            """CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                created_at REAL NOT NULL,
                ttl REAL
            )"""
        )
        _conn.commit()
    return _conn


def get_with_status(key: str, *, allow_stale: bool = False,
                    max_stale_seconds: float | None = None) -> tuple[object | None, str]:
    """Return a cached object and one of ``hit``, ``stale``, or ``miss``.

    Expired values remain available for a bounded stale-if-error fallback. They
    are removed later by pruning rather than at the moment an upstream service
    happens to fail.
    """
    with _lock:
        conn = _get_conn()
        memory = _memory_cache.get(key)
        if memory:
            _memory_cache.move_to_end(key)
            value, created_at, ttl, _ = memory
            row = None
        else:
            row = conn.execute(
                "SELECT payload, created_at, ttl FROM cache WHERE key = ?", (key,)
            ).fetchone()
            value = None
    if memory:
        payload = None
    elif row is not None:
        payload, created_at, ttl = row
        value = json.loads(payload)
        with _lock:
            _remember_locked(key, value, created_at, ttl, len(payload))
    if row is None and not memory:
        CACHE_EVENTS.labels(outcome="miss").inc()
        record_cache_status("miss")
        return None, "miss"
    assert created_at is not None
    age = time.time() - created_at
    if ttl is not None and age > ttl:
        stale_limit = (max_stale_seconds if max_stale_seconds is not None
                       else get_settings().cache_stale_seconds)
        if not allow_stale or age > ttl + stale_limit:
            CACHE_EVENTS.labels(outcome="miss").inc()
            record_cache_status("miss")
            return None, "miss"
        CACHE_EVENTS.labels(outcome="stale").inc()
        record_cache_status("stale")
        return value, "stale"
    CACHE_EVENTS.labels(outcome="hit").inc()
    record_cache_status("hit")
    return value, "hit"


def get(key: str, *, allow_stale: bool = False):
    value, _ = get_with_status(key, allow_stale=allow_stale)
    return value


def set(key: str, value, ttl: float | None) -> None:
    global _writes_since_prune
    payload = json.dumps(value)
    with _lock:
        conn = _get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO cache (key, payload, created_at, ttl) VALUES (?, ?, ?, ?)",
            (key, payload, time.time(), ttl),
        )
        conn.commit()
        _remember_locked(key, value, time.time(), ttl, len(payload))
        _writes_since_prune += 1
        if _writes_since_prune >= 100:
            _prune_locked(conn, get_settings().cache_max_mb)
            _writes_since_prune = 0
    record_cache_status("refreshed")


def _prune_locked(conn: sqlite3.Connection, max_mb: int) -> int:
    """Bound logical payload size and discard unusably old stale entries."""
    global _memory_bytes
    max_bytes = max_mb * 1024 * 1024
    total = int(conn.execute("SELECT COALESCE(SUM(length(payload)), 0) FROM cache").fetchone()[0])
    removed = 0
    stale_cutoff = time.time() - get_settings().cache_stale_seconds
    cursor = conn.execute(
        "DELETE FROM cache WHERE ttl IS NOT NULL AND created_at + ttl < ?", (stale_cutoff,)
    )
    removed += max(cursor.rowcount, 0)
    total = int(conn.execute("SELECT COALESCE(SUM(length(payload)), 0) FROM cache").fetchone()[0])
    while total > max_bytes:
        rows = conn.execute(
            "SELECT key, length(payload) FROM cache ORDER BY created_at ASC LIMIT 100"
        ).fetchall()
        if not rows:
            break
        conn.executemany("DELETE FROM cache WHERE key = ?", [(row[0],) for row in rows])
        removed += len(rows)
        total -= sum(int(row[1]) for row in rows)
    conn.commit()
    if removed:
        _memory_cache.clear()
        _memory_bytes = 0
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        CACHE_EVENTS.labels(outcome="pruned").inc(removed)
    return removed


def prune(max_mb: int | None = None) -> int:
    with _lock:
        return _prune_locked(_get_conn(), max_mb or get_settings().cache_max_mb)


def pipeline_payload_stats() -> dict[str, int]:
    """Size of obsolete team-season payloads superseded by raw Parquet partitions."""
    with _lock:
        count, payload_bytes = _get_conn().execute(
            "SELECT COUNT(*), COALESCE(SUM(length(payload)), 0) FROM cache WHERE key LIKE ?",
            (PIPELINE_SHOT_PATTERN,),
        ).fetchone()
    return {"entries": int(count), "payload_bytes": int(payload_bytes)}


def prune_pipeline_payloads(*, vacuum: bool = False) -> dict[str, int]:
    """Remove only team-level training payloads; player-facing cache entries remain."""
    global _memory_bytes
    with _lock:
        conn = _get_conn()
        before = pipeline_payload_stats_unlocked(conn)
        conn.execute("DELETE FROM cache WHERE key LIKE ?", (PIPELINE_SHOT_PATTERN,))
        conn.commit()
        for key in [key for key in _memory_cache if _pipeline_key(key)]:
            _memory_bytes -= _memory_cache.pop(key)[3]
        if vacuum and before["entries"]:
            conn.execute("VACUUM")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        if before["entries"]:
            CACHE_EVENTS.labels(outcome="pruned").inc(before["entries"])
        return before


def _pipeline_key(key: str) -> bool:
    return key.startswith("ShotChartDetail:") and "player_id=0&" in key


def pipeline_payload_stats_unlocked(conn: sqlite3.Connection) -> dict[str, int]:
    count, payload_bytes = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(length(payload)), 0) FROM cache WHERE key LIKE ?",
        (PIPELINE_SHOT_PATTERN,),
    ).fetchone()
    return {"entries": int(count), "payload_bytes": int(payload_bytes)}


def stats() -> dict[str, int]:
    with _lock:
        conn = _get_conn()
        count, payload_bytes = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(length(payload)), 0) FROM cache"
        ).fetchone()
        page_count = int(conn.execute("PRAGMA page_count").fetchone()[0])
        page_size = int(conn.execute("PRAGMA page_size").fetchone()[0])
    wal_path = Path(f"{DB_PATH}-wal")
    return {
        "entries": int(count),
        "payload_bytes": int(payload_bytes),
        "database_bytes": page_count * page_size,
        "wal_bytes": wal_path.stat().st_size if wal_path.exists() else 0,
        "memory_entries": len(_memory_cache),
        "memory_bytes": _memory_bytes,
    }


def healthcheck() -> bool:
    try:
        with _lock:
            return _get_conn().execute("SELECT 1").fetchone() == (1,)
    except sqlite3.Error:
        return False


def close() -> None:
    """Close the process connection; primarily useful for isolated tests."""
    global _conn, _memory_bytes
    with _lock:
        if _conn is not None:
            _conn.close()
            _conn = None
        _memory_cache.clear()
        _memory_bytes = 0
