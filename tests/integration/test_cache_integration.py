"""P0 集成测试: CacheManager 真实 SQLite 读写与 Pipeline 缓存集成。

使用 tmp_path 创建临时数据库，不 mock 任何组件。
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.api.models import CommitInfo, DevelopmentInfo, ProductionInfo, TaskInfo
from src.cache.manager import CacheManager
from src.cache.models import CacheStatus


@pytest.fixture
def cache_manager(tmp_path: Path) -> CacheManager:
    """使用临时路径创建真实的 CacheManager。"""
    db_path = tmp_path / "test_cache.db"
    return CacheManager(db_path=db_path, ttl=3600)


@pytest.fixture
def sample_task_info() -> TaskInfo:
    return TaskInfo(
        task_id=10001,
        title="缓存集成测试任务",
        description="用于测试 CacheManager 的真实读写操作",
        status="resolved",
        priority="medium",
        create_time=datetime(2024, 5, 1, 10, 0, 0),
        resolve_time=datetime(2024, 5, 1, 12, 0, 0),
        development=DevelopmentInfo(
            commits=[
                CommitInfo(
                    commit_id="cache_test_001",
                    message="添加缓存功能",
                    author="tester",
                    time=datetime(2024, 5, 1, 9, 0, 0),
                    changes=["src/cache.py"],
                )
            ]
        ),
        production=ProductionInfo(
            incident_time=datetime(2024, 5, 1, 11, 0, 0),
            symptoms="内存泄漏",
            logs=["ERROR: MemoryError"],
            stack_traces=["MemoryError at line 42"],
            resolution="修复内存泄漏",
        ),
    )


class TestCacheManagerRealSQLite:
    """测试 CacheManager 使用真实 SQLite 数据库。"""

    def test_save_and_load_task(self, cache_manager: CacheManager, sample_task_info: TaskInfo):
        """保存后应能正确读取相同数据。"""
        task_dict = sample_task_info.model_dump(mode="json")
        cache_manager.save_task(10001, task_dict)

        loaded = cache_manager.get_task(10001)
        assert loaded is not None
        assert loaded["task_id"] == 10001
        assert loaded["title"] == "缓存集成测试任务"
        assert loaded["status"] == "resolved"

    def test_load_nonexistent_returns_none(self, cache_manager: CacheManager):
        """读取不存在的 task_id 应返回 None。"""
        result = cache_manager.get_task(99999)
        assert result is None

    def test_save_overwrites_existing(self, cache_manager: CacheManager):
        """重复保存同一 task_id 应覆盖旧数据。"""
        cache_manager.save_task(10002, {"task_id": 10002, "title": "旧标题"})
        cache_manager.save_task(10002, {"task_id": 10002, "title": "新标题"})

        loaded = cache_manager.get_task(10002)
        assert loaded is not None
        assert loaded["title"] == "新标题"

    def test_invalidate_single(self, cache_manager: CacheManager):
        """invalidate(task_id) 应只删除指定任务。"""
        cache_manager.save_task(10003, {"task_id": 10003, "title": "A"})
        cache_manager.save_task(10004, {"task_id": 10004, "title": "B"})

        cache_manager.invalidate(10003)

        assert cache_manager.get_task(10003) is None
        assert cache_manager.get_task(10004) is not None

    def test_invalidate_all(self, cache_manager: CacheManager):
        """invalidate_all() 应清空所有缓存。"""
        cache_manager.save_task(10005, {"task_id": 10005, "title": "A"})
        cache_manager.save_task(10006, {"task_id": 10006, "title": "B"})

        cache_manager.invalidate_all()

        assert cache_manager.get_task(10005) is None
        assert cache_manager.get_task(10006) is None

    def test_get_status_valid(self, cache_manager: CacheManager):
        """新保存的条目状态应为 VALID。"""
        cache_manager.save_task(10007, {"task_id": 10007, "title": "test"})
        status = cache_manager.get_status(10007)
        assert status == CacheStatus.VALID

    def test_get_status_not_exists(self, cache_manager: CacheManager):
        """不存在的条目状态应为 NOT_EXISTS。"""
        status = cache_manager.get_status(99999)
        assert status == CacheStatus.NOT_EXISTS

    def test_get_status_expired(self, tmp_path: Path) -> None:
        """TTL 过期后状态应为 EXPIRED，且 get_task 返回 None。"""
        # 使用极短 TTL
        db_path = tmp_path / "short_ttl.db"
        manager = CacheManager(db_path=db_path, ttl=1)

        manager.save_task(10008, {"task_id": 10008, "title": "test"})

        # 手动修改数据库中的 expires_at 为过去时间
        past_time = (datetime.now() - timedelta(hours=1)).isoformat()
        with sqlite3.connect(db_path) as conn:
            conn.execute("UPDATE cache SET expires_at = ? WHERE task_id = ?", (past_time, 10008))
            conn.commit()

        status = manager.get_status(10008)
        assert status == CacheStatus.EXPIRED

        result = manager.get_task(10008)
        assert result is None

    def test_get_stats(self, cache_manager: CacheManager) -> None:
        """get_stats 应返回正确的统计信息。"""
        cache_manager.save_task(10009, {"task_id": 10009, "title": "A"})
        cache_manager.save_task(10010, {"task_id": 10010, "title": "B"})

        stats = cache_manager.get_stats()
        assert stats["total_entries"] == 2
        assert stats["valid_entries"] == 2
        assert stats["expired_entries"] == 0

    def test_get_index(self, cache_manager: CacheManager) -> None:
        """get_index 应返回所有条目的索引信息。"""
        cache_manager.save_task(10011, {"task_id": 10011, "title": "A"})
        cache_manager.save_task(10012, {"task_id": 10012, "title": "B"})

        index = cache_manager.get_index()
        assert len(index) == 2
        task_ids = {item["task_id"] for item in index}
        assert 10011 in task_ids
        assert 10012 in task_ids

    def test_cleanup_expired(self, tmp_path: Path) -> None:
        """cleanup_expired 应只删除过期条目。"""
        db_path = tmp_path / "cleanup_test.db"
        manager = CacheManager(db_path=db_path, ttl=3600)

        manager.save_task(10013, {"task_id": 10013, "title": "valid"})
        manager.save_task(10014, {"task_id": 10014, "title": "expired"})

        # 将 10014 标记为过期
        past_time = (datetime.now() - timedelta(hours=1)).isoformat()
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "UPDATE cache SET expires_at = ? WHERE task_id = ?",
                (past_time, 10014),
            )
            conn.commit()

        deleted = manager.cleanup_expired()
        assert deleted == 1

        assert manager.get_task(10013) is not None
        assert manager.get_task(10014) is None

    def test_db_file_created_on_init(self, tmp_path: Path) -> None:
        """CacheManager 初始化时应创建数据库文件。"""
        db_path = tmp_path / "subdir" / "cache.db"
        CacheManager(db_path=db_path, ttl=60)  # 初始化触发文件创建

        assert db_path.exists()
        # 验证表已创建
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            assert "cache" in tables

    def test_complex_data_roundtrip(self, cache_manager: CacheManager, sample_task_info: TaskInfo) -> None:
        """复杂嵌套数据应能正确保存和读取。"""
        task_dict = sample_task_info.model_dump(mode="json")
        cache_manager.save_task(10001, task_dict)

        loaded = cache_manager.load_task(10001)
        assert loaded is not None
        # 验证嵌套结构
        assert "development" in loaded
        assert "commits" in loaded["development"]
        assert len(loaded["development"]["commits"]) == 1
        assert loaded["development"]["commits"][0]["commit_id"] == "cache_test_001"
        assert "production" in loaded
        assert loaded["production"]["symptoms"] == "内存泄漏"
