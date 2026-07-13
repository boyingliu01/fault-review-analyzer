"""EmbeddingGenerator 扩展测试 - 边界场景"""

from unittest.mock import AsyncMock, Mock, patch

import numpy as np
import pytest

from src.embedding.generator import EmbeddingGenerator
from src.embedding.models import BatchEmbeddingResult, EmbeddingResult


class TestEmbeddingGeneratorBoundary:
    """EmbeddingGenerator 边界场景测试"""

    @pytest.mark.asyncio
    async def test_embed_text_empty_string(self):
        """测试空字符串向量化应该抛出异常"""
        generator = EmbeddingGenerator(provider="openai", api_key="test-key")

        with pytest.raises(ValueError, match="Text cannot be empty"):
            await generator.embed_text("")

    @pytest.mark.asyncio
    async def test_embed_text_whitespace_only(self):
        """测试仅包含空白字符的字符串"""
        generator = EmbeddingGenerator(provider="openai", api_key="test-key")

        with pytest.raises(ValueError, match="Text cannot be empty"):
            await generator.embed_text("   \n\t  ")

    @pytest.mark.asyncio
    async def test_embed_text_none_provider(self):
        """测试 provider 为 None 的情况"""
        generator = EmbeddingGenerator(provider="unknown", api_key="test-key")

        with pytest.raises(ValueError, match="client not initialized"):
            await generator.embed_text("测试文本")

    @pytest.mark.asyncio
    async def test_embed_text_api_error(self):
        """测试 API 调用失败"""
        generator = EmbeddingGenerator(provider="openai", api_key="test-key")

        with patch.object(generator, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.embeddings.create.side_effect = Exception("API Error")
            mock_get_client.return_value = mock_client

            with pytest.raises(Exception, match="API Error"):
                await generator.embed_text("测试文本")

    @pytest.mark.asyncio
    async def test_embed_text_very_long_text(self):
        """测试超长文本向量化"""
        generator = EmbeddingGenerator(provider="openai", api_key="test-key")
        long_text = "测试" * 10000  # 非常长的文本

        with patch.object(generator, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.data = [Mock(embedding=[0.1] * 1536)]
            mock_client.embeddings.create.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await generator.embed_text(long_text)
            assert len(result) == 1536

    @pytest.mark.asyncio
    async def test_embed_text_special_characters(self):
        """测试特殊字符文本"""
        generator = EmbeddingGenerator(provider="openai", api_key="test-key")
        special_text = "<script>alert('xss')</script> \\n\\t 中文🎉 émojis"

        with patch.object(generator, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.data = [Mock(embedding=[0.1] * 1536)]
            mock_client.embeddings.create.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await generator.embed_text(special_text)
            assert len(result) == 1536

    @pytest.mark.asyncio
    async def test_embed_batch_empty_list(self):
        """测试空列表批处理"""
        generator = EmbeddingGenerator(provider="openai", api_key="test-key")

        result = await generator.embed_batch([])
        assert result == []

    @pytest.mark.asyncio
    async def test_embed_batch_single_item(self):
        """测试单条数据批处理"""
        generator = EmbeddingGenerator(provider="openai", api_key="test-key")

        with patch.object(generator, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.data = [Mock(embedding=[0.1] * 1536)]
            mock_client.embeddings.create.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await generator.embed_batch(["测试文本"])
            assert len(result) == 1
            assert len(result[0]) == 1536

    @pytest.mark.asyncio
    async def test_embed_batch_multiple_items(self):
        """测试多条数据批处理"""
        generator = EmbeddingGenerator(provider="openai", api_key="test-key", batch_size=2)

        with patch.object(generator, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.data = [
                Mock(embedding=[0.1] * 1536),
                Mock(embedding=[0.2] * 1536),
            ]
            mock_client.embeddings.create.return_value = mock_response
            mock_get_client.return_value = mock_client

            texts = ["文本1", "文本2"]
            result = await generator.embed_batch(texts)

            assert len(result) == 2
            assert len(result[0]) == 1536
            assert len(result[1]) == 1536

    @pytest.mark.asyncio
    async def test_embed_batch_exceeds_batch_size(self):
        """测试超过批处理大小"""
        generator = EmbeddingGenerator(provider="openai", api_key="test-key", batch_size=2)

        with patch.object(generator, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.data = [
                Mock(embedding=[0.1] * 1536),
                Mock(embedding=[0.2] * 1536),
            ]
            mock_client.embeddings.create.return_value = mock_response
            mock_get_client.return_value = mock_client

            texts = ["文本1", "文本2", "文本3", "文本4"]
            await generator.embed_batch(texts)

            # 应该分两次调用
            assert mock_client.embeddings.create.call_count == 2

    def test_get_dimension_known_model(self):
        """测试已知模型的维度"""
        generator = EmbeddingGenerator(provider="openai", model="text-embedding-3-small")
        assert generator.get_dimension() == 1536

    def test_get_dimension_unknown_model(self):
        """测试未知模型的默认维度"""
        generator = EmbeddingGenerator(provider="openai", model="unknown-model")
        assert generator.get_dimension() == 1536  # 默认维度

    @pytest.mark.asyncio
    async def test_local_embed_single(self):
        """测试本地嵌入"""
        generator = EmbeddingGenerator(provider="local")

        result = await generator.embed_text("测试文本")
        assert len(result) == 1024  # 本地嵌入维度
        assert all(isinstance(x, float) for x in result)

    @pytest.mark.asyncio
    async def test_volcengine_vision_embed(self):
        """测试火山引擎视觉模型嵌入"""
        generator = EmbeddingGenerator(
            provider="volcengine",
            model="doubao-embedding-vision-251215",
            api_key="test-key",
            base_url="https://api.volcengine.com",
        )

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.status_code = 200
            # 实际响应格式: data["data"]["embedding"]
            mock_response.json.return_value = {"data": {"embedding": [0.1] * 2048}}
            mock_client.post.return_value = mock_response
            mock_httpx.return_value.__aenter__.return_value = mock_client

            result = await generator.embed_text("测试文本")
            assert len(result) == 2048

    @pytest.mark.asyncio
    async def test_volcengine_vision_error(self):
        """测试火山引擎视觉模型错误"""
        generator = EmbeddingGenerator(
            provider="volcengine",
            model="doubao-embedding-vision-251215",
            api_key="test-key",
            base_url="https://api.volcengine.com",
        )

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            mock_client.post.return_value = mock_response
            mock_httpx.return_value.__aenter__.return_value = mock_client

            with pytest.raises(Exception, match="HTTP 500"):
                await generator.embed_text("测试文本")

    @pytest.mark.asyncio
    async def test_volcengine_vision_invalid_response(self):
        """测试火山引擎视觉模型无效响应"""
        generator = EmbeddingGenerator(
            provider="volcengine",
            model="doubao-embedding-vision-251215",
            api_key="test-key",
            base_url="https://api.volcengine.com",
        )

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"error": "invalid request"}  # 没有 data 字段
            mock_client.post.return_value = mock_response
            mock_httpx.return_value.__aenter__.return_value = mock_client

            with pytest.raises((KeyError, IndexError)):
                await generator.embed_text("测试文本")

    def test_different_providers_initialization(self):
        """测试不同 provider 的初始化"""
        providers = ["openai", "zhipu", "volcengine", "local"]

        for provider in providers:
            generator = EmbeddingGenerator(provider=provider, api_key="test-key")
            assert generator.provider == provider

    @pytest.mark.asyncio
    async def test_embed_text_unicode_edge_cases(self):
        """测试 Unicode 边界情况"""
        generator = EmbeddingGenerator(provider="openai", api_key="test-key")

        unicode_texts = [
            "",  # 空字符串已在其他测试覆盖
            "🎉" * 100,  # 纯表情符号
            "\x00\x01\x02",  # 控制字符
            "日本語テキスト",  # 日文
            "한국어텍스트",  # 韩文
            "العربية",  # 阿拉伯文
        ]

        with patch.object(generator, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.data = [Mock(embedding=[0.1] * 1536)]
            mock_client.embeddings.create.return_value = mock_response
            mock_get_client.return_value = mock_client

            for text in unicode_texts[1:]:  # 跳过空字符串
                result = await generator.embed_text(text)
                assert len(result) == 1536

    @pytest.mark.asyncio
    async def test_embed_batch_local_provider(self):
        """测试本地 provider 的批处理"""
        generator = EmbeddingGenerator(provider="local")

        texts = ["文本1", "文本2", "文本3"]
        result = await generator.embed_batch(texts)

        assert len(result) == 3
        assert all(len(emb) == 1024 for emb in result)  # 本地嵌入维度是 1024

    @pytest.mark.asyncio
    async def test_embed_batch_with_whitespace(self):
        """测试批处理中的空白文本"""
        generator = EmbeddingGenerator(provider="openai", api_key="test-key")

        with patch.object(generator, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.data = [Mock(embedding=[0.1] * 1536)]
            mock_client.embeddings.create.return_value = mock_response
            mock_get_client.return_value = mock_client

            # 包含空白文本的列表
            texts = ["正常文本", "   ", "另一个文本"]
            with pytest.raises(ValueError, match="Text cannot be empty"):
                await generator.embed_batch(texts)

    @pytest.mark.asyncio
    async def test_embed_tasks_success(self):
        """测试 embed_tasks 成功"""
        generator = EmbeddingGenerator(provider="openai", api_key="test-key")

        task_data = [
            {"task_id": 1, "combined_text": "文本1"},
            {"task_id": 2, "combined_text": "文本2"},
        ]

        with patch.object(generator, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.data = [
                Mock(embedding=[0.1] * 1536),
                Mock(embedding=[0.2] * 1536),
            ]
            mock_client.embeddings.create.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await generator.embed_tasks(task_data)

            assert result.total_count == 2
            assert result.success_count == 2
            assert len(result.results) == 2

    def test_cosine_similarity_identical(self):
        """测试相同向量的余弦相似度"""
        vec = np.array([1.0, 0.0, 0.0])
        similarity = EmbeddingGenerator.cosine_similarity(vec, vec)
        assert abs(similarity - 1.0) < 1e-6

    def test_cosine_similarity_orthogonal(self):
        """测试正交向量的余弦相似度"""
        vec1 = np.array([1.0, 0.0, 0.0])
        vec2 = np.array([0.0, 1.0, 0.0])
        similarity = EmbeddingGenerator.cosine_similarity(vec1, vec2)
        assert abs(similarity - 0.0) < 1e-6

    def test_cosine_similarity_zero_vector(self):
        """测试零向量的余弦相似度"""
        vec1 = np.array([0.0, 0.0, 0.0])
        vec2 = np.array([1.0, 0.0, 0.0])
        similarity = EmbeddingGenerator.cosine_similarity(vec1, vec2)
        assert similarity == 0.0

    def test_get_dimension_known_models(self):
        """测试已知模型的维度"""
        generator = EmbeddingGenerator(
            provider="openai", api_key="test-key", model="text-embedding-3-small"
        )
        assert generator.get_dimension() == 1536

    def test_get_dimension_default(self):
        """测试默认维度"""
        generator = EmbeddingGenerator(provider="openai", api_key="test-key", model="unknown-model")
        assert generator.get_dimension() == 1536

    def test_zhipu_provider_initialization(self):
        """测试智谱 provider 初始化"""
        generator = EmbeddingGenerator(provider="zhipu", api_key="test-key")
        assert generator.provider == "zhipu"
        # 触发 _get_client
        client = generator._get_client()
        assert client is not None

    def test_volcengine_provider_initialization(self):
        """测试火山引擎 provider 初始化"""
        generator = EmbeddingGenerator(
            provider="volcengine", api_key="test-key", base_url="https://api.volcengine.com"
        )
        assert generator.provider == "volcengine"
        # 触发 _get_client
        client = generator._get_client()
        assert client is not None


class TestEmbeddingModelsBoundary:
    """Embedding 模型边界测试"""

    def test_embedding_result_with_defaults(self):
        """测试 EmbeddingResult 默认值"""
        result = EmbeddingResult(
            task_id=1,
            embedding=[0.1, 0.2, 0.3],
            model="test-model",
        )
        assert result.task_id == 1
        assert result.model == "test-model"
        assert result.metadata == {}  # 默认是空字典

    def test_batch_embedding_result_empty(self):
        """测试空批处理结果"""
        result = BatchEmbeddingResult(
            results=[],
            total_count=0,
            success_count=0,
            error_count=0,
        )
        assert result.total_count == 0
        assert len(result.results) == 0

    def test_batch_embedding_result_mixed(self):
        """测试混合成功失败的批处理结果"""
        result = BatchEmbeddingResult(
            results=[
                EmbeddingResult(task_id=1, embedding=[0.1] * 10, model="model1"),
                EmbeddingResult(task_id=2, embedding=[0.2] * 10, model="model1"),
            ],
            total_count=3,
            success_count=2,
            error_count=1,
            model="model1",
        )
        assert result.total_count == 3
        assert result.success_count == 2
        assert result.error_count == 1
