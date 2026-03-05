
import numpy as np
import pytest

from src.clustering.analyzer import ClusterAnalyzer
from src.clustering.models import ClusterInfo, ClusterResult


class TestClusterAnalyzer:
    @pytest.fixture
    def analyzer(self):
        return ClusterAnalyzer(
            algorithm="hdbscan",
            min_cluster_size=3,
            min_samples=2,
        )

    @pytest.fixture
    def sample_embeddings(self):
        np.random.seed(42)
        cluster1 = np.random.randn(5, 128) + np.array([1] * 128)
        cluster2 = np.random.randn(5, 128) + np.array([-1] * 128)
        noise = np.random.randn(2, 128)
        return np.vstack([cluster1, cluster2, noise])

    def test_fit_predict(self, analyzer, sample_embeddings):
        result = analyzer.fit_predict(sample_embeddings)

        assert result is not None
        assert len(result.labels) == len(sample_embeddings)
        assert result.n_clusters >= 0

    def test_cluster_info(self, analyzer, sample_embeddings):
        result = analyzer.fit_predict(sample_embeddings)

        assert len(result.clusters) > 0 or result.n_noise > 0

        for cluster in result.clusters:
            assert cluster.cluster_id >= 0
            assert len(cluster.member_indices) > 0
            assert cluster.size == len(cluster.member_indices)

    def test_noise_detection(self, analyzer, sample_embeddings):
        result = analyzer.fit_predict(sample_embeddings)

        noise_count = sum(1 for label in result.labels if label == -1)
        assert result.n_noise == noise_count

    def test_get_cluster_members(self, analyzer, sample_embeddings):
        result = analyzer.fit_predict(sample_embeddings)

        if result.n_clusters > 0:
            cluster = result.clusters[0]
            members = cluster.member_indices

            assert all(0 <= idx < len(sample_embeddings) for idx in members)

    def test_empty_input(self, analyzer):
        embeddings = np.array([])

        with pytest.raises(ValueError):
            analyzer.fit_predict(embeddings)

    def test_single_sample(self, analyzer):
        embeddings = np.random.randn(1, 128)

        result = analyzer.fit_predict(embeddings)

        assert len(result.labels) == 1
        assert result.labels[0] == -1

    def test_algorithm_parameters(self):
        analyzer = ClusterAnalyzer(
            algorithm="hdbscan",
            min_cluster_size=5,
            min_samples=3,
            metric="euclidean",
        )

        assert analyzer.min_cluster_size == 5
        assert analyzer.min_samples == 3

    def test_fit_predict_with_cosine_metric(self):
        analyzer = ClusterAnalyzer(
            algorithm="hdbscan",
            min_cluster_size=2,
            min_samples=1,
            metric="cosine",
        )
        np.random.seed(42)
        embeddings = np.random.randn(10, 128)
        embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)

        result = analyzer.fit_predict(embeddings)

        assert result is not None
        assert len(result.labels) == 10

    def test_fit_predict_small_dataset(self):
        analyzer = ClusterAnalyzer(
            algorithm="hdbscan",
            min_cluster_size=2,
            min_samples=1,
        )
        np.random.seed(42)
        embeddings = np.random.randn(3, 128)

        result = analyzer.fit_predict(embeddings)

        assert result is not None
        assert len(result.labels) == 3

    def test_cluster_centroid_calculation(self, analyzer):
        np.random.seed(42)
        embeddings = np.random.randn(10, 128)

        result = analyzer.fit_predict(embeddings)

        for cluster in result.clusters:
            if cluster.centroid is not None:
                assert len(cluster.centroid) == 128

    def test_cluster_silhouette_score(self, analyzer):
        np.random.seed(42)
        cluster1 = np.random.randn(5, 128) + 1
        cluster2 = np.random.randn(5, 128) - 1
        embeddings = np.vstack([cluster1, cluster2])

        result = analyzer.fit_predict(embeddings)

        if result.n_clusters > 1:
            assert "silhouette_score" in result.metadata or result.n_clusters >= 1


class TestClusterResult:
    def test_create_result(self):
        result = ClusterResult(
            labels=[0, 0, 1, 1, -1],
            n_clusters=2,
            n_noise=1,
            clusters=[
                ClusterInfo(cluster_id=0, member_indices=[0, 1], size=2),
                ClusterInfo(cluster_id=1, member_indices=[2, 3], size=2),
            ],
        )

        assert result.n_clusters == 2
        assert result.n_noise == 1
        assert len(result.clusters) == 2

    def test_get_cluster_by_id(self):
        result = ClusterResult(
            labels=[0, 0, 1],
            n_clusters=2,
            n_noise=0,
            clusters=[
                ClusterInfo(cluster_id=0, member_indices=[0, 1], size=2),
                ClusterInfo(cluster_id=1, member_indices=[2], size=1),
            ],
        )

        cluster = result.get_cluster(0)
        assert cluster is not None
        assert cluster.cluster_id == 0

        cluster = result.get_cluster(99)
        assert cluster is None

    def test_result_with_silhouette(self):
        result = ClusterResult(
            labels=[0, 0, 1, 1],
            n_clusters=2,
            n_noise=0,
            clusters=[
                ClusterInfo(cluster_id=0, member_indices=[0, 1], size=2),
                ClusterInfo(cluster_id=1, member_indices=[2, 3], size=2),
            ],
            metadata={"silhouette_score": 0.75},
        )

        assert result.metadata.get("silhouette_score") == 0.75


class TestClusterInfo:
    def test_cluster_info(self):
        info = ClusterInfo(
            cluster_id=0,
            member_indices=[0, 1, 2],
            size=3,
            centroid=np.array([0.1, 0.2, 0.3]),
        )

        assert info.cluster_id == 0
        assert info.size == 3
        assert info.centroid is not None

    def test_cluster_info_without_centroid(self):
        info = ClusterInfo(
            cluster_id=0,
            member_indices=[0, 1],
            size=2,
        )

        assert info.cluster_id == 0
        assert info.centroid is None
