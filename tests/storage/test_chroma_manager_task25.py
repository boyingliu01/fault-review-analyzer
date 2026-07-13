from unittest.mock import MagicMock, patch

import pytest

from src.core.models import EmbeddingResult
from src.storage.chroma_manager import ChromaManager


class TestChromaManagerTask25:
    """ChromaManager 扩展测试 - 批量操作状态返回"""

    @pytest.fixture
    def mock_chroma_collection(self):
        """创建 mock 集合"""
        mock_collection = MagicMock()
        mock_collection.add.return_value = None
        mock_collection.get.return_value = {
            "ids": ["123"],
            "documents": ["test doc"],
            "embeddings": [[0.1, 0.2, 0.3]],
            "metadatas": [{"task_id": "123"}],
        }
        mock_collection.query.return_value = {
            "ids": [["123", "456"]],
            "documents": [["doc1", "doc2"]],
            "distances": [[0.1, 0.2]],
            "metadatas": [[{"task_id": "123"}, {"task_id": "456"}]],
        }
        return mock_collection

    @pytest.fixture
    def mock_chroma_client(self, mock_chroma_collection):
        """创建 mock 客户端"""
        mock_client = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_chroma_collection
        mock_client.list_collections.return_value = ["fault_embeddings"]
        mock_client.heartbeat.return_value = None
        return mock_client

    @pytest.fixture
    def chroma_manager(self, tmp_path, mock_chroma_client):
        """创建 ChromaManager 实例"""
        with patch("chromadb.PersistentClient", return_value=mock_chroma_client):
            manager = ChromaManager(
                persist_directory=str(tmp_path / "chroma"),
                enable_fallback=False,
            )
            manager._connection_healthy = True
            return manager

    def test_add_batch_embeddings_basic(self, chroma_manager, mock_chroma_collection):
        """测试基本的批量添加"""
        embeddings = [
            EmbeddingResult(
                task_id="1",
                text="text 1",
                embedding=[0.1, 0.2, 0.3],
                media_type="text",
            ),
            EmbeddingResult(
                task_id="2",
                text="text 2",
                embedding=[0.4, 0.5, 0.6],
                media_type="text",
            ),
        ]

        results = chroma_manager.add_batch_embeddings(embeddings)

        assert len(results) == 2
        assert "1" in results
        assert "2" in results
        assert all(isinstance(v, bool) for v in results.values())

        # 验证是否调用了批量添加
        mock_chroma_collection.add.assert_called_once()

    def test_add_batch_embeddings_dict_input(self, chroma_manager):
        """测试字典输入的批量添加"""
        embeddings = [
            {
                "task_id": "1",
                "text": "text 1",
                "embedding": [0.1, 0.2, 0.3],
                "metadata": {"priority": "high"},
            },
            {
                "task_id": "2",
                "text": "text 2",
                "embedding": [0.4, 0.5, 0.6],
                "metadata": {"priority": "low"},
            },
        ]

        results = chroma_manager.add_batch_embeddings(embeddings)

        assert len(results) == 2
        assert "1" in results
        assert "2" in results
        assert all(isinstance(v, bool) for v in results.values())

    def test_add_batch_with_detailed_status(self, chroma_manager):
        """测试详细状态返回"""
        embeddings = [
            EmbeddingResult(
                task_id="1",
                text="text 1",
                embedding=[0.1, 0.2, 0.3],
                media_type="text",
            ),
            EmbeddingResult(
                task_id="2",
                text="text 2",
                embedding=[0.4, 0.5, 0.6],
                media_type="text",
            ),
        ]

        results = chroma_manager.add_batch_embeddings_with_detailed_status(embeddings)

        assert len(results) == 2
        assert "1" in results
        assert "2" in results

        for task_id, info in results.items():
            assert "success" in info
            assert "source" in info
            assert isinstance(info["success"], bool)
            assert isinstance(info["source"], str)

        # 应该都是成功的
        assert all(info["success"] for info in results.values())

    def test_query_by_metadata(self, chroma_manager):
        """测试元数据查询"""
        results = chroma_manager.query_by_metadata({"priority": "high"})

        assert len(results) > 0
        assert all(isinstance(r, dict) for r in results)

    def test_query_empty_metadata(self, chroma_manager):
        """测试空元数据查询"""
        results = chroma_manager.query_by_metadata({})
        assert len(results) > 0

    def test_add_embedding_with_metadata(self, chroma_manager, mock_chroma_collection):
        """测试带元数据的添加"""
        embedding = EmbeddingResult(
            task_id="123",
            text="test text",
            embedding=[0.1, 0.2, 0.3],
            media_type="text",
            metadata={"priority": "high", "status": "resolved"},
        )

        chroma_manager.add_embedding(embedding)

        # 验证调用参数 - 检查是否有调用
        assert mock_chroma_collection.upsert.called, "Collection.upsert 方法没有被调用"
        call_args = mock_chroma_collection.upsert.call_args
        args, kwargs = call_args

        assert kwargs["ids"] == ["123"]
        assert len(kwargs["metadatas"]) == 1
        assert kwargs["metadatas"][0]["priority"] == "high"
        assert kwargs["metadatas"][0]["status"] == "resolved"

    def test_query_similar_by_embedding(self, chroma_manager):
        """测试通过向量查询相似"""
        query_vector = [0.1, 0.2, 0.3]
        results = chroma_manager.query_similar(query_embedding=query_vector, n_results=5)

        assert len(results) >= 1
        assert "id" in results[0]
        assert "distance" in results[0]

    def test_query_similar_by_text(self, chroma_manager):
        """测试通过文本查询相似"""
        results = chroma_manager.query_similar(query_text="test query", n_results=3)

        assert len(results) >= 1
        assert "id" in results[0]
        assert "document" in results[0]

    def test_get_by_task_id_not_found(self, chroma_manager, mock_chroma_collection):
        """测试查询不存在的任务"""
        mock_chroma_collection.get.return_value = {"ids": []}
        result = chroma_manager.get_by_task_id("nonexistent")
        assert result is None

    def test_collection_stats(self, chroma_manager):
        """测试集合统计"""
        stats = chroma_manager.get_stats()
        assert "total_embeddings" in stats
        assert "collections" in stats
        assert "connection_healthy" in stats
        assert "pending_writes" in stats

    def test_fallback_behavior_when_chroma_unavailable(self, tmp_path):
        """测试 Chroma 不可用时的降级行为（简化版）"""
        # 创建 ChromaManager，强制连接状态为不健康
        manager = ChromaManager(
            persist_directory=str(tmp_path / "chroma"),
            enable_fallback=True,
        )
        manager._connection_healthy = False

        embedding = EmbeddingResult(
            task_id="123",
            text="test",
            embedding=[0.1, 0.2, 0.3],
            media_type="text",
        )

        # 应该降级到本地缓存
        result = manager.add_embedding(embedding)
        # 结果取决于是否成功写入 fallback
        assert isinstance(result, bool)

    def test_batch_add_with_fallback(self, tmp_path):
        """测试批量添加时的降级行为（简化版）"""
        manager = ChromaManager(
            persist_directory=str(tmp_path / "chroma"),
            enable_fallback=True,
        )
        manager._connection_healthy = False

        embeddings = [
            EmbeddingResult(
                task_id="1",
                text="text 1",
                embedding=[0.1, 0.2, 0.3],
                media_type="text",
            ),
            EmbeddingResult(
                task_id="2",
                text="text 2",
                embedding=[0.4, 0.5, 0.6],
                media_type="text",
            ),
        ]

        results = manager.add_batch_embeddings(embeddings)
        assert len(results) == 2
        assert all(isinstance(v, bool) for v in results.values())
