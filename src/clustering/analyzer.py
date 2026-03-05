from typing import Any

import numpy as np

from src.clustering.models import ClusterInfo, ClusterResult


class ClusterAnalyzer:
    def __init__(
        self,
        algorithm: str = "hdbscan",
        min_cluster_size: int = 3,
        min_samples: int = 2,
        metric: str = "cosine",
    ):
        self.algorithm = algorithm
        self.min_cluster_size = min_cluster_size
        self.min_samples = min_samples
        self.metric = metric
        self._model: Any = None

    def fit_predict(self, embeddings: np.ndarray) -> ClusterResult:
        if embeddings.size == 0:
            raise ValueError("Embeddings cannot be empty")

        if len(embeddings.shape) == 1:
            embeddings = embeddings.reshape(1, -1)

        if self.algorithm == "hdbscan":
            try:
                labels = self._fit_hdbscan(embeddings)
            except ImportError:
                labels = self._fit_sklearn(embeddings)
        else:
            raise ValueError(f"Unknown algorithm: {self.algorithm}")

        clusters = self._build_clusters(labels, embeddings)
        n_noise = sum(1 for label in labels if label == -1)
        n_clusters = len(set(labels) - {-1})

        return ClusterResult(
            labels=labels.tolist(),
            n_clusters=n_clusters,
            n_noise=n_noise,
            clusters=clusters,
        )

    def _fit_hdbscan(self, embeddings: np.ndarray) -> np.ndarray:
        import hdbscan

        if len(embeddings) < self.min_cluster_size:
            return np.array([-1] * len(embeddings))

        embeddings_to_use = embeddings
        if self.metric == "cosine":
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            norms = np.where(norms == 0, 1, norms)
            embeddings_to_use = embeddings / norms

        self._model = hdbscan.HDBSCAN(
            min_cluster_size=self.min_cluster_size,
            min_samples=self.min_samples,
            metric="euclidean",
        )

        result = self._model.fit_predict(embeddings_to_use)
        return np.asarray(result)

    def _fit_sklearn(self, embeddings: np.ndarray) -> np.ndarray:
        from sklearn.cluster import AgglomerativeClustering

        if len(embeddings) < self.min_cluster_size:
            return np.array([-1] * len(embeddings))

        embeddings_to_use = embeddings
        if self.metric == "cosine":
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            norms = np.where(norms == 0, 1, norms)
            embeddings_to_use = embeddings / norms

        n_clusters = max(1, len(embeddings) // self.min_cluster_size)

        self._model = AgglomerativeClustering(
            n_clusters=n_clusters,
            metric="euclidean",
            linkage="ward",
        )

        labels = self._model.fit_predict(embeddings_to_use)
        return np.asarray(labels)

    def _build_clusters(
        self,
        labels: np.ndarray,
        embeddings: np.ndarray,
    ) -> list[ClusterInfo]:
        unique_labels = set(labels) - {-1}
        clusters = []

        for label in unique_labels:
            indices = np.where(labels == label)[0]
            cluster_embeddings = embeddings[indices]

            centroid = np.mean(cluster_embeddings, axis=0)

            clusters.append(
                ClusterInfo(
                    cluster_id=int(label),
                    size=len(indices),
                    centroid=centroid.tolist(),
                    member_indices=indices.tolist(),
                )
            )

        return clusters
