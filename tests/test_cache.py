import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

import pytest

from src.cache.manager import CacheManager
from src.cache.models import CacheEntry, CacheStatus


class TestCacheManager:
    @pytest.fixture
    def cache_manager(self, temp_dir):
        db_path = temp_dir / "cache.db"
        cache_manager = CacheManager(db_path=db_path, ttl=60)
        yield cache_manager
        cache_manager.close()

    def test_save_and_load_cache(self, cache_manager):
        task_data = {
            "task_id": 12345,
            "title": "SQL查询导致OOM",
            "description": "生产环境执行大表查询时发生内存溢出",
            "status": "resolved",
            "priority": "high",
            "create_time": "2024-01-15T10:00:00",
        }

        cache_manager.save_task(12345, task_data)

        loaded = cache_manager.get_task(12345)

        assert loaded is not None
        assert loaded["task_id"] == 12345
        assert loaded["title"] == "SQL查询导致OOM"

    def test_shared_manager_supports_cross_thread_operations(
        self, cache_manager: CacheManager
    ) -> None:
        def save_and_load(task_id: int) -> dict[str, Any]:
            cache_manager.save_task(task_id, {"task_id": task_id})
            loaded = cache_manager.get_task(task_id)
            assert loaded is not None
            return loaded

        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(save_and_load, range(20)))

        assert {result["task_id"] for result in results} == set(range(20))

    def test_close_is_idempotent(self, cache_manager):
        cache_manager.close()

        cache_manager.close()

        with pytest.raises(sqlite3.ProgrammingError):
            cache_manager.get_task(1)

    def test_cache_ttl(self, cache_manager):
        with CacheManager(db_path=cache_manager.db_path, ttl=1) as ttl_cache_manager:
            task_data = {"task_id": 12345, "title": "Test"}
            ttl_cache_manager.save_task(12345, task_data)

            assert ttl_cache_manager.get_task(12345) is not None

            time.sleep(2)

            assert ttl_cache_manager.get_task(12345) is None

    def test_init_does_not_purge_expired_data(self, tmp_path):
        """构造 CacheManager 不得物理删除已存在的过期数据。

        背景（11955497 复盘数据事故）：__init__ 曾无条件执行
        cleanup_expired()，全量 pytest 期间实例化指向真实库的实例时，
        已过期的 194 条 task 数据被全部物理删除。修复后构造无副作用，
        过期判断由 get_task 惰性完成。
        """
        import sqlite3

        db_path = tmp_path / "cache.db"
        with CacheManager(db_path=db_path, ttl=3600) as manager:
            manager.save_task(12345, {"task_id": 12345, "title": "old"})

        # 手工把 expires_at 改为过去，模拟已过期数据
        conn = sqlite3.connect(db_path)
        conn.execute("UPDATE cache SET expires_at = ?", ("2000-01-01 00:00:00",))
        conn.commit()
        conn.close()

        # 重新构造实例：物理数据仍在（构造无删除副作用），
        # 逻辑上过期（get_task 返回 None，其惰性单条删除是预期行为）
        with CacheManager(db_path=db_path, ttl=3600) as manager2:
            conn = sqlite3.connect(db_path)
            count = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
            conn.close()
            assert count == 1, "构造 CacheManager 不得物理删除已过期数据"

            assert manager2.get_task(12345) is None

    def test_cache_invalidation(self, cache_manager):
        task_data = {"task_id": 12345, "title": "Test"}
        cache_manager.save_task(12345, task_data)

        assert cache_manager.get_task(12345) is not None

        cache_manager.invalidate(12345)

        assert cache_manager.get_task(12345) is None

    def test_cache_invalidate_all(self, cache_manager):
        cache_manager.save_task(1, {"task_id": 1, "title": "Test1"})
        cache_manager.save_task(2, {"task_id": 2, "title": "Test2"})

        cache_manager.invalidate_all()

        assert cache_manager.get_task(1) is None
        assert cache_manager.get_task(2) is None

    def test_cache_index(self, cache_manager):
        cache_manager.save_task(1, {"task_id": 1, "title": "Test1"})
        cache_manager.save_task(2, {"task_id": 2, "title": "Test2"})
        cache_manager.save_task(3, {"task_id": 3, "title": "Test3"})

        index = cache_manager.get_index()

        assert len(index) == 3
        assert any(entry["task_id"] == 1 for entry in index)

    def test_cache_status(self, cache_manager):
        task_data = {"task_id": 12345, "title": "Test"}

        assert cache_manager.get_status(12345) == CacheStatus.NOT_EXISTS

        cache_manager.save_task(12345, task_data)

        assert cache_manager.get_status(12345) == CacheStatus.VALID

    def test_cache_status_expired(self, temp_dir):
        db_path = temp_dir / "cache_expired.db"
        with CacheManager(db_path=db_path, ttl=1) as cache_manager:
            cache_manager.save_task(12345, {"task_id": 12345})
            time.sleep(2)

            assert cache_manager.get_status(12345) == CacheStatus.EXPIRED

    def test_update_existing_cache(self, cache_manager):
        cache_manager.save_task(12345, {"task_id": 12345, "title": "Old Title"})
        cache_manager.save_task(12345, {"task_id": 12345, "title": "New Title"})

        loaded = cache_manager.get_task(12345)

        assert loaded["title"] == "New Title"

    def test_cache_stats(self, cache_manager):
        cache_manager.save_task(1, {"task_id": 1})
        cache_manager.save_task(2, {"task_id": 2})

        stats = cache_manager.get_stats()

        assert stats["total_entries"] == 2
        assert stats["valid_entries"] == 2

    def test_get_all_tasks(self, cache_manager):
        cache_manager.save_task(1, {"task_id": 1, "title": "Test1"})
        cache_manager.save_task(2, {"task_id": 2, "title": "Test2"})

        all_tasks = cache_manager.get_all_tasks()

        assert len(all_tasks) == 2
        assert any(t["task_id"] == 1 for t in all_tasks)

    def test_load_task_alias(self, cache_manager):
        cache_manager.save_task(12345, {"task_id": 12345, "title": "Test"})

        loaded = cache_manager.load_task(12345)

        assert loaded is not None
        assert loaded["task_id"] == 12345

    def test_get_task_not_found(self, cache_manager):
        loaded = cache_manager.get_task(99999)
        assert loaded is None

    def test_cache_cleanup(self, temp_dir):
        db_path = temp_dir / "cache_cleanup.db"
        with CacheManager(db_path=db_path, ttl=1) as cache_manager:
            cache_manager.save_task(1, {"task_id": 1})
            cache_manager.save_task(2, {"task_id": 2})
            time.sleep(2)

            cleaned = cache_manager.cleanup_expired()

            assert cleaned == 2

    def test_cache_stats_with_expired(self, temp_dir):
        db_path = temp_dir / "cache_stats.db"
        with CacheManager(db_path=db_path, ttl=1) as cache_manager:
            cache_manager.save_task(1, {"task_id": 1})
            cache_manager.save_task(2, {"task_id": 2})
            time.sleep(2)

            stats = cache_manager.get_stats()

            assert stats["total_entries"] == 2
            assert stats["expired_entries"] == 2


class TestCacheModels:
    def test_cache_entry(self):
        entry = CacheEntry(
            task_id=12345,
            data={"title": "Test"},
            created_at=datetime.now(),
            expires_at=datetime.now(),
        )

        assert entry.task_id == 12345
        assert entry.data["title"] == "Test"

    def test_cache_status_enum(self):
        assert CacheStatus.VALID.value == "valid"
        assert CacheStatus.EXPIRED.value == "expired"
        assert CacheStatus.NOT_EXISTS.value == "not_exists"
