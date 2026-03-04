from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from src.embedding.generator import EmbeddingGenerator
from src.embedding.models import EmbeddingResult


class TestEmbeddingGenerator:
    @pytest.fixture
    def generator(self):
        return EmbeddingGenerator(
            provider="openai",
            model="text-embedding-3-small",
            api_key="test-key",
        )

    @pytest.mark.asyncio
    async def test_generate_single_embedding(self, generator):
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1536)]

        with patch("openai.AsyncOpenAI") as mock_client:
            mock_client.return_value.embeddings.create = AsyncMock(return_value=mock_response)

            generator._client = mock_client.return_value
            result = await generator.embed_text("Test text")

            assert result is not None
            assert len(result) == 1536

    @pytest.mark.asyncio
    async def test_generate_batch_embeddings(self, generator):
        texts = ["Text 1", "Text 2", "Text 3"]
        mock_response = MagicMock()
        mock_response.data = [
            MagicMock(embedding=[0.1] * 1536),
            MagicMock(embedding=[0.2] * 1536),
            MagicMock(embedding=[0.3] * 1536),
        ]

        with patch("openai.AsyncOpenAI") as mock_client:
            mock_client.return_value.embeddings.create = AsyncMock(return_value=mock_response)

            generator._client = mock_client.return_value
            results = await generator.embed_batch(texts)

            assert len(results) == 3
            assert all(len(r) == 1536 for r in results)

    def test_cosine_similarity(self, generator):
        vec1 = np.array([1.0, 0.0, 0.0])
        vec2 = np.array([1.0, 0.0, 0.0])
        vec3 = np.array([0.0, 1.0, 0.0])

        sim_same = generator.cosine_similarity(vec1, vec2)
        sim_diff = generator.cosine_similarity(vec1, vec3)

        assert abs(sim_same - 1.0) < 0.001
        assert abs(sim_diff - 0.0) < 0.001

    def test_embedding_dimension(self, generator):
        assert generator.get_dimension() == 1536

    @pytest.mark.asyncio
    async def test_empty_text_handling(self, generator):
        with pytest.raises(ValueError, match="Text cannot be empty"):
            await generator.embed_text("")

    @pytest.mark.asyncio
    async def test_embed_texts(self, generator):
        texts = ["Text 1", "Text 2"]
        mock_response = MagicMock()
        mock_response.data = [
            MagicMock(embedding=[0.1] * 1536),
            MagicMock(embedding=[0.2] * 1536),
        ]

        with patch("openai.AsyncOpenAI") as mock_client:
            mock_client.return_value.embeddings.create = AsyncMock(return_value=mock_response)

            generator._client = mock_client.return_value
            results = await generator.embed_batch(texts)

            assert len(results) == 2

    def test_get_model_name(self, generator):
        assert generator.model == "text-embedding-3-small"

    def test_get_provider(self, generator):
        assert generator.provider == "openai"

    @pytest.mark.asyncio
    async def test_embed_batch_empty_list(self, generator):
        results = await generator.embed_batch([])
        assert results == []

    def test_cosine_similarity_zero_vector(self, generator):
        vec1 = np.array([0.0, 0.0, 0.0])
        vec2 = np.array([1.0, 0.0, 0.0])

        sim = generator.cosine_similarity(vec1, vec2)

        assert sim == 0.0

    def test_cosine_similarity_matrix(self, generator):
        vecs = np.array([
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [1.0, 1.0, 0.0],
        ])

        matrix = generator.cosine_similarity_matrix(vecs)

        assert matrix.shape == (3, 3)
        assert abs(matrix[0, 0] - 1.0) < 0.001


class TestEmbeddingResult:
    def test_create_result(self):
        result = EmbeddingResult(
            task_id=12345,
            embedding=[0.1] * 1536,
            model="text-embedding-3-small",
        )

        assert result.task_id == 12345
        assert len(result.embedding) == 1536
        assert result.model == "text-embedding-3-small"

    def test_to_numpy(self):
        result = EmbeddingResult(
            task_id=1,
            embedding=[0.1, 0.2, 0.3],
            model="test-model",
        )

        arr = result.to_numpy()

        assert isinstance(arr, np.ndarray)
        assert arr.shape == (3,)

    def test_result_with_metadata(self):
        result = EmbeddingResult(
            task_id=1,
            embedding=[0.1, 0.2],
            model="test-model",
            metadata={"source": "test"},
        )

        assert result.metadata["source"] == "test"
