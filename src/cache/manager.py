import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from src.cache.models import CacheStatus


class CacheManager:
    def __init__(self, db_path: Path | str, ttl: int = 86400):
        self.db_path = Path(db_path)
        self.ttl = ttl
        self._init_db()

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    task_id INTEGER PRIMARY KEY,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_expires_at ON cache(expires_at)
            """)
            conn.commit()

    def get_task(self, task_id: int) -> dict[str, Any] | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM cache WHERE task_id = ?",
                (task_id,),
            )
            row = cursor.fetchone()

            if row is None:
                return None

            expires_at = datetime.fromisoformat(row["expires_at"])
            if datetime.now() > expires_at:
                return None

            return json.loads(row["data"])

    def save_task(self, task_id: int, data: dict[str, Any]) -> None:
        now = datetime.now()
        expires_at = now + timedelta(seconds=self.ttl)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO cache (task_id, data, created_at, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    task_id,
                    json.dumps(data, ensure_ascii=False),
                    now.isoformat(),
                    expires_at.isoformat(),
                ),
            )
            conn.commit()

    def invalidate(self, task_id: int | None = None) -> None:
        with sqlite3.connect(self.db_path) as conn:
            if task_id is not None:
                conn.execute("DELETE FROM cache WHERE task_id = ?", (task_id,))
            else:
                conn.execute("DELETE FROM cache")
            conn.commit()

    def invalidate_all(self) -> None:
        self.invalidate(None)

    def get_status(self, task_id: int) -> CacheStatus:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT expires_at FROM cache WHERE task_id = ?",
                (task_id,),
            )
            row = cursor.fetchone()

            if row is None:
                return CacheStatus.NOT_EXISTS

            expires_at = datetime.fromisoformat(row["expires_at"])
            if datetime.now() > expires_at:
                return CacheStatus.EXPIRED

            return CacheStatus.VALID

    def get_index(self) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT task_id, created_at, expires_at FROM cache"
            )
            rows = cursor.fetchall()

            return [
                {
                    "task_id": row["task_id"],
                    "created_at": row["created_at"],
                    "expires_at": row["expires_at"],
                }
                for row in rows
            ]

    def get_stats(self) -> dict[str, Any]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM cache")
            total = cursor.fetchone()[0]

            now = datetime.now().isoformat()
            cursor = conn.execute(
                "SELECT COUNT(*) FROM cache WHERE expires_at > ?",
                (now,),
            )
            valid = cursor.fetchone()[0]

            return {
                "total_entries": total,
                "valid_entries": valid,
                "expired_entries": total - valid,
            }

    def cleanup_expired(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            now = datetime.now().isoformat()
            cursor = conn.execute(
                "DELETE FROM cache WHERE expires_at < ?",
                (now,),
            )
            conn.commit()
            return cursor.rowcount
