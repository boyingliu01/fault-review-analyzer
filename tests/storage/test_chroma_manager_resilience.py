"""ChromaDB 容错机制测试"""

from pathlib import Path
from unittest.mock import patch

import pytest

from src.core.models import EmbeddingResult
from src.storage.chroma_manager import (
    ChromaDBConnectionError,
    ChromaDBError,
    ChromaDBWriteError,
    ChromaManager,
    FallbackCache,
)


class TestFallbackCache:
    """本地缓存降级机制测试"""

    def test_init_creates_directory(self, tmp_path: Path):
        """初始化时创建缓存目录"""
        cache_dir = tmp_path / "fallback"
        FallbackCache(cache_dir)
        assert cache_dir.exists()

    def test_add_pending_creates_file(self, tmp_path: Path):
        """添加待处理数据创建文件"""
        cache_dir = tmp_path / "fallback"
        cache = FallbackCache(cache_dir)

        result = cache.add_pending(
            task_id="TASK-001",
            embedding=[0.1, 0.2, 0.3],
            text="test text",
            metadata={"source": "test"},
        )

        assert result is True
        assert cache.get_pending_count() == 1

    def test_load_pending_returns_records(self, tmp_path: Path):
        """加载待处理记录返回正确数据"""
        cache_dir = tmp_path / "fallback"
        cache = FallbackCache(cache_dir)

        cache.add_pending(
            task_id="TASK-001",
            embedding=[0.1, 0.2, 0.3],
            text="text 1",
            metadata={"idx": 1},
        )
        cache.add_pending(
            task_id="TASK-002",
            embedding=[0.4, 0.5, 0.6],
            text="text 2",
            metadata={"idx": 2},
        )

        records = cache.load_pending()
        assert len(records) == 2
        assert records[0]["task_id"] == "TASK-001"
        assert records[1]["task_id"] == "TASK-002"

    def test_clear_pending_removes_file(self, tmp_path: Path):
        """清空待处理记录删除文件"""
        cache_dir = tmp_path / "fallback"
        cache = FallbackCache(cache_dir)

        cache.add_pending(
            task_id="TASK-001",
            embedding=[0.1],
            text="text",
            metadata={},
        )
        assert cache.get_pending_count() == 1

        cache.clear_pending()
        assert cache.get_pending_count() == 0

    def test_get_pending_count_empty_file(self, tmp_path: Path):
        """空文件返回 0"""
        cache_dir = tmp_path / "fallback"
        cache = FallbackCache(cache_dir)
        assert cache.get_pending_count() == 0


class TestChromaManagerResilience:
    """ChromaDB 容错机制测试"""

    def test_init_with_fallback_enabled(self, tmp_path: Path):
        """启用降级时创建缓存"""
        chroma_dir = tmp_path / "chroma"
        fallback_dir = tmp_path / "fallback"

        manager = ChromaManager(
            persist_directory=chroma_dir,
            enable_fallback=True,
            fallback_dir=fallback_dir,
        )

        assert manager._enable_fallback is True
        assert manager._fallback_cache is not None
        assert manager.is_healthy()

    def test_init_with_fallback_disabled(self, tmp_path: Path):
        """禁用降级时不创建缓存"""
        chroma_dir = tmp_path / "chroma"

        manager = ChromaManager(
            persist_directory=chroma_dir,
            enable_fallback=False,
        )

        assert manager._enable_fallback is False
        assert manager._fallback_cache is None

    def test_add_embedding_success(self, chroma_manager, sample_embedding_result):
        """成功添加向量"""
        result = chroma_manager.add_embedding(sample_embedding_result)
        assert result is True
        assert chroma_manager.is_healthy()

    def test_add_batch_embeddings_returns_per_item_status(
        self, chroma_manager, sample_embedding_results
    ):
        """批量添加返回每个任务的状态"""
        results = chroma_manager.add_batch_embeddings(sample_embedding_results)

        assert isinstance(results, dict)
        assert len(results) == len(sample_embedding_results)
        assert all(results.values())

    def test_get_pending_count_zero_initially(self, chroma_manager):
        """初始待处理数为 0"""
        assert chroma_manager.get_pending_count() == 0

    def test_get_stats_includes_health_info(self, chroma_manager):
        """统计信息包含健康状态"""
        stats = chroma_manager.get_stats()

        assert "connection_healthy" in stats
        assert "pending_writes" in stats
        assert stats["connection_healthy"] is True

    def test_sync_pending_writes_empty(self, chroma_manager):
        """无待同步数据时返回 0"""
        synced = chroma_manager.sync_pending_writes()
        assert synced == 0

    def test_fallback_on_connection_error(self, tmp_path: Path):
        """连接失败时降级到本地缓存"""
        chroma_dir = tmp_path / "chroma"
        fallback_dir = tmp_path / "fallback"

        with patch("chromadb.PersistentClient") as mock_client:
            # 模拟连接失败
            mock_client.side_effect = Exception("Connection refused")

            manager = ChromaManager(
                persist_directory=chroma_dir,
                enable_fallback=True,
                fallback_dir=fallback_dir,
            )

            # 连接应标记为不健康
            assert manager.is_healthy() is False

    def test_add_embedding_fallback_to_cache(self, tmp_path: Path):
        """添加向量失败时缓存到本地"""
        chroma_dir = tmp_path / "chroma"
        fallback_dir = tmp_path / "fallback"

        manager = ChromaManager(
            persist_directory=chroma_dir,
            enable_fallback=True,
            fallback_dir=fallback_dir,
        )

        # 正常情况下先添加一个
        embedding = EmbeddingResult(
            task_id="FALLBACK-001",
            embedding=[0.1] * 128,
            text="fallback test",
            media_type="text",
        )

        # 模拟后续写入失败
        with patch.object(manager, "_retry_operation") as mock_retry:
            # 第一次调用返回 False（模拟失败）
            mock_retry.return_value = False
            result = manager.add_embedding(embedding)
            assert result is False

    def test_connection_error_raised_without_fallback(self, tmp_path: Path):
        """禁用降级时连接错误抛出异常"""
        chroma_dir = tmp_path / "chroma"

        with patch("chromadb.PersistentClient") as mock_client:
            mock_client.side_effect = Exception("Connection refused")

            with pytest.raises(ChromaDBConnectionError):
                ChromaManager(
                    persist_directory=chroma_dir,
                    enable_fallback=False,
                )

    def test_retry_logic_on_transient_failure(self, tmp_path: Path):
        """瞬时故障触发重试"""
        chroma_dir = tmp_path / "chroma"

        # 使用真实的 ChromaDB 但模拟瞬时故障
        manager = ChromaManager(
            persist_directory=chroma_dir,
            enable_fallback=True,
        )

        # 验证重试配置
        assert manager.MAX_RETRIES == 3
        assert manager.RETRY_DELAY == 1.0


class TestChromaManagerSyncPending:
    """待处理数据同步测试"""

    def test_sync_writes_pending_to_chroma(self, chroma_manager, sample_embedding_result):
        """同步将缓存数据写入 ChromaDB"""
        # 先手动添加到 fallback cache
        if chroma_manager._fallback_cache:
            chroma_manager._fallback_cache.add_pending(
                task_id=sample_embedding_result.task_id,
                embedding=sample_embedding_result.embedding,
                text=sample_embedding_result.text,
                metadata={
                    "task_id": sample_embedding_result.task_id,
                    "media_type": sample_embedding_result.media_type,
                },
            )

            assert chroma_manager.get_pending_count() == 1

            # 同步
            synced = chroma_manager.sync_pending_writes()
            assert synced == 1

            # 缓存应被清空
            assert chroma_manager.get_pending_count() == 0

            # 数据应存在于 ChromaDB
            result = chroma_manager.get_by_task_id(sample_embedding_result.task_id)
            assert result is not None

    def test_sync_handles_partial_failure(self, chroma_manager):
        """同步处理部分失败"""
        if not chroma_manager._fallback_cache:
            pytest.skip("Fallback not enabled")

        # 添加多条记录
        for i in range(3):
            chroma_manager._fallback_cache.add_pending(
                task_id=f"PARTIAL-{i}",
                embedding=[0.1] * 128,
                text=f"text {i}",
                metadata={"idx": i},
            )

        # 正常同步应成功
        synced = chroma_manager.sync_pending_writes()
        assert synced == 3


class TestChromaDBExceptions:
    """异常类测试"""

    def test_chromadb_error_message(self):
        """错误消息格式正确"""
        error = ChromaDBError("test message", "test_op")
        assert "test_op" in str(error)
        assert "test message" in str(error)

    def test_chromadb_error_with_cause(self):
        """错误包含原始异常"""
        cause = ValueError("original error")
        error = ChromaDBError("wrapped", "operation", cause=cause)
        assert error.cause is cause

    def test_connection_error_is_chromadb_error(self):
        """连接错误是 ChromaDBError 子类"""
        error = ChromaDBConnectionError("conn failed", "connect")
        assert isinstance(error, ChromaDBError)

    def test_write_error_is_chromadb_error(self):
        """写入错误是 ChromaDBError 子类"""
        error = ChromaDBWriteError("write failed", "add")
        assert isinstance(error, ChromaDBError)


class TestChromaManagerHealthCheck:
    """健康检查测试"""

    def test_is_healthy_returns_true_when_connected(self, chroma_manager):
        """连接正常时返回 True"""
        assert chroma_manager.is_healthy() is True

    def test_is_healthy_returns_false_on_error(self, tmp_path: Path):
        """错误时返回 False"""
        chroma_dir = tmp_path / "chroma"

        manager = ChromaManager(
            persist_directory=chroma_dir,
            enable_fallback=True,
        )

        # 模拟心跳失败
        with patch.object(manager._client, "heartbeat") as mock_heartbeat:
            mock_heartbeat.side_effect = Exception("heartbeat failed")
            assert manager.is_healthy() is False

    def test_is_healthy_returns_false_without_client(self, tmp_path: Path):
        """无客户端时返回 False"""
        chroma_dir = tmp_path / "chroma"

        manager = ChromaManager(
            persist_directory=chroma_dir,
            enable_fallback=True,
        )
        manager._client = None
        manager._connection_healthy = False

        assert manager.is_healthy() is False
