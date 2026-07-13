"""聚类分析模块"""

from __future__ import annotations

from typing import Any

import hdbscan
import numpy as np
from loguru import logger
from sklearn.cluster import AgglomerativeClustering, KMeans

from src.clustering.models import ClusterInfo, ClusterResult


def _prepare_embeddings(embeddings: list[list[float]]) -> np.ndarray:
    """准备嵌入向量"""
    if not embeddings:
        return np.array([])
    return np.array(embeddings)


class ClusteringAnalyzer:
    """聚类分析器"""

    def cluster_hdbscan(
        self,
        embeddings: list[list[float]],
        min_cluster_size: int = 3,
        min_samples: int = 2,
        metric: str = "euclidean",
    ) -> ClusterResult:
        """使用 HDBSCAN 进行聚类

        Args:
            embeddings: 嵌入向量列表
            min_cluster_size: 最小簇大小
            min_samples: 最小样本数
            metric: 距离度量

        Returns:
            聚类结果
        """
        try:
            X = _prepare_embeddings(embeddings)

            if len(X) == 0:
                return ClusterResult(
                    labels=[],
                    n_clusters=0,
                    n_noise=0,
                    clusters=[],
                    metadata={"algorithm": "hdbscan", "params": {}},
                )

            # 调整参数以适应数据量
            min_cluster_size = min(min_cluster_size, len(X))
            min_samples = min(min_samples, len(X) - 1) if len(X) > 1 else 1

            clusterer = hdbscan.HDBSCAN(
                min_cluster_size=min_cluster_size,
                min_samples=min_samples,
                metric=metric,
            )

            labels = clusterer.fit_predict(X)
            labels_list = labels.tolist()

            n_clusters = len(set(labels_list)) - (1 if -1 in labels_list else 0)
            n_noise = sum(1 for label in labels_list if label == -1)

            logger.info(f"HDBSCAN 聚类完成: {n_clusters} 个簇, {n_noise} 个噪声点")

            # 构建聚类信息
            clusters = self._build_cluster_info(labels_list, X)

            return ClusterResult(
                labels=labels_list,
                n_clusters=n_clusters,
                n_noise=n_noise,
                clusters=clusters,
                metadata={
                    "algorithm": "hdbscan",
                    "params": {
                        "min_cluster_size": min_cluster_size,
                        "min_samples": min_samples,
                        "metric": metric,
                    },
                },
            )

        except Exception as e:
            logger.error(f"HDBSCAN 聚类失败: {e}")
            raise

    def cluster_kmeans(
        self,
        embeddings: list[list[float]],
        n_clusters: int = 5,
        random_state: int = 42,
    ) -> ClusterResult:
        """使用 K-Means 进行聚类

        Args:
            embeddings: 嵌入向量列表
            n_clusters: 簇数量
            random_state: 随机种子

        Returns:
            聚类结果
        """
        try:
            X = _prepare_embeddings(embeddings)

            if len(X) == 0:
                return ClusterResult(
                    labels=[],
                    n_clusters=0,
                    n_noise=0,
                    clusters=[],
                    metadata={"algorithm": "kmeans", "params": {}},
                )

            # 调整簇数量
            n_clusters = min(n_clusters, len(X))

            kmeans = KMeans(
                n_clusters=n_clusters,
                random_state=random_state,
                n_init=10,
            )

            labels = kmeans.fit_predict(X)
            labels_list = labels.tolist()

            logger.info(f"K-Means 聚类完成: {n_clusters} 个簇")

            # 构建聚类信息
            clusters = self._build_cluster_info(labels_list, X)

            return ClusterResult(
                labels=labels_list,
                n_clusters=n_clusters,
                n_noise=0,
                clusters=clusters,
                metadata={
                    "algorithm": "kmeans",
                    "params": {
                        "n_clusters": n_clusters,
                        "random_state": random_state,
                    },
                },
            )

        except Exception as e:
            logger.error(f"K-Means 聚类失败: {e}")
            raise

    def cluster_hierarchical(
        self,
        embeddings: list[list[float]],
        n_clusters: int = 5,
        metric: str = "euclidean",
        linkage: str = "ward",
    ) -> ClusterResult:
        """使用层次聚类

        Args:
            embeddings: 嵌入向量列表
            n_clusters: 簇数量
            metric: 距离度量
            linkage: 连接方式

        Returns:
            聚类结果
        """
        try:
            X = _prepare_embeddings(embeddings)

            if len(X) == 0:
                return ClusterResult(
                    labels=[],
                    n_clusters=0,
                    n_noise=0,
                    clusters=[],
                    metadata={"algorithm": "hierarchical", "params": {}},
                )

            # 调整簇数量
            n_clusters = min(n_clusters, len(X))

            # ward 连接需要欧氏距离
            if linkage == "ward" and metric != "euclidean":
                metric = "euclidean"

            clusterer = AgglomerativeClustering(
                n_clusters=n_clusters,
                metric=metric,
                linkage=linkage,
            )

            labels = clusterer.fit_predict(X)
            labels_list = labels.tolist()

            logger.info(f"层次聚类完成: {n_clusters} 个簇")

            # 构建聚类信息
            clusters = self._build_cluster_info(labels_list, X)

            return ClusterResult(
                labels=labels_list,
                n_clusters=n_clusters,
                n_noise=0,
                clusters=clusters,
                metadata={
                    "algorithm": "hierarchical",
                    "params": {
                        "n_clusters": n_clusters,
                        "metric": metric,
                        "linkage": linkage,
                    },
                },
            )

        except Exception as e:
            logger.error(f"层次聚类失败: {e}")
            raise

    def _build_cluster_info(
        self,
        labels: list[int],
        embeddings: np.ndarray,
    ) -> list[ClusterInfo]:
        """构建聚类信息列表

        Args:
            labels: 聚类标签列表
            embeddings: 嵌入向量数组

        Returns:
            聚类信息列表
        """
        unique_labels = set(labels) - {-1}
        clusters = []

        for label in unique_labels:
            indices = [i for i, lbl in enumerate(labels) if lbl == label]
            cluster_embeddings = embeddings[indices]

            centroid = np.mean(cluster_embeddings, axis=0)

            clusters.append(
                ClusterInfo(
                    cluster_id=int(label),
                    size=len(indices),
                    centroid=centroid.tolist(),
                    member_indices=indices,
                )
            )

        return clusters

    def analyze_clusters(
        self,
        labels: list[int],
        metadatas: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """分析聚类结果

        Args:
            labels: 聚类标签
            metadatas: 元数据列表

        Returns:
            分析结果
        """
        if not labels or not metadatas:
            return {}

        clusters: dict[int, list[dict[str, Any]]] = {}

        for idx, label in enumerate(labels):
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(metadatas[idx])

        analysis: dict[str, Any] = {
            "n_clusters": len(set(labels)) - (1 if -1 in labels else 0),
            "n_noise": sum(1 for label in labels if label == -1),
            "clusters": {},
        }

        for cluster_id, items in clusters.items():
            if cluster_id == -1:
                continue

            # 统计该簇的根因
            root_causes: dict[str, int] = {}
            for item in items:
                cause = item.get("root_cause", "未知")
                root_causes[cause] = root_causes.get(cause, 0) + 1

            # 找出最常见的根因
            if not root_causes:
                most_common_cause = "未知"
            else:
                most_common_cause = max(root_causes.items(), key=lambda x: x[1])[0]

            analysis["clusters"][cluster_id] = {
                "size": len(items),
                "most_common_root_cause": most_common_cause,
                "root_cause_distribution": root_causes,
                "task_ids": [item.get("task_id", "未知") for item in items],
            }

        return analysis
