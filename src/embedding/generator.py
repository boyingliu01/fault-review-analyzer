import asyncio
import hashlib
from collections import OrderedDict
from datetime import datetime, timedelta

import numpy as np
from openai import AsyncOpenAI

from src.embedding.models import BatchEmbeddingResult, EmbeddingResult
from src.utils.circuit_breaker import CircuitBreaker, CircuitBreakerError


class LRUEmbeddingCache:
    """LRU缓存用于存储文本到向量的映射"""

    def __init__(self, max_size: int = 10000, ttl: int = 86400):
        self.max_size = max_size
        self.ttl = ttl
        self._cache: OrderedDict[str, tuple[list[float], datetime]] = OrderedDict()

    def _get_key(self, text: str) -> str:
        """生成文本的缓存键"""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def get(self, text: str) -> list[float] | None:
        """获取缓存的向量"""
        key = self._get_key(text)
        if key not in self._cache:
            return None
        vec, timestamp = self._cache[key]
        if datetime.now() - timestamp > timedelta(seconds=self.ttl):
            del self._cache[key]
            return None
        self._cache.move_to_end(key)
        return vec

    def set(self, text: str, vector: list[float]) -> None:
        """设置缓存的向量"""
        key = self._get_key(text)
        if key in self._cache:
            self._cache.move_to_end(key)
        elif len(self._cache) >= self.max_size:
            self._cache.popitem(last=False)
        self._cache[key] = (vector, datetime.now())

    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()

    def __len__(self) -> int:
        return len(self._cache)


class AdaptiveRateLimiter:
    """自适应速率限制器"""

    def __init__(
        self,
        initial_qps: float = 10.0,
        min_qps: float = 1.0,
        max_qps: float = 50.0,
        backoff_factor: float = 0.5,
        recovery_factor: float = 1.1,
    ):
        self.min_qps = min_qps
        self.max_qps = max_qps
        self.backoff_factor = backoff_factor
        self.recovery_factor = recovery_factor
        self.current_qps = initial_qps
        self._last_request_time: float = 0.0
        self._min_interval = 1.0 / max_qps

    async def acquire(self) -> None:
        """获取请求令牌"""
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request_time
        interval = 1.0 / self.current_qps
        if elapsed < interval:
            await asyncio.sleep(interval - elapsed)
        self._last_request_time = asyncio.get_event_loop().time()

    def record_success(self) -> None:
        """记录成功请求"""
        self.current_qps = min(self.current_qps * self.recovery_factor, self.max_qps)

    def record_failure(self) -> None:
        """记录失败请求（触发退避）"""
        self.current_qps = max(self.current_qps * self.backoff_factor, self.min_qps)


class EmbeddingGenerator:
    def __init__(
        self,
        provider: str = "openai",
        model: str = "text-embedding-3-small",
        api_key: str = "",
        base_url: str | None = None,
        batch_size: int = 100,
        circuit_breaker: CircuitBreaker | None = None,
        timeout: float = 60.0,
        max_concurrency: int = 10,
        enable_cache: bool = True,
        cache_max_size: int = 10000,
        cache_ttl: int = 86400,
    ):
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.batch_size = batch_size
        self.timeout = timeout
        self.max_concurrency = max_concurrency
        self._client: AsyncOpenAI | None = None
        self._circuit_breaker = circuit_breaker or CircuitBreaker(
            name=f"embedding_{provider}",
            failure_threshold=5,
            reset_timeout=60.0,
        )
        self._dimension_map = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
            "embedding-3": 1024,
            "doubao-embedding-large": 4096,
            "doubao-embedding-text-240715": 1024,
            "Doubao-embedding-240715": 1024,
            "doubao-embedding-vision-251215": 2048,
        }
        # 缓存
        self._cache = LRUEmbeddingCache(max_size=cache_max_size, ttl=cache_ttl) if enable_cache else None
        # 速率限制器
        self._rate_limiter = AdaptiveRateLimiter()
        # 信号量用于并发控制
        self._semaphore = asyncio.Semaphore(max_concurrency)

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        """Get the circuit breaker instance."""
        return self._circuit_breaker

    def _get_client(self) -> AsyncOpenAI | None:
        if self._client is None:
            if self.provider == "openai":
                self._client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                )
            elif self.provider == "zhipu":
                self._client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url="https://open.bigmodel.cn/api/paas/v4/",
                )
            elif self.provider == "volcengine":
                self._client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                )
            elif self.provider == "whalecloud":
                # 浩鲸内部代理（OpenAI兼容协议）
                self._client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                )
            elif self.provider == "local":
                pass
        return self._client

    async def embed_text(self, text: str) -> list[float]:
        if not text or not text.strip():
            raise ValueError("Text cannot be empty for embedding")

        # 检查缓存
        if self._cache is not None:
            cached = self._cache.get(text)
            if cached is not None:
                return cached

        if self.provider == "local":
            result = self._local_embed_single(text)
            if self._cache is not None:
                self._cache.set(text, result)
            return result

        # Check circuit breaker before making API call
        if not self._circuit_breaker.can_execute():
            raise CircuitBreakerError(
                self._circuit_breaker.name,
                self._circuit_breaker.reset_timeout,
            )

        try:
            await self._rate_limiter.acquire()
            async with self._semaphore:
                if self.provider == "volcengine" and "vision" in self.model.lower():
                    result = await self._embed_volcengine_vision(text)
                else:
                    client = self._get_client()
                    if client is None:
                        raise ValueError("Embedding client not initialized")

                    response = await client.embeddings.create(
                        model=self.model,
                        input=text,
                        timeout=self.timeout,
                    )
                    result = list(response.data[0].embedding)

            self._circuit_breaker.record_success()
            self._rate_limiter.record_success()

            if self._cache is not None:
                self._cache.set(text, result)

            return result

        except ValueError:
            # Client initialization error - don't record as circuit failure
            raise
        except Exception as e:
            self._circuit_breaker.record_failure(e)
            self._rate_limiter.record_failure()
            raise

    async def _embed_volcengine_vision(self, text: str) -> list[float]:
        import httpx

        base_url = (self.base_url or "").rstrip("/")
        if not base_url.endswith("/embeddings/multimodal"):
            if base_url.endswith("/embeddings"):
                base_url = base_url + "/multimodal"
            else:
                base_url = base_url + "/embeddings/multimodal"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        payload = {
            "model": self.model,
            "input": [{"type": "text", "text": text}],
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(base_url, json=payload, headers=headers, timeout=30)
            if response.status_code != 200:
                raise Exception(f"HTTP {response.status_code}: {response.text}")
            data = response.json()
            return list(data["data"]["embedding"])

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        results: list[list[float] | None] = [None] * len(texts)
        uncached_indices: list[int] = []
        uncached_texts: list[str] = []

        # 首先检查缓存
        if self._cache is not None:
            for i, text in enumerate(texts):
                if not text or not text.strip():
                    results[i] = [0.0] * self.get_dimension()
                else:
                    cached = self._cache.get(text)
                    if cached is not None:
                        results[i] = cached
                    else:
                        uncached_indices.append(i)
                        uncached_texts.append(text)
        else:
            for i, text in enumerate(texts):
                if not text or not text.strip():
                    results[i] = [0.0] * self.get_dimension()
                else:
                    uncached_indices.append(i)
                    uncached_texts.append(text)

        if not uncached_texts:
            # 所有都在缓存中
            return [r for r in results if r is not None]

        if self.provider == "local":
            local_results = self._local_embed_batch(uncached_texts)
            for i, idx in enumerate(uncached_indices):
                results[idx] = local_results[i]
                if self._cache is not None:
                    self._cache.set(uncached_texts[i], local_results[i])
            return [r for r in results if r is not None]

        # 处理需要生成的文本
        if self.provider == "volcengine" and "vision" in self.model.lower():
            # 单个处理（火山视觉模型）
            for idx, text in zip(uncached_indices, uncached_texts, strict=True):
                emb = await self.embed_text(text)  # 使用单个方法（已包含缓存逻辑）
                results[idx] = emb
            return [r for r in results if r is not None]

        # 其他provider使用批量并发处理
        # Check circuit breaker before making API calls
        if not self._circuit_breaker.can_execute():
            raise CircuitBreakerError(
                self._circuit_breaker.name,
                self._circuit_breaker.reset_timeout,
            )

        # 分批并发处理
        batch_results = await self._embed_batch_concurrent(uncached_texts)

        # 填充结果和缓存
        for i, idx in enumerate(uncached_indices):
            results[idx] = batch_results[i]
            if self._cache is not None:
                self._cache.set(uncached_texts[i], batch_results[i])

        return [r for r in results if r is not None]

    async def _embed_batch_concurrent(self, texts: list[str]) -> list[list[float]]:
        """并发批量处理embedding"""
        results: list[list[float]] = []

        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            batch_result = await self._embed_batch_internal(batch)
            results.extend(batch_result)

        return results

    def _local_embed_single(self, text: str) -> list[float]:
        import hashlib

        hash_obj = hashlib.sha256(text.encode())
        hash_bytes = hash_obj.digest()
        vector = []
        dim = 1024
        for i in range(dim):
            byte_idx = i % len(hash_bytes)
            next_byte_idx = (byte_idx + 1) % len(hash_bytes)
            val = (hash_bytes[byte_idx] + hash_bytes[next_byte_idx] * 0.01) / 255.0
            vector.append(val)
        norm = sum(v * v for v in vector) ** 0.5
        if norm > 0:
            vector = [v / norm for v in vector]
        return vector

    def _local_embed_batch(self, texts: list[str]) -> list[list[float]]:
        import hashlib

        def text_to_vector(text: str, dim: int = 1024) -> list[float]:
            hash_obj = hashlib.sha256(text.encode())
            hash_bytes = hash_obj.digest()
            vector = []
            for i in range(dim):
                byte_idx = i % len(hash_bytes)
                next_byte_idx = (byte_idx + 1) % len(hash_bytes)
                val = (hash_bytes[byte_idx] + hash_bytes[next_byte_idx] * 0.01) / 255.0
                vector.append(val)
            norm = sum(v * v for v in vector) ** 0.5
            if norm > 0:
                vector = [v / norm for v in vector]
            return vector

        return [text_to_vector(text) for text in texts]

    async def _embed_batch_internal(self, texts: list[str]) -> list[list[float]]:
        client = self._get_client()
        if client is None:
            raise ValueError("Embedding client not initialized")

        try:
            response = await client.embeddings.create(
                model=self.model,
                input=texts,
            )

            embeddings = [list(item.embedding) for item in response.data]
            self._circuit_breaker.record_success()
            return embeddings
        except ValueError:
            # Client initialization error - don't record as circuit failure
            raise
        except Exception as e:
            self._circuit_breaker.record_failure(e)
            raise

    async def embed_tasks(
        self,
        task_data: list[dict],
        text_field: str = "combined_text",
    ) -> BatchEmbeddingResult:
        texts = [task.get(text_field, "") for task in task_data]
        embeddings = await self.embed_batch(texts)

        results = []
        for i, (task, embedding) in enumerate(zip(task_data, embeddings, strict=False)):
            results.append(
                EmbeddingResult(
                    task_id=task.get("task_id", i),
                    embedding=embedding,
                    model=self.model,
                    metadata={"text_length": len(task.get(text_field, ""))},
                )
            )

        return BatchEmbeddingResult(
            results=results,
            total_count=len(task_data),
            success_count=len(results),
            error_count=0,
            model=self.model,
        )

    def get_dimension(self) -> int:
        return self._dimension_map.get(self.model, 1536)

    @staticmethod
    def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    @staticmethod
    def cosine_similarity_matrix(embeddings: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        normalized = embeddings / (norms + 1e-10)
        result = np.dot(normalized, normalized.T)
        return np.asarray(result)
