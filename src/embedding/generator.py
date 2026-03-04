
import numpy as np

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
        self._client = None
        self._dimension_map = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }

    def _get_client(self):
        if self._client is None and self.provider == "openai":
            import openai

            self._client = openai.AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        return self._client

    async def embed_text(self, text: str) -> list[float]:
        if not text or not text.strip():
            raise ValueError("Text cannot be empty for embedding")

        client = self._get_client()

        response = await client.embeddings.create(
            model=self.model,
            input=text,
        )

        return list(response.data[0].embedding)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        for text in texts:
            if not text or not text.strip():
                raise ValueError("Text cannot be empty for embedding")

        results = []

        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            batch_results = await self._embed_batch_internal(batch)
            results.extend(batch_results)

        return results

    async def _embed_batch_internal(self, texts: list[str]) -> list[list[float]]:
        client = self._get_client()

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
            results.append(EmbeddingResult(
                task_id=task.get("task_id", i),
                embedding=embedding,
                model=self.model,
                metadata={"text_length": len(task.get(text_field, ""))},
            ))

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
        return np.dot(normalized, normalized.T)
