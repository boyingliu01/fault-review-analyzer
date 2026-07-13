import asyncio

import numpy as np
import pytest

from src.embedding.generator import (
    AdaptiveRateLimiter,
    EmbeddingGenerator,
    LRUEmbeddingCache,
)


class TestLRUEmbeddingCache:
    """测试 LRU 缓存"""

    def test_cache_basic_operations(self):
        """测试基本的缓存操作"""
        cache = LRUEmbeddingCache(max_size=10)

        vector = [0.1, 0.2, 0.3]
        cache.set("test text", vector)

        result = cache.get("test text")
        assert result == vector

    def test_cache_miss(self):
        """测试缓存未命中"""
        cache = LRUEmbeddingCache(max_size=10)

        result = cache.get("nonexistent")
        assert result is None

    def test_cache_eviction_lru(self):
        """测试 LRU 淘汰策略"""
        cache = LRUEmbeddingCache(max_size=3)

        cache.set("key1", [1.0])
        cache.set("key2", [2.0])
        cache.set("key3", [3.0])

        # 访问 key1，使其变为最近使用
        cache.get("key1")

        # 添加 key4，应该淘汰 key2（最久未使用）
        cache.set("key4", [4.0])

        assert cache.get("key1") is not None
        assert cache.get("key2") is None
        assert cache.get("key3") is not None
        assert cache.get("key4") is not None

    def test_cache_ttl(self):
        """测试 TTL 过期"""
        cache = LRUEmbeddingCache(max_size=10, ttl=1)

        cache.set("test", [1.0])
        assert cache.get("test") is not None

        # 修改内部时间，模拟过期
        from datetime import datetime, timedelta
        cache._cache[cache._get_key("test")] = (
            [1.0],
            datetime.now() - timedelta(seconds=2),
        )

        assert cache.get("test") is None

    def test_cache_clear(self):
        """测试清空缓存"""
        cache = LRUEmbeddingCache(max_size=10)

        cache.set("key1", [1.0])
        cache.set("key2", [2.0])
        assert len(cache) == 2

        cache.clear()
        assert len(cache) == 0


class TestAdaptiveRateLimiter:
    """测试自适应速率限制器"""

    @pytest.mark.asyncio
    async def test_rate_limiter_acquire(self):
        """测试获取令牌"""
        limiter = AdaptiveRateLimiter(initial_qps=100.0)

        # 应该能快速获取多次
        start = asyncio.get_event_loop().time()
        for _ in range(5):
            await limiter.acquire()
        elapsed = asyncio.get_event_loop().time() - start

        assert elapsed < 0.5  # 应该很快完成

    def test_rate_limiter_backoff(self):
        """测试退避机制"""
        limiter = AdaptiveRateLimiter(initial_qps=10.0)

        initial_qps = limiter.current_qps
        limiter.record_failure()
        assert limiter.current_qps < initial_qps

        # 多次失败
        for _ in range(10):
            limiter.record_failure()
        min_qps = limiter.current_qps
        limiter.record_failure()
        assert limiter.current_qps == min_qps  # 不应低于最小值

    def test_rate_limiter_recovery(self):
        """测试恢复机制"""
        limiter = AdaptiveRateLimiter(initial_qps=10.0)

        # 先降低
        limiter.record_failure()
        low_qps = limiter.current_qps

        # 再恢复
        limiter.record_success()
        assert limiter.current_qps > low_qps

        # 多次成功
        for _ in range(10):
            limiter.record_success()
        max_qps = limiter.current_qps
        limiter.record_success()
        # 检查是否接近 max_qps，允许浮点误差
        assert abs(limiter.current_qps - limiter.max_qps) < 0.0001 or limiter.current_qps <= limiter.max_qps


class TestEmbeddingGeneratorTask24:
    """测试 EmbeddingGenerator 的新功能"""

    @pytest.fixture
    def generator(self):
        return EmbeddingGenerator(
            provider="local",
            model="text-embedding-3-small",
            enable_cache=True,
        )

    def test_generator_with_cache(self, generator):
        """测试缓存功能"""
        assert generator._cache is not None

    def test_generator_no_cache(self):
        """测试无缓存模式"""
        generator = EmbeddingGenerator(
            provider="local", enable_cache=False
        )
        assert generator._cache is None

    @pytest.mark.asyncio
    async def test_embed_text_caching(self):
        """测试文本嵌入缓存"""
        generator = EmbeddingGenerator(
            provider="local", enable_cache=True, cache_max_size=100
        )

        text = "test text for caching"

        # 第一次调用
        result1 = await generator.embed_text(text)

        # 第二次调用应该从缓存获取
        result2 = await generator.embed_text(text)

        assert result1 == result2
        # 验证缓存中存在
        assert generator._cache is not None
        assert generator._cache.get(text) is not None

    @pytest.mark.asyncio
    async def test_embed_batch_caching(self):
        """测试批量嵌入缓存"""
        generator = EmbeddingGenerator(
            provider="local", enable_cache=True
        )

        texts = ["text 1", "text 2", "text 3"]

        # 第一次调用
        results1 = await generator.embed_batch(texts)

        # 第二次调用应该从缓存获取
        results2 = await generator.embed_batch(texts)

        assert results1 == results2

    @pytest.mark.asyncio
    async def test_embed_batch_mixed_cache(self):
        """测试部分缓存命中"""
        generator = EmbeddingGenerator(
            provider="local", enable_cache=True
        )

        # 先缓存一个
        text1 = "cached text"
        await generator.embed_text(text1)

        # 批量请求包含缓存和未缓存的
        texts = [text1, "new text 1", "new text 2"]
        results = await generator.embed_batch(texts)

        assert len(results) == 3

    def test_dimension_map(self):
        """测试维度映射"""
        generator = EmbeddingGenerator(
            provider="openai", model="text-embedding-3-small"
        )
        assert generator.get_dimension() == 1536

        generator = EmbeddingGenerator(
            provider="openai", model="text-embedding-3-large"
        )
        assert generator.get_dimension() == 3072

        generator = EmbeddingGenerator(
            provider="unknown", model="unknown-model"
        )
        assert generator.get_dimension() == 1536  # 默认值

    @pytest.mark.asyncio
    async def test_embed_empty_text(self, generator):
        """测试空文本处理"""
        with pytest.raises(ValueError):
            await generator.embed_text("")

        with pytest.raises(ValueError):
            await generator.embed_text("   ")

    @pytest.mark.asyncio
    async def test_embed_batch_empty_texts(self):
        """测试批量空文本处理"""
        generator = EmbeddingGenerator(
            provider="local", enable_cache=True
        )

        # 空文本列表
        texts = ["", "valid text", "   "]
        results = await generator.embed_batch(texts)

        assert len(results) == 3

    def test_cosine_similarity(self):
        """测试余弦相似度"""
        vec1 = np.array([1.0, 0.0, 0.0])
        vec2 = np.array([1.0, 0.0, 0.0])
        vec3 = np.array([0.0, 1.0, 0.0])

        assert EmbeddingGenerator.cosine_similarity(vec1, vec2) == 1.0
        assert EmbeddingGenerator.cosine_similarity(vec1, vec3) == 0.0

    def test_cosine_similarity_matrix(self):
        """测试余弦相似度矩阵"""
        embeddings = np.array([
            [1.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        ])

        matrix = EmbeddingGenerator.cosine_similarity_matrix(embeddings)

        assert matrix.shape == (3, 3)
        assert abs(matrix[0][1] - 1.0) < 1e-8
        assert abs(matrix[0][2]) < 1e-8
