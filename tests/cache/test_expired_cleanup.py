import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from src.cache.manager import CacheManager
from src.cache.models import CacheStatus


def _expire_task(db_path: Path, task_id: int) -> None:
    expired_at = (datetime.now() - timedelta(hours=1)).isoformat()
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE cache SET expires_at = ? WHERE task_id = ?",
            (expired_at, task_id),
        )


def _task_count(db_path: Path) -> int:
    with sqlite3.connect(db_path) as connection:
        row = connection.execute("SELECT COUNT(*) FROM cache").fetchone()
    assert row is not None
    return int(row[0])


def test_get_task_deletes_expired_row_after_status_reports_expired(tmp_path: Path) -> None:
    db_path = tmp_path / "get_task.db"
    with CacheManager(db_path=db_path) as manager:
        manager.save_task(1, {"task_id": 1})
        _expire_task(db_path, 1)

        assert manager.get_status(1) == CacheStatus.EXPIRED

        assert manager.get_task(1) is None
        assert _task_count(db_path) == 0


def test_get_all_tasks_deletes_expired_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "get_all_tasks.db"
    with CacheManager(db_path=db_path) as manager:
        manager.save_task(1, {"task_id": 1})
        manager.save_task(2, {"task_id": 2})
        _expire_task(db_path, 1)

        assert manager.get_all_tasks() == [{"task_id": 2}]
        assert _task_count(db_path) == 1


def test_get_stats_deletes_expired_rows_after_reporting_snapshot(tmp_path: Path) -> None:
    db_path = tmp_path / "get_stats.db"
    with CacheManager(db_path=db_path) as manager:
        manager.save_task(1, {"task_id": 1})
        _expire_task(db_path, 1)

        stats = manager.get_stats()

        assert stats == {"total_entries": 1, "valid_entries": 0, "expired_entries": 1}
        assert _task_count(db_path) == 0


def test_initialization_does_not_delete_expired_rows(tmp_path: Path) -> None:
    """构造 CacheManager 不得有删除副作用；物理清理只走显式 cleanup_expired。

    回归背景：旧版 __init__ 无条件 cleanup_expired()，叠加测试未隔离
    缓存路径，曾在全量 pytest 期间物理删除真实库 data/cache/cache.db
    中全部已过期数据。
    """
    db_path = tmp_path / "initialization.db"
    with CacheManager(db_path=db_path) as manager:
        manager.save_task(1, {"task_id": 1})
    _expire_task(db_path, 1)

    with CacheManager(db_path=db_path):
        assert _task_count(db_path) == 1

    # 显式调用才会物理删除
    with CacheManager(db_path=db_path) as manager:
        assert manager.cleanup_expired() == 1
        assert _task_count(db_path) == 0
