"""ChromaManager 扩展测试套件 - 补充测试以提升覆盖率"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import numpy as np

from src.storage.chroma_manager import ChromaManager
from src.core.models import EmbeddingResult


class TestChromaManagerExtended:
    """ChromaManager 扩展测试"""

    def test_init_client_failure(self):
        """测试初始化客户端失败"""
        with patch("src.storage.chroma_manager.chromadb") as mock_chroma:
            mock_chroma.PersistentClient.side_effect = Exception("初始化失败")
            
            with pytest.raises(Exception, match="初始化失败"):
                ChromaManager()

    def test_query_similar_with_results(self):
        """测试查询相似向量有结果"""
        with patch("src.storage.chroma_manager.chromadb") as mock_chroma:
            mock_client = MagicMock()
            mock_collection = MagicMock()

            # 模拟查询结果
            mock_collection.query.return_value = {
                "ids": [["id1", "id2"]],
                "distances": [[0.1, 0.2]],
                "metadatas": [[{"task_id": "T1"}, {"task_id": "T2"}]],
                "documents": [["text1", "text2"]],
            }

            mock_client.get_or_create_collection.return_value = mock_collection
            mock_chroma.PersistentClient.return_value = mock_client

            manager = ChromaManager()
            # 使用 query_embedding 参数
            results = manager.query_similar(
                query_embedding=[0.1] * 2048,
                n_results=2,
            )

            assert len(results) == 2
            assert results[0]["metadata"]["task_id"] == "T1"
            assert results[0]["distance"] == 0.1

    def test_query_similar_empty(self):
        """测试查询相似向量为空"""
        with patch("src.storage.chroma_manager.chromadb") as mock_chroma:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_collection.query.return_value = {
                "ids": [[]],
                "distances": [[]],
                "metadatas": [[]],
                "documents": [[]],
            }

            mock_client.get_or_create_collection.return_value = mock_collection
            mock_chroma.PersistentClient.return_value = mock_client

            manager = ChromaManager()
            results = manager.query_similar(query_embedding=[0.1] * 2048)

            assert len(results) == 0

    def test_get_stats(self):
        """测试获取统计信息"""
        with patch("src.storage.chroma_manager.chromadb") as mock_chroma:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_collection.count.return_value = 10

            mock_client.get_or_create_collection.return_value = mock_collection
            mock_client.list_collections.return_value = [
                MagicMock(name="collection1"),
            ]
            mock_chroma.PersistentClient.return_value = mock_client

            manager = ChromaManager()
            stats = manager.get_stats()

            assert stats["total_embeddings"] == 10
            assert "collections" in stats
            assert "persist_directory" in stats

    def test_get_stats_error(self):
        """测试获取统计信息失败"""
        with patch("src.storage.chroma_manager.chromadb") as mock_chroma:
            mock_client = MagicMock()
            mock_client.list_collections.side_effect = Exception("连接失败")
            mock_chroma.PersistentClient.return_value = mock_client

            manager = ChromaManager()
            stats = manager.get_stats()

            assert stats["total_embeddings"] == 0
            assert stats["collections"] == []

    def test_delete_by_task_id(self):
        """测试按任务ID删除"""
        with patch("src.storage.chroma_manager.chromadb") as mock_chroma:
            mock_client = MagicMock()
            mock_collection = MagicMock()

            mock_client.get_or_create_collection.return_value = mock_collection
            mock_chroma.PersistentClient.return_value = mock_client

            manager = ChromaManager()
            result = manager.delete_by_task_id("TASK-001")

            assert result is True
            mock_collection.delete.assert_called_once_with(ids=["TASK-001"])

    def test_delete_by_task_id_error(self):
        """测试删除失败"""
        with patch("src.storage.chroma_manager.chromadb") as mock_chroma:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_collection.delete.side_effect = Exception("删除失败")

            mock_client.get_or_create_collection.return_value = mock_collection
            mock_chroma.PersistentClient.return_value = mock_client

            manager = ChromaManager()
            result = manager.delete_by_task_id("TASK-001")

            assert result is False

    def test_get_by_task_id_found(self):
        """测试根据任务ID获取向量 - 找到"""
        with patch("src.storage.chroma_manager.chromadb") as mock_chroma:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_collection.get.return_value = {
                "ids": ["TASK-001"],
                "embeddings": [[0.1] * 2048],
                "metadatas": [{"task_id": "TASK-001"}],
                "documents": ["测试文本"],
            }

            mock_client.get_or_create_collection.return_value = mock_collection
            mock_chroma.PersistentClient.return_value = mock_client

            manager = ChromaManager()
            result = manager.get_by_task_id("TASK-001")

            assert result is not None
            assert result["metadata"]["task_id"] == "TASK-001"

    def test_get_by_task_id_not_found(self):
        """测试根据任务ID获取向量 - 未找到"""
        with patch("src.storage.chroma_manager.chromadb") as mock_chroma:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_collection.get.return_value = {
                "ids": [],
                "embeddings": [],
                "metadatas": [],
                "documents": [],
            }

            mock_client.get_or_create_collection.return_value = mock_collection
            mock_chroma.PersistentClient.return_value = mock_client

            manager = ChromaManager()
            result = manager.get_by_task_id("TASK-001")

            assert result is None

    def test_update_metadata(self):
        """测试更新元数据"""
        with patch("src.storage.chroma_manager.chromadb") as mock_chroma:
            mock_client = MagicMock()
            mock_collection = MagicMock()

            mock_client.get_or_create_collection.return_value = mock_collection
            mock_chroma.PersistentClient.return_value = mock_client

            manager = ChromaManager()
            result = manager.update_metadata(
                "TASK-001",
                {"new_key": "new_value"},
            )

            assert result is True
            mock_collection.update.assert_called_once()

    def test_update_metadata_error(self):
        """测试更新元数据失败"""
        with patch("src.storage.chroma_manager.chromadb") as mock_chroma:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_collection.update.side_effect = Exception("更新失败")

            mock_client.get_or_create_collection.return_value = mock_collection
            mock_chroma.PersistentClient.return_value = mock_client

            manager = ChromaManager()
            result = manager.update_metadata("TASK-001", {})

            assert result is False

    def test_list_collections(self):
        """测试列出所有集合"""
        with patch("src.storage.chroma_manager.chromadb") as mock_chroma:
            mock_client = MagicMock()
            # 创建具有 name 属性的 mock 对象
            col1_mock = MagicMock()
            col1_mock.name = "col1"
            col2_mock = MagicMock()
            col2_mock.name = "col2"
            
            mock_client.list_collections.return_value = [col1_mock, col2_mock]
            mock_chroma.PersistentClient.return_value = mock_client

            manager = ChromaManager()
            collections = manager.list_collections()

            assert len(collections) == 2
            assert "col1" in collections
            assert "col2" in collections

    def test_list_collections_error(self):
        """测试列出集合失败"""
        with patch("src.storage.chroma_manager.chromadb") as mock_chroma:
            mock_client = MagicMock()
            mock_client.list_collections.side_effect = Exception("列出失败")
            mock_chroma.PersistentClient.return_value = mock_client

            manager = ChromaManager()
            collections = manager.list_collections()

            assert collections == []

    def test_delete_collection(self):
        """测试删除集合"""
        with patch("src.storage.chroma_manager.chromadb") as mock_chroma:
            mock_client = MagicMock()
            mock_chroma.PersistentClient.return_value = mock_client

            manager = ChromaManager()
            result = manager.delete_collection("test_collection")

            assert result is True
            mock_client.delete_collection.assert_called_once_with(
                name="test_collection"
            )

    def test_delete_collection_error(self):
        """测试删除集合失败"""
        with patch("src.storage.chroma_manager.chromadb") as mock_chroma:
            mock_client = MagicMock()
            mock_client.delete_collection.side_effect = Exception("删除失败")
            mock_chroma.PersistentClient.return_value = mock_client

            manager = ChromaManager()
            result = manager.delete_collection("test_collection")

            assert result is False

    def test_reset(self):
        """测试重置数据库"""
        with patch("src.storage.chroma_manager.chromadb") as mock_chroma:
            mock_client = MagicMock()
            mock_chroma.PersistentClient.return_value = mock_client

            manager = ChromaManager()
            result = manager.reset()

            assert result is True
            mock_client.reset.assert_called_once()

    def test_reset_error(self):
        """测试重置失败"""
        with patch("src.storage.chroma_manager.chromadb") as mock_chroma:
            mock_client = MagicMock()
            mock_client.reset.side_effect = Exception("重置失败")
            mock_chroma.PersistentClient.return_value = mock_client

            manager = ChromaManager()
            result = manager.reset()

            assert result is False

    def test_get_stats_with_exception(self):
        """测试获取统计信息时发生异常"""
        with patch("src.storage.chroma_manager.chromadb") as mock_chroma:
            mock_client = MagicMock()
            mock_client.list_collections.side_effect = Exception("统计失败")
            mock_chroma.PersistentClient.return_value = mock_client

            manager = ChromaManager()
            stats = manager.get_stats()

            assert stats["total_embeddings"] == 0
            assert stats["collections"] == []

    def test_search_similar_with_filter(self):
        """测试带过滤条件的相似性搜索"""
        with patch("src.storage.chroma_manager.chromadb") as mock_chroma:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_collection.query.return_value = {
                "ids": [["TASK-001", "TASK-002"]],
                "distances": [[0.1, 0.2]],
                "metadatas": [[{"key": "value1"}, {"key": "value2"}]],
                "documents": [["doc1", "doc2"]],
            }

            mock_client.get_or_create_collection.return_value = mock_collection
            mock_chroma.PersistentClient.return_value = mock_client

            manager = ChromaManager()
            results = manager.query_similar(
                query_embedding=[0.1] * 1024,
                n_results=5,
                where={"status": "active"},
            )

            assert len(results) == 2
            assert results[0]["id"] == "TASK-001"


class TestEmbeddingResult:
    """EmbeddingResult 测试"""

    def test_create_embedding_result(self):
        """测试创建嵌入结果"""
        result = EmbeddingResult(
            task_id="TASK-001",
            text="测试文本",
            embedding=[0.1, 0.2, 0.3],
            media_type="text",
            metadata={"key": "value"},
        )

        assert result.task_id == "TASK-001"
        assert result.media_type == "text"
        assert len(result.embedding) == 3
        assert result.metadata == {"key": "value"}

    def test_embedding_result_default_values(self):
        """测试默认值"""
        result = EmbeddingResult(
            task_id="TASK-001",
            embedding=[0.1, 0.2],
        )

        assert result.media_type == "text"
        assert result.text == ""
        assert result.metadata == {}  # 默认是空字典
