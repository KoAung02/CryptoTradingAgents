import sqlite3
import json
import time
import hashlib
from pathlib import Path


class SQLiteCache:
    def __init__(self, db_path: str = "./crypto_cache.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    expires_at REAL NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_expires ON cache(expires_at)")

    def _make_key(self, namespace: str, **kwargs) -> str:
        raw = namespace + json.dumps(kwargs, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, namespace: str, **kwargs):
        key = self._make_key(namespace, **kwargs)
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT value FROM cache WHERE key=? AND expires_at>?",
                (key, time.time())
            ).fetchone()
        if row:
            return json.loads(row[0])
        return None

    def set(self, value, ttl_seconds: int, namespace: str, **kwargs):
        key = self._make_key(namespace, **kwargs)
        expires_at = time.time() + ttl_seconds
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache(key, value, expires_at) VALUES(?,?,?)",
                (key, json.dumps(value), expires_at)
            )

    def evict_expired(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM cache WHERE expires_at<?", (time.time(),))


_cache_instance = None


def get_cache(db_path: str = "./crypto_cache.db") -> SQLiteCache:
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = SQLiteCache(db_path)
    return _cache_instance
