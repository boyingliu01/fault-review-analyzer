"""P2 集成测试: Embedding → ChromaDB 存储集成。

使用合成 embedding 向量测试 ChromaDB 的存储和查询功能。
不依赖外部 embedding API。
"""

from pathlib import Path

import numpy as np
import pytest

chromadb = pytest.importorskip("chromadb", reason="chromadb 不可用则跳过")

from src.core.models import EmbeddingResult  # noqa: E402
from src.storage.chroma_manager import ChromaManager  # noqa: E402


@pytest.fixture
def chroma_manager(tmp_path: Path) -> ChromaManager:
    """创建使用临时目录的 ChromaManager。"""
    return ChromaManager(
        persist_directory=str(tmp_path / "chroma"),
    )


def _make_embedding(task_id: str, dim: int = 128, seed: int = 42) -> EmbeddingResult:
    """生成合成 EmbeddingResult。"""
    rng = np.random.RandomState(seed)
    vec = rng.randn(dim).tolist()
    return EmbeddingResult(
        task_id=task_id,
        embedding=vec,
        text=f"测试文本 {task_id}",
        media_type="text",
        metadata={"source": "test"},
    )


class TestChromaDBStoreAndQuery:
    """测试 ChromaDB 存储和查询。"""

    def test_add_and_query_embedding(self, chroma_manager: ChromaManager):
        """添加 embedding 后应能查询到。"""
        emb = _make_embedding("task_001", seed=1)
        success = chroma_manager.add_embedding(emb)
        assert success is True

        # 使用相同的 embedding 查询自身
        results = chroma_manager.query_similar(
            query_embedding=emb.embedding,
            n_results=1,
        )
        assert len(results) >= 1
        # 结果应包含我们添加的任务（task_id 在 metadata 中）
        task_ids = [r.get("metadata", {}).get("task_id", "") for r in results]
        assert "task_001" in task_ids

    def test_query_similar_returns_closest(self, chroma_manager: ChromaManager):
        """查询应返回最相似的结果。"""
        # 添加两个不同的 embedding
        emb1 = _make_embedding("task_A", seed=10)
        emb2 = _make_embedding("task_B", seed=20)
        chroma_manager.add_embedding(emb1)
        chroma_manager.add_embedding(emb2)

        # 查询与 emb1 最相似的
        results = chroma_manager.query_similar(
            query_embedding=emb1.embedding,
            n_results=2,
        )
        assert len(results) >= 1
        # 第一个结果应该是 task_A（与自身最相似）
        assert results[0].get("metadata", {}).get("task_id") == "task_A"

    def test_add_multiple_embeddings(self, chroma_manager: ChromaManager):
        """批量添加多个 embedding 后应能全部查询到。"""
        for i in range(5):
            emb = _make_embedding(f"task_{i:03d}", seed=i)
            chroma_manager.add_embedding(emb)

        # 查询应返回结果
        query_emb = _make_embedding("query", seed=0)
        results = chroma_manager.query_similar(
            query_embedding=query_emb.embedding,
            n_results=5,
        )
        assert len(results) >= 3  # 至少找到一些

    def test_metadata_stored_correctly(self, chroma_manager: ChromaManager):
        """embedding 的 metadata 应被正确存储。"""
        emb = EmbeddingResult(
            task_id="meta_test",
            embedding=np.random.randn(128).tolist(),
            text="元数据测试",
            media_type="text",
            metadata={"priority": "high", "category": "security"},
        )
        chroma_manager.add_embedding(emb)

        # 通过 task_id 获取记录并验证 metadata
        result = chroma_manager.get_by_task_id("meta_test")
        assert result is not None
        # metadata 应包含我们设置的字段
        assert result["metadata"].get("priority") == "high"
        assert result["metadata"].get("category") == "security"
        assert result["metadata"].get("task_id") == "meta_test"


class TestChromaDBCollectionManagement:
    """测试 ChromaDB 集合管理。"""

    def test_create_collection(self, chroma_manager: ChromaManager):
        """应能创建新的集合。"""
        collection = chroma_manager.get_or_create_collection("test_collection")
        assert collection is not None
        assert collection.name == "test_collection"

    def test_list_collections(self, chroma_manager: ChromaManager):
        """应能列出所有集合。"""
        chroma_manager.get_or_create_collection("col_a")
        chroma_manager.get_or_create_collection("col_b")

        collections = chroma_manager.list_collections()
        names = [c.name if hasattr(c, "name") else c for c in collections]
        assert "col_a" in names
        assert "col_b" in names

    def test_get_collection_count(self, chroma_manager: ChromaManager):
        """集合应能返回正确的条目数。"""
        collection = chroma_manager.get_or_create_collection("count_test")

        # 添加几个 embedding
        for i in range(3):
            emb = _make_embedding(f"count_{i}", seed=i)
            collection.upsert(
                embeddings=[emb.embedding],
                ids=[emb.task_id],
                metadatas=[{"task_id": emb.task_id}],
            )

        assert collection.count() == 3


class TestChromaDBPersistence:
    """测试 ChromaDB 数据持久化。"""

    def test_data_persists_across_instances(self, tmp_path: Path):
        """数据应在不同 ChromaManager 实例间持久化。"""
        persist_dir = str(tmp_path / "persist_test")

        # 第一个实例写入数据
        manager1 = ChromaManager(persist_directory=persist_dir)
        emb = _make_embedding("persist_001", seed=1)
        manager1.add_embedding(emb)

        # 第二个实例读取数据
        manager2 = ChromaManager(persist_directory=persist_dir)
        results = manager2.query_similar(
            query_embedding=emb.embedding,
            n_results=1,
        )
        assert len(results) >= 1
        assert results[0].get("metadata", {}).get("task_id") == "persist_001"
