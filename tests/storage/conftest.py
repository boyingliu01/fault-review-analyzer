"""Storage模块测试 fixtures"""

import random

import pytest

from src.core.models import EmbeddingResult
from src.storage.chroma_manager import ChromaManager


@pytest.fixture
def temp_chroma_dir(tmp_path):
    return tmp_path / "chroma_test"


@pytest.fixture
def chroma_manager(temp_chroma_dir):
    return ChromaManager(persist_directory=temp_chroma_dir)


@pytest.fixture
def sample_embedding_result():
    return EmbeddingResult(
        task_id="TASK-TEST-001",
        embedding=[0.1] * 1536,
        text="这是一个测试故障单的向量化文本内容",
        media_type="text",
        metadata={"source": "test", "priority": "high"},
    )


@pytest.fixture
def sample_embedding_results():
    random.seed(42)
    return [
        EmbeddingResult(
            task_id=f"TASK-TEST-{i:03d}",
            embedding=[random.gauss(0, 1) for _ in range(1536)],
            text=f"测试故障单 {i} 的文本内容",
            media_type="text",
            metadata={"index": i},
        )
        for i in range(1, 6)
    ]
