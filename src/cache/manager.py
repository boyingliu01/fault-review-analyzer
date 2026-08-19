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
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.db_path)
        self._connection.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS cache (
                task_id INTEGER PRIMARY KEY,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
        """
        )
        self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_expires_at ON cache(expires_at)
        """
        )
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "CacheManager":
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()

    def get_task(self, task_id: int) -> dict[str, Any] | None:
        cursor = self._connection.execute(
            "SELECT * FROM cache WHERE task_id = ?",
            (task_id,),
        )
        row = cursor.fetchone()

        if row is None:
            return None

        expires_at = datetime.fromisoformat(row["expires_at"])
        if datetime.now() > expires_at:
            return None

        data = json.loads(row["data"])
        return data if isinstance(data, dict) else None

    def load_task(self, task_id: int) -> dict[str, Any] | None:
        return self.get_task(task_id)

    def save_task(self, task_id: int, data: dict[str, Any]) -> None:
        now = datetime.now()
        expires_at = now + timedelta(seconds=self.ttl)

        self._connection.execute(
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
        self._connection.commit()

    def invalidate(self, task_id: int | None = None) -> None:
        if task_id is not None:
            self._connection.execute("DELETE FROM cache WHERE task_id = ?", (task_id,))
        else:
            self._connection.execute("DELETE FROM cache")
        self._connection.commit()

    def invalidate_all(self) -> None:
        self.invalidate(None)

    def get_status(self, task_id: int) -> CacheStatus:
        cursor = self._connection.execute(
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
        cursor = self._connection.execute("SELECT task_id, created_at, expires_at FROM cache")
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
        cursor = self._connection.execute("SELECT COUNT(*) FROM cache")
        total = cursor.fetchone()[0]

        now = datetime.now().isoformat()
        cursor = self._connection.execute(
            "SELECT COUNT(*) FROM cache WHERE expires_at > ?",
            (now,),
        )
        valid = cursor.fetchone()[0]

        return {
            "total_entries": total,
            "valid_entries": valid,
            "expired_entries": total - valid,
        }

    def get_all_tasks(self) -> list[dict[str, Any]]:
        cursor = self._connection.execute("SELECT * FROM cache")
        rows = cursor.fetchall()

        result = []
        now = datetime.now()
        for row in rows:
            expires_at = datetime.fromisoformat(row["expires_at"])
            if now <= expires_at:
                data = json.loads(row["data"])
                result.append(data)

        return result

    def cleanup_expired(self) -> int:
        now = datetime.now().isoformat()
        cursor = self._connection.execute(
            "DELETE FROM cache WHERE expires_at < ?",
            (now,),
        )
        self._connection.commit()
        return cursor.rowcount
