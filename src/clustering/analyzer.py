
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
        self._model = None

    def fit_predict(self, embeddings: np.ndarray) -> ClusterResult:
        if embeddings.size == 0:
            raise ValueError("Embeddings cannot be empty")

        if len(embeddings.shape) == 1:
            embeddings = embeddings.reshape(1, -1)

        if self.algorithm == "hdbscan":
            labels = self._fit_hdbscan(embeddings)
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

        return self._model.fit_predict(embeddings_to_use)

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

            cluster = ClusterInfo(
                cluster_id=int(label),
                member_indices=indices.tolist(),
                size=len(indices),
                centroid=centroid.tolist(),
            )
            clusters.append(cluster)

        return sorted(clusters, key=lambda c: c.size, reverse=True)

    def get_cluster_members(
        self,
        cluster_id: int,
        labels: np.ndarray,
    ) -> list[int]:
        return np.where(labels == cluster_id)[0].tolist()

    def compute_cluster_quality(
        self,
        embeddings: np.ndarray,
        labels: np.ndarray,
    ) -> dict:
        from sklearn.metrics import calinski_harabasz_score, silhouette_score

        valid_mask = labels != -1
        valid_embeddings = embeddings[valid_mask]
        valid_labels = labels[valid_mask]

        if len(set(valid_labels)) < 2:
            return {
                "silhouette_score": None,
                "calinski_harabasz_score": None,
            }

        silhouette = silhouette_score(valid_embeddings, valid_labels)
        calinski = calinski_harabasz_score(valid_embeddings, valid_labels)

        return {
            "silhouette_score": float(silhouette),
            "calinski_harabasz_score": float(calinski),
        }
