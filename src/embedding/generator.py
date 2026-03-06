import numpy as np
from openai import AsyncOpenAI

from src.embedding.models import BatchEmbeddingResult, EmbeddingResult


class EmbeddingGenerator:
    def __init__(
        self,
        provider: str = "openai",
        model: str = "text-embedding-3-small",
        api_key: str = "",
        base_url: str | None = None,
        batch_size: int = 100,
    ):
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.batch_size = batch_size
        self._client: AsyncOpenAI | None = None
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
            elif self.provider == "local":
                pass
        return self._client

    async def embed_text(self, text: str) -> list[float]:
        if not text or not text.strip():
            raise ValueError("Text cannot be empty for embedding")

        if self.provider == "local":
            return self._local_embed_single(text)

        if self.provider == "volcengine" and "vision" in self.model.lower():
            return await self._embed_volcengine_vision(text)

        client = self._get_client()
        if client is None:
            raise ValueError("Embedding client not initialized")

        response = await client.embeddings.create(
            model=self.model,
            input=text,
        )

        return list(response.data[0].embedding)

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
            try:
                response = await client.post(base_url, json=payload, headers=headers, timeout=30)
                if response.status_code != 200:
                    raise Exception(f"HTTP {response.status_code}: {response.text}")
                data = response.json()
                return list(data["data"]["embedding"])
            except httpx.HTTPError as e:
                raise Exception(f"HTTP Error: {e}") from e

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        if self.provider == "local":
            return self._local_embed_batch(texts)

        if self.provider == "volcengine" and "vision" in self.model.lower():
            results = []
            for text in texts:
                if not text or not text.strip():
                    results.append([0.0] * 1024)
                else:
                    emb = await self._embed_volcengine_vision(text)
                    results.append(emb)
            return results

        for text in texts:
            if not text or not text.strip():
                raise ValueError("Text cannot be empty for embedding")

        results = []

        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            batch_results = await self._embed_batch_internal(batch)
            results.extend(batch_results)

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

        def text_to_vector(text: str, dim: int = 384) -> list[float]:
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

        response = await client.embeddings.create(
            model=self.model,
            input=texts,
        )

        embeddings = [list(item.embedding) for item in response.data]
        return embeddings

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
