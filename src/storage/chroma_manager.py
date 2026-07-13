"""Chroma向量数据库管理器 - 带容错机制的增强版"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import chromadb
from chromadb.config import Settings
from loguru import logger

from src.core.models import EmbeddingResult

if TYPE_CHECKING:
    from collections.abc import Callable


class ChromaDBError(Exception):
    """ChromaDB 操作错误"""

    def __init__(self, message: str, operation: str, cause: Exception | None = None):
        self.message = message
        self.operation = operation
        self.cause = cause
        super().__init__(f"{operation}: {message}")


class ChromaDBConnectionError(ChromaDBError):
    """ChromaDB 连接错误"""

    pass


class ChromaDBWriteError(ChromaDBError):
    """ChromaDB 写入错误"""

    pass


class FallbackCache:
    """本地文件备份缓存 - 用于 ChromaDB 不可用时降级"""

    def __init__(self, cache_dir: Path):
        self._cache_dir = cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._pending_file = self._cache_dir / "pending_writes.jsonl"
        self._pending_lock = None

    def add_pending(
        self,
        task_id: str,
        embedding: list[float],
        text: str,
        metadata: dict[str, Any],
    ) -> bool:
        """将待写入数据保存到本地缓存"""
        try:
            record = {
                "task_id": task_id,
                "embedding": embedding,
                "text": text,
                "metadata": metadata,
                "timestamp": time.time(),
            }
            with self._pending_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            logger.info(f"已缓存待写入数据: {task_id}")
            return True
        except Exception as e:
            logger.error(f"写入本地缓存失败: {e}")
            return False

    def get_pending_count(self) -> int:
        """获取待处理记录数"""
        if not self._pending_file.exists():
            return 0
        try:
            with self._pending_file.open(encoding="utf-8") as f:
                return sum(1 for _ in f)
        except Exception:
            return 0

    def load_pending(self) -> list[dict[str, Any]]:
        """加载所有待处理记录"""
        if not self._pending_file.exists():
            return []
        try:
            records = []
            with self._pending_file.open(encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        records.append(json.loads(line))
            return records
        except Exception as e:
            logger.error(f"加载待处理记录失败: {e}")
            return []

    def clear_pending(self) -> bool:
        """清空待处理记录"""
        try:
            if self._pending_file.exists():
                self._pending_file.unlink()
            return True
        except Exception as e:
            logger.error(f"清空待处理记录失败: {e}")
            return False


class ChromaManager:
    """Chroma向量数据库管理器 - 带容错和降级机制"""

    DEFAULT_COLLECTION = "fault_embeddings"
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0  # seconds

    def __init__(
        self,
        persist_directory: str | Path | None = None,
        enable_fallback: bool = True,
        fallback_dir: str | Path | None = None,
    ) -> None:
        self._persist_directory = Path(persist_directory or "./data/chroma")
        self._default_collection = ChromaManager.DEFAULT_COLLECTION
        self._client: Any = None
        self._enable_fallback = enable_fallback
        self._fallback_cache: FallbackCache | None = None

        if enable_fallback:
            fallback_path = Path(fallback_dir or "./data/chroma_fallback")
            self._fallback_cache = FallbackCache(fallback_path)

        self._connection_healthy = False
        self._last_error: Exception | None = None
        self._init_client()

    def _init_client(self) -> None:
        """初始化 ChromaDB 客户端，支持重试"""
        for attempt in range(self.MAX_RETRIES):
            try:
                self._persist_directory.mkdir(parents=True, exist_ok=True)
                self._client = chromadb.PersistentClient(
                    path=str(self._persist_directory),
                    settings=Settings(
                        anonymized_telemetry=False,
                        allow_reset=True,
                    ),
                )
                # 测试连接
                self._client.heartbeat()
                self._connection_healthy = True
                logger.info(f"Chroma客户端已初始化，存储路径: {self._persist_directory}")
                return
            except Exception as e:
                self._last_error = e
                logger.warning(
                    f"Chroma客户端初始化失败 (尝试 {attempt + 1}/{self.MAX_RETRIES}): {e}"
                )
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY * (attempt + 1))

        self._connection_healthy = False
        logger.error(f"Chroma客户端初始化失败，已用尽重试次数: {self._last_error}")

        if not self._enable_fallback:
            raise ChromaDBConnectionError(
                "Failed to initialize ChromaDB client",
                "init",
                self._last_error,
            )

    def _retry_operation(
        self,
        operation: Callable[[], Any],
        operation_name: str,
        fallback_handler: Callable[[], Any] | None = None,
    ) -> Any:
        """执行带重试的操作

        Args:
            operation: 要执行的操作
            operation_name: 操作名称（用于日志）
            fallback_handler: 降级处理函数

        Returns:
            操作结果

        Raises:
            ChromaDBError: 操作失败且无降级处理
        """
        last_error: Exception | None = None

        for attempt in range(self.MAX_RETRIES):
            try:
                if not self._connection_healthy and attempt == 0:
                    # 尝试重新初始化连接
                    self._init_client()

                result = operation()
                self._connection_healthy = True
                return result

            except Exception as e:
                last_error = e
                self._connection_healthy = False
                logger.warning(
                    f"{operation_name} 失败 (尝试 {attempt + 1}/{self.MAX_RETRIES}): {e}"
                )
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY * (attempt + 1))

        # 所有重试失败，尝试降级
        if fallback_handler and self._enable_fallback:
            logger.warning(f"{operation_name} 降级到本地缓存")
            return fallback_handler()

        raise ChromaDBWriteError(
            f"Operation failed after {self.MAX_RETRIES} retries",
            operation_name,
            last_error,
        )

    def get_or_create_collection(self, collection_name: str = DEFAULT_COLLECTION) -> Any:
        """获取或创建集合"""
        if self._client is None:
            raise ChromaDBConnectionError(
                "ChromaDB client not initialized",
                "get_or_create_collection",
            )
        return self._client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "故障单向量存储集合"},
        )

    def add_embedding(
        self,
        embedding: EmbeddingResult,
        collection_name: str = DEFAULT_COLLECTION,
    ) -> bool:
        """添加单个 embedding，支持降级"""

        def _do_add() -> bool:
            collection = self.get_or_create_collection(collection_name)

            metadata = {
                "task_id": embedding.task_id,
                "media_type": embedding.media_type,
                "text_length": len(embedding.text),
            }

            if embedding.metadata:
                metadata.update(embedding.metadata)

            collection.upsert(
                embeddings=[embedding.embedding],
                documents=[embedding.text],
                metadatas=[metadata],
                ids=[embedding.task_id],
            )

            logger.info(f"已添加向量: {embedding.task_id}")
            return True

        def _fallback_add() -> bool:
            if self._fallback_cache:
                return self._fallback_cache.add_pending(
                    task_id=embedding.task_id,
                    embedding=embedding.embedding,
                    text=embedding.text,
                    metadata={
                        "task_id": embedding.task_id,
                        "media_type": embedding.media_type,
                        **embedding.metadata,
                    },
                )
            return False

        try:
            return self._retry_operation(_do_add, "add_embedding", _fallback_add)
        except ChromaDBError as e:
            logger.error(f"添加向量失败: {e}")
            return False

    def add_batch_embeddings(
        self,
        embeddings: list[EmbeddingResult] | list[dict[str, Any]],
        collection_name: str = DEFAULT_COLLECTION,
    ) -> dict[str, bool]:
        """批量添加 embeddings，返回每个任务的状态

        Returns:
            dict[task_id, bool]: 每个任务的成功/失败状态
        """
        results: dict[str, bool] = {}

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
                    task_id = emb.get("task_id", f"task_{len(ids)}")
                    embedding_list.append(emb.get("embedding", []))
                    documents.append(emb.get("text", ""))
                    metadatas.append(emb.get("metadata", {}))
                    ids.append(task_id)

            def _do_batch_add() -> dict[str, bool]:
                # 执行批量添加
                collection.add(
                    embeddings=embedding_list,
                    documents=documents,
                    metadatas=metadatas,
                    ids=ids,
                )
                logger.info(f"批量添加 {len(ids)} 个向量")
                return dict.fromkeys(ids, True)

            def _fallback_batch_add() -> dict[str, bool]:
                fallback_results = {}
                if self._fallback_cache:
                    for i, id_ in enumerate(ids):
                        success = self._fallback_cache.add_pending(
                            task_id=id_,
                            embedding=embedding_list[i],
                            text=documents[i],
                            metadata=metadatas[i],
                        )
                        fallback_results[id_] = success
                return fallback_results

            return self._retry_operation(_do_batch_add, "add_batch_embeddings", _fallback_batch_add)

        except Exception as e:
            logger.error(f"批量添加向量失败: {e}")
            # 标记所有失败
            for emb in embeddings:
                if isinstance(emb, EmbeddingResult):
                    results[emb.task_id] = False
                elif isinstance(emb, dict):
                    results[emb.get("task_id", "unknown")] = False
            return results

    def add_batch_embeddings_with_detailed_status(
        self,
        embeddings: list[EmbeddingResult] | list[dict[str, Any]],
        collection_name: str = DEFAULT_COLLECTION,
    ) -> dict[str, dict]:
        """批量添加 embeddings，返回详细的状态信息（成功/失败/错误原因）

        Returns:
            dict[task_id, dict]: 每个任务的详细状态
                - success: bool
                - error: str (可选)
                - source: str ("chroma" or "fallback")
        """
        results: dict[str, dict] = {}

        for emb in embeddings:
            try:
                if isinstance(emb, EmbeddingResult):
                    task_id = emb.task_id
                elif isinstance(emb, dict):
                    task_id = emb.get("task_id", f"task_{len(results)}")
                else:
                    task_id = f"task_{len(results)}"

                success = self.add_embedding(emb, collection_name)
                results[task_id] = {
                    "success": success,
                    "source": "chroma" if self._connection_healthy else "fallback",
                }
            except Exception as e:
                results[task_id] = {
                    "success": False,
                    "error": str(e),
                    "source": "failed",
                }
                logger.warning(f"添加任务 {task_id} 失败: {e}")

        return results

    def query_by_metadata(
        self,
        metadata_filters: dict,
        collection_name: str = DEFAULT_COLLECTION,
        n_results: int = 10,
    ) -> list[dict[str, Any]]:
        """根据元数据查询向量

        Args:
            metadata_filters: 元数据过滤条件，例如 {"priority": "high"}
            collection_name: 集合名称
            n_results: 返回结果数量

        Returns:
            查询结果列表
        """
        try:
            collection = self.get_or_create_collection(collection_name)

            where = {}
            for key, value in metadata_filters.items():
                if isinstance(value, list):
                    where[key] = {"$in": value}
                else:
                    where[key] = value

            results = collection.query(
                query_embeddings=None,
                where=where,
                n_results=n_results,
            )

            return self._parse_query_results(results)
        except Exception as e:
            logger.error(f"元数据查询失败: {e}")
            return []

    def sync_pending_writes(self, collection_name: str = DEFAULT_COLLECTION) -> int:
        """同步本地缓存中的待写入数据到 ChromaDB

        Returns:
            成功同步的记录数
        """
        if not self._fallback_cache:
            return 0

        pending = self._fallback_cache.load_pending()
        if not pending:
            return 0

        synced = 0
        remaining = []

        try:
            collection = self.get_or_create_collection(collection_name)

            for record in pending:
                try:
                    collection.upsert(
                        embeddings=[record["embedding"]],
                        documents=[record["text"]],
                        metadatas=[record["metadata"]],
                        ids=[record["task_id"]],
                    )
                    synced += 1
                    logger.info(f"已同步缓存数据: {record['task_id']}")
                except Exception as e:
                    logger.warning(f"同步记录失败: {record['task_id']}: {e}")
                    remaining.append(record)

            # 更新缓存文件
            if synced > 0:
                self._fallback_cache.clear_pending()
                if remaining:
                    for record in remaining:
                        self._fallback_cache.add_pending(**record)

            logger.info(f"同步完成: {synced} 条成功, {len(remaining)} 条待重试")
            return synced

        except Exception as e:
            logger.error(f"同步待写入数据失败: {e}")
            return 0

    def get_pending_count(self) -> int:
        """获取待同步的缓存记录数"""
        if self._fallback_cache:
            return self._fallback_cache.get_pending_count()
        return 0

    def is_healthy(self) -> bool:
        """检查 ChromaDB 连接是否健康"""
        if not self._connection_healthy or self._client is None:
            return False

        try:
            self._client.heartbeat()
            return True
        except Exception:
            return False

    def query_similar(
        self,
        collection_name: str = DEFAULT_COLLECTION,
        query_embedding: list[float] | None = None,
        query_text: str | None = None,
        n_results: int = 5,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """查询相似向量"""
        try:
            collection = self.get_or_create_collection(collection_name)

            if query_embedding is not None:
                results = collection.query(
                    query_embeddings=[query_embedding],
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
        """解析查询结果"""
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
        """按 task_id 获取记录"""
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
        """更新元数据"""
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
        """删除 embedding"""
        try:
            collection = self.get_or_create_collection(collection_name)
            collection.delete(ids=[task_id])
            logger.info(f"已删除向量: {task_id}")
            return True

        except Exception as e:
            logger.error(f"删除向量失败: {e}")
            return False

    def get_collection_stats(self, collection_name: str = DEFAULT_COLLECTION) -> dict[str, Any]:
        """获取集合统计信息"""
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
        """列出所有集合"""
        try:
            if self._client is None:
                return []
            return [col.name for col in self._client.list_collections()]
        except Exception as e:
            logger.error(f"列出集合失败: {e}")
            return []

    def delete_collection(self, collection_name: str) -> bool:
        """删除集合"""
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
        """重置数据库"""
        try:
            if self._client is not None:
                self._client.reset()
                logger.warning("Chroma数据库已重置")
            return True
        except Exception as e:
            logger.error(f"重置数据库失败: {e}")
            return False

    def get_stats(self) -> dict[str, Any]:
        """获取向量数据库统计信息"""
        try:
            collections = self.list_collections()
            total_embeddings = 0

            for col_name in collections:
                try:
                    collection = self.get_or_create_collection(col_name)
                    total_embeddings += collection.count()
                except Exception as e:
                    logger.warning(f"跳过集合 '{col_name}' 统计: {e}")

            return {
                "total_embeddings": total_embeddings,
                "collections": collections,
                "persist_directory": str(self._persist_directory),
                "connection_healthy": self._connection_healthy,
                "pending_writes": self.get_pending_count(),
            }
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {
                "total_embeddings": 0,
                "collections": [],
                "persist_directory": str(self._persist_directory),
                "connection_healthy": False,
                "pending_writes": self.get_pending_count(),
            }
