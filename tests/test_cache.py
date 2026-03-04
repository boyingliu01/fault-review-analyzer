import time
from datetime import datetime

import pytest

from src.cache.manager import CacheManager
from src.cache.models import CacheEntry, CacheStatus


class TestCacheManager:
    @pytest.fixture
    def cache_manager(self, temp_dir):
        db_path = temp_dir / "cache.db"
        return CacheManager(db_path=db_path, ttl=60)

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

    def test_cache_ttl(self, cache_manager):
        cache_manager = CacheManager(db_path=cache_manager.db_path, ttl=1)

        task_data = {"task_id": 12345, "title": "Test"}
        cache_manager.save_task(12345, task_data)

        assert cache_manager.get_task(12345) is not None

        time.sleep(2)

        assert cache_manager.get_task(12345) is None

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
        cache_manager = CacheManager(db_path=db_path, ttl=1)

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
