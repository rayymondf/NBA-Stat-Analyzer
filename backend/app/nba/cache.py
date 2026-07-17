"""SQLite cache for NBA API responses.

Completed-season data never changes, so it is cached permanently (ttl=None).
Current-season data uses a 12h TTL so fresh games appear within half a day.
"""
import json
import os
import sqlite3
import threading
import time

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
DB_PATH = os.path.abspath(os.path.join(DATA_DIR, "cache.sqlite"))

CURRENT_SEASON_TTL = 12 * 3600

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        os.makedirs(DATA_DIR, exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
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


def get(key: str):
    with _lock:
        conn = _get_conn()
        row = conn.execute(
            "SELECT payload, created_at, ttl FROM cache WHERE key = ?", (key,)
        ).fetchone()
    if row is None:
        return None
    payload, created_at, ttl = row
    if ttl is not None and time.time() - created_at > ttl:
        with _lock:
            conn.execute("DELETE FROM cache WHERE key = ?", (key,))
            conn.commit()
        return None
    return json.loads(payload)


def set(key: str, value, ttl: float | None) -> None:
    payload = json.dumps(value)
    with _lock:
        conn = _get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO cache (key, payload, created_at, ttl) VALUES (?, ?, ?, ?)",
            (key, payload, time.time(), ttl),
        )
        conn.commit()
