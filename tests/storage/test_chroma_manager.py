"""Chroma向量数据库管理器测试套件"""

import pytest
from unittest.mock import MagicMock, patch

from src.storage.chroma_manager import ChromaManager
from src.core.models import EmbeddingResult


class TestChromaManager:
    """Chroma向量数据库管理器测试套件"""

    def test_create_collection(self, chroma_manager):
        """测试创建集合"""
        collection = chroma_manager.get_or_create_collection("test_collection")
        assert collection is not None

    def test_add_embedding(self, chroma_manager, sample_embedding_result):
        """测试添加向量"""
        result = chroma_manager.add_embedding(
            embedding=sample_embedding_result,
            collection_name="test_faults",
        )
        assert result is True

    def test_add_batch_embeddings(self, chroma_manager, sample_embedding_results):
        """测试批量添加向量"""
        result = chroma_manager.add_batch_embeddings(
            embeddings=sample_embedding_results,
            collection_name="test_faults",
        )
        assert result is True

    def test_query_similar(self, chroma_manager):
        """测试相似向量查询"""
        query_embedding = [0.1] * 2048
        results = chroma_manager.query_similar(
            collection_name="test_faults",
            query_embedding=query_embedding,
            n_results=3,
        )
        assert isinstance(results, list)

    def test_get_by_task_id(self, chroma_manager, sample_embedding_result):
        """测试按task_id查询"""
        chroma_manager.add_embedding(
            embedding=sample_embedding_result,
            collection_name="test_faults",
        )
        result = chroma_manager.get_by_task_id(
            task_id=sample_embedding_result.task_id,
            collection_name="test_faults",
        )
        assert result is not None

    def test_update_metadata(self, chroma_manager, sample_embedding_result):
        """测试更新元数据"""
        chroma_manager.add_embedding(
            embedding=sample_embedding_result,
            collection_name="test_faults",
        )
        new_metadata = {"status": "analyzed", "cluster_id": 1}
        result = chroma_manager.update_metadata(
            task_id=sample_embedding_result.task_id,
            metadata=new_metadata,
            collection_name="test_faults",
        )
        assert result is True

    def test_delete_embedding(self, chroma_manager, sample_embedding_result):
        """测试删除向量"""
        chroma_manager.add_embedding(
            embedding=sample_embedding_result,
            collection_name="test_faults",
        )
        result = chroma_manager.delete_embedding(
            task_id=sample_embedding_result.task_id,
            collection_name="test_faults",
        )
        assert result is True

    def test_get_collection_stats(self, chroma_manager):
        """测试获取集合统计信息"""
        stats = chroma_manager.get_collection_stats("test_faults")
        assert isinstance(stats, dict)

    def test_list_collections(self, chroma_manager):
        """测试列出所有集合"""
        collections = chroma_manager.list_collections()
        assert isinstance(collections, list)

    def test_multimodal_metadata(self, chroma_manager):
        """测试多模态元数据支持"""
        embedding = EmbeddingResult(
            task_id="TASK-MULTI",
            embedding=[0.1] * 2048,
            text="测试文本",
            media_type="mixed",
            metadata={"images": 2, "text_length": 100},
        )
        result = chroma_manager.add_embedding(
            collection_name="test_multimodal",
            embedding=embedding,
        )
        assert result is True
