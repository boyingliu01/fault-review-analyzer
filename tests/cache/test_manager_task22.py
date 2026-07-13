import tempfile
import time
from pathlib import Path

import pytest

from src.cache.manager import CacheManager
from src.cache.models import CacheStatus


class TestCacheManagerTask22:
    """CacheManager 扩展测试 - TTL 和性能验证"""

    @pytest.fixture
    def temp_cache_path(self):
        """创建临时数据库文件路径"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "test_cache.db"

    @pytest.fixture
    def cache_manager(self, temp_cache_path):
        """创建 CacheManager 实例"""
        cache = CacheManager(db_path=temp_cache_path, ttl=3600)
        yield cache
        # 确保所有连接都关闭
        try:
            cache.close()
        except Exception:
            pass
        import gc
        gc.collect()

    def test_ttl_precise_expiration(self, temp_cache_path):
        """测试精确的 TTL 过期机制"""
        # 使用非常短的 TTL
        cache = CacheManager(db_path=temp_cache_path, ttl=1)

        task_data = {"task_id": 123, "title": "Test Task"}
        cache.save_task(123, task_data)

        # 立即读取应该存在
        result = cache.get_task(123)
        assert result is not None
        assert result["task_id"] == 123

        # 等待 TTL 过期
        time.sleep(1.5)

        # 应该返回 None
        result = cache.get_task(123)
        assert result is None

    def test_ttl_status_transitions(self, temp_cache_path):
        """测试缓存状态转换"""
        cache = CacheManager(db_path=temp_cache_path, ttl=1)

        # 初始状态：不存在
        assert cache.get_status(999) == CacheStatus.NOT_EXISTS

        # 保存后：有效
        cache.save_task(999, {"task_id": 999})
        assert cache.get_status(999) == CacheStatus.VALID

        # 过期后：过期状态
        time.sleep(1.5)
        assert cache.get_status(999) == CacheStatus.EXPIRED

    def test_ttl_independent_entries(self, temp_cache_path):
        """测试不同任务的 TTL 独立"""
        cache = CacheManager(db_path=temp_cache_path, ttl=10)

        # 先保存一个任务
        cache.save_task(1, {"task_id": 1, "title": "Task 1"})

        # 等待一会儿
        time.sleep(0.5)

        # 再保存另一个任务
        cache.save_task(2, {"task_id": 2, "title": "Task 2"})

        # 两个都应该存在
        assert cache.get_task(1) is not None
        assert cache.get_task(2) is not None

    def test_cache_read_performance(self, cache_manager):
        """测试缓存读取性能"""
        # 预先写入大量数据
        num_tasks = 100
        for i in range(num_tasks):
            cache_manager.save_task(
                i,
                {
                    "task_id": i,
                    "title": f"Task {i}",
                    "description": "A test task with some content",
                    "data": list(range(100)),
                },
            )

        # 测试批量读取性能
        start_time = time.time()
        for i in range(num_tasks):
            cache_manager.get_task(i)
        elapsed = time.time() - start_time

        # 100次读取应该在 1 秒内完成
        assert elapsed < 1.0, f"Read operations too slow: {elapsed:.2f}s"

    def test_cache_write_performance(self, temp_cache_path):
        """测试缓存写入性能"""
        cache = CacheManager(db_path=temp_cache_path, ttl=3600)
        num_tasks = 100

        start_time = time.time()
        for i in range(num_tasks):
            cache.save_task(
                i,
                {
                    "task_id": i,
                    "title": f"Task {i}",
                    "content": "x" * 1000,  # 1KB 数据
                },
            )
        elapsed = time.time() - start_time

        # 100次写入应该在 2 秒内完成
        assert elapsed < 2.0, f"Write operations too slow: {elapsed:.2f}s"

    def test_cache_mixed_operations_performance(self, cache_manager):
        """测试混合操作性能"""
        num_operations = 50

        start_time = time.time()
        for i in range(num_operations):
            # 写入
            cache_manager.save_task(i, {"task_id": i, "data": "x" * 500})
            # 读取刚写入的
            cache_manager.get_task(i)
            # 读取一个不存在的
            cache_manager.get_task(i + 1000)

        elapsed = time.time() - start_time

        # 150次操作应该在 2 秒内完成
        assert elapsed < 2.0, f"Mixed operations too slow: {elapsed:.2f}s"

    def test_cleanup_expired_performance(self, temp_cache_path):
        """测试清理过期数据的性能"""
        # 使用短期 TTL
        cache = CacheManager(db_path=temp_cache_path, ttl=1)

        # 写入大量数据
        num_tasks = 100
        for i in range(num_tasks):
            cache.save_task(i, {"task_id": i})

        # 等待过期
        time.sleep(1.5)

        # 测试清理性能
        start_time = time.time()
        cleaned = cache.cleanup_expired()
        elapsed = time.time() - start_time

        assert cleaned == num_tasks
        assert elapsed < 1.0, f"Cleanup too slow: {elapsed:.2f}s"

    def test_large_data_caching(self, cache_manager):
        """测试大数据缓存"""
        large_data = {
            "task_id": 999,
            "title": "Large Task",
            "content": "x" * 10000,  # 10KB 数据
            "nested": {f"key_{i}": f"value_{i}" for i in range(100)},
        }

        # 保存和读取大数据
        cache_manager.save_task(999, large_data)
        result = cache_manager.get_task(999)

        assert result is not None
        assert result["task_id"] == 999
        assert len(result["content"]) == 10000
        assert len(result["nested"]) == 100

    def test_concurrent_save_same_task(self, cache_manager):
        """测试同一任务的并发保存（幂等性）"""
        data1 = {"task_id": 100, "version": 1, "title": "First"}
        data2 = {"task_id": 100, "version": 2, "title": "Second"}

        cache_manager.save_task(100, data1)
        cache_manager.save_task(100, data2)

        result = cache_manager.get_task(100)
        assert result["version"] == 2
        assert result["title"] == "Second"

    def test_get_all_tasks_excludes_expired(self, temp_cache_path):
        """测试 get_all_tasks 排除过期项"""
        cache = CacheManager(db_path=temp_cache_path, ttl=1)

        # 保存一些任务
        cache.save_task(1, {"task_id": 1, "title": "Expired Task"})
        cache.save_task(2, {"task_id": 2, "title": "Expired Task 2"})

        # 等待过期
        time.sleep(1.5)

        # 保存一个新的
        cache3 = CacheManager(db_path=temp_cache_path, ttl=3600)
        cache3.save_task(3, {"task_id": 3, "title": "Valid Task"})

        # 只应该返回有效的
        all_tasks = cache3.get_all_tasks()
        assert len(all_tasks) == 1
        assert all_tasks[0]["task_id"] == 3

    def test_stats_calculation(self, temp_cache_path):
        """测试统计信息计算"""
        cache = CacheManager(db_path=temp_cache_path, ttl=3600)

        # 空缓存
        stats = cache.get_stats()
        assert stats["total_entries"] == 0
        assert stats["valid_entries"] == 0
        assert stats["expired_entries"] == 0

        # 添加一些数据
        cache.save_task(1, {"task_id": 1})
        cache.save_task(2, {"task_id": 2})

        stats = cache.get_stats()
        assert stats["total_entries"] == 2
        assert stats["valid_entries"] == 2
        assert stats["expired_entries"] == 0
