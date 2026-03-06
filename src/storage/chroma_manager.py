"""Chroma向量数据库管理器 - 多模态增强版"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import chromadb
from chromadb.config import Settings
from loguru import logger

from src.core.models import EmbeddingResult

if TYPE_CHECKING:
    from pathlib import Path


class ChromaManager:
    """Chroma向量数据库管理器 - 支持多模态向量存储和查询"""

    DEFAULT_COLLECTION = "fault_embeddings"

    def __init__(
        self,
        persist_directory: str | Path | None = None,
    ) -> None:
        self._persist_directory = persist_directory or "./data/chroma"
        self._default_collection = ChromaManager.DEFAULT_COLLECTION
        self._client: Any = None
        self._init_client()

    def _init_client(self) -> None:
        try:
            self._client = chromadb.PersistentClient(
                path=str(self._persist_directory),
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True,
                ),
            )
            logger.info(f"Chroma客户端已初始化，存储路径: {self._persist_directory}")
        except Exception as e:
            logger.error(f"Chroma客户端初始化失败: {e}")
            raise

    def get_or_create_collection(self, collection_name: str = DEFAULT_COLLECTION) -> Any:
        if self._client is None:
            raise RuntimeError("Chroma客户端未初始化")
        return self._client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "故障单向量存储集合"},
        )

    def add_embedding(
        self,
        embedding: EmbeddingResult,
        collection_name: str = DEFAULT_COLLECTION,
    ) -> bool:
        try:
            collection = self.get_or_create_collection(collection_name)

            metadata = {
                "task_id": embedding.task_id,
                "media_type": embedding.media_type,
                "text_length": len(embedding.text),
            }

            if embedding.metadata:
                metadata.update(embedding.metadata)

            collection.add(  # type: ignore[arg-type]
                embeddings=[embedding.embedding],
                documents=[embedding.text],
                metadatas=[metadata],  # type: ignore[arg-type]
                ids=[embedding.task_id],
            )

            logger.info(f"已添加向量: {embedding.task_id}")
            return True

        except Exception as e:
            logger.error(f"添加向量失败: {e}")
            return False

    def add_batch_embeddings(
        self,
        embeddings: list[EmbeddingResult] | list[dict[str, Any]],
        collection_name: str = DEFAULT_COLLECTION,
    ) -> bool:
        try:
            collection = self.get_or_create_collection(collection_name)

            embedding_list = []
            documents = []
            metadatas = []
            ids = []

            for emb in embeddings:
                if isinstance(emb, EmbeddingResult):
                    embedding_list.append(emb.embedding)
                    documents.append(emb.text)
                    metadata = {
                        "task_id": emb.task_id,
                        "media_type": emb.media_type,
                        "text_length": len(emb.text),
                    }
                    if emb.metadata:
                        metadata.update(emb.metadata)
                    metadatas.append(metadata)
                    ids.append(emb.task_id)
                elif isinstance(emb, dict):
                    embedding_list.append(emb.get("embedding", []))
                    documents.append(emb.get("text", ""))
                    metadatas.append(emb.get("metadata", {}))
                    ids.append(emb.get("task_id", f"task_{len(ids)}"))

            collection.add(  # type: ignore[arg-type]
                embeddings=embedding_list,
                documents=documents,
                metadatas=metadatas,  # type: ignore[arg-type]
                ids=ids,
            )

            logger.info(f"批量添加 {len(embeddings)} 个向量")
            return True

        except Exception as e:
            logger.error(f"批量添加向量失败: {e}")
            return False

    def query_similar(
        self,
        collection_name: str = DEFAULT_COLLECTION,
        query_embedding: list[float] | None = None,
        query_text: str | None = None,
        n_results: int = 5,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        try:
            collection = self.get_or_create_collection(collection_name)

            if query_embedding is not None:
                results = collection.query(
                    query_embeddings=[query_embedding],  # type: ignore[arg-type]
                    n_results=n_results,
                    where=where,
                )
            elif query_text is not None:
                results = collection.query(
                    query_texts=[query_text],
                    n_results=n_results,
                    where=where,
                )
            else:
                raise ValueError("必须提供 query_embedding 或 query_text")

            return self._parse_query_results(results)

        except Exception as e:
            logger.error(f"查询相似向量失败: {e}")
            return []

    def _parse_query_results(self, results: Any) -> list[dict[str, Any]]:
        parsed: list[dict[str, Any]] = []
        if not results.get("ids") or not results["ids"][0]:
            return parsed

        for i in range(len(results["ids"][0])):
            parsed.append(
                {
                    "id": results["ids"][0][i],
                    "document": results["documents"][0][i] if results["documents"] else "",
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results.get("distances") else 0.0,
                }
            )

        return parsed

    def get_by_task_id(
        self,
        task_id: str,
        collection_name: str = DEFAULT_COLLECTION,
    ) -> dict[str, Any] | None:
        try:
            collection = self.get_or_create_collection(collection_name)
            result = collection.get(ids=[task_id])

            if not result["ids"]:
                return None

            return {
                "id": result["ids"][0],
                "document": result["documents"][0] if result["documents"] else "",
                "metadata": result["metadatas"][0] if result["metadatas"] else {},
                "embedding": result["embeddings"][0] if result["embeddings"] else [],
            }

        except Exception as e:
            logger.error(f"按task_id查询失败: {e}")
            return None

    def update_metadata(
        self,
        task_id: str,
        metadata: dict[str, Any],
        collection_name: str = DEFAULT_COLLECTION,
    ) -> bool:
        try:
            collection = self.get_or_create_collection(collection_name)
            collection.update(
                ids=[task_id],
                metadatas=[metadata],
            )
            logger.info(f"已更新元数据: {task_id}")
            return True

        except Exception as e:
            logger.error(f"更新元数据失败: {e}")
            return False

    def delete_embedding(
        self,
        task_id: str,
        collection_name: str = DEFAULT_COLLECTION,
    ) -> bool:
        try:
            collection = self.get_or_create_collection(collection_name)
            collection.delete(ids=[task_id])
            logger.info(f"已删除向量: {task_id}")
            return True

        except Exception as e:
            logger.error(f"删除向量失败: {e}")
            return False

    def get_collection_stats(self, collection_name: str = DEFAULT_COLLECTION) -> dict[str, Any]:
        try:
            collection = self.get_or_create_collection(collection_name)
            return {
                "name": collection.name,
                "count": collection.count(),
                "metadata": collection.metadata,
            }
        except Exception as e:
            logger.error(f"获取集合统计失败: {e}")
            return {}

    def list_collections(self) -> list[str]:
        try:
            if self._client is None:
                return []
            return [col.name for col in self._client.list_collections()]
        except Exception as e:
            logger.error(f"列出集合失败: {e}")
            return []

    def delete_collection(self, collection_name: str) -> bool:
        try:
            if self._client is None:
                return False
            self._client.delete_collection(name=collection_name)
            logger.info(f"已删除集合: {collection_name}")
            return True
        except Exception as e:
            logger.error(f"删除集合失败: {e}")
            return False

    def reset(self) -> bool:
        try:
            if self._client is not None:
                self._client.reset()
                logger.warning("Chroma数据库已重置")
            return True
        except Exception as e:
            logger.error(f"重置数据库失败: {e}")
            return False
