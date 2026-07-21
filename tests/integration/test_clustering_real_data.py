"""P2 集成测试: 聚类分析使用真实合成数据。

使用可分簇的合成 embedding 数据测试 HDBSCAN / sklearn 聚类算法。
不依赖外部 API。
"""

import numpy as np
import pytest

from src.clustering.analyzer import ClusterAnalyzer
from src.core.models import ClusterResult


def _generate_clustered_data(
    n_clusters: int = 3,
    points_per_cluster: int = 10,
    dim: int = 64,
    separation: float = 5.0,
    seed: int = 42,
) -> np.ndarray:
    """生成具有明确聚类结构的合成数据。"""
    rng = np.random.RandomState(seed)
    clusters = []

    for i in range(n_clusters):
        # 每个聚类的中心在不同方向
        center = np.zeros(dim)
        center[i % dim] = separation * (i + 1)
        # 在中心附近生成点
        points = center + rng.randn(points_per_cluster, dim) * 0.5
        clusters.append(points)

    return np.vstack(clusters)


@pytest.fixture
def clustered_data() -> np.ndarray:
    """生成具有 3 个明确聚类的数据。"""
    return _generate_clustered_data(n_clusters=3, points_per_cluster=15, dim=64)


@pytest.fixture
def small_clustered_data() -> np.ndarray:
    """生成较小的聚类数据集。"""
    return _generate_clustered_data(n_clusters=2, points_per_cluster=5, dim=32)


class TestHDBSCANClustering:
    """测试 HDBSCAN 聚类算法。"""

    def test_hdbscan_finds_clusters(self, clustered_data: np.ndarray):
        """HDBSCAN 应能从合成数据中发现聚类。"""
        analyzer = ClusterAnalyzer(
            algorithm="hdbscan",
            min_cluster_size=5,
            min_samples=3,
            metric="euclidean",
        )

        result = analyzer.fit_predict(clustered_data)

        assert isinstance(result, ClusterResult)
        # 应发现至少 2 个聚类（HDBSCAN 可能不会完美恢复 3 个）
        assert result.n_clusters >= 2
        # 噪声点应该较少（数据分离良好）
        assert result.n_noise < len(clustered_data) * 0.3

    def test_hdbscan_labels_match_data_length(self, clustered_data: np.ndarray):
        """聚类标签数量应与数据点数量一致。"""
        analyzer = ClusterAnalyzer(
            algorithm="hdbscan",
            min_cluster_size=5,
            metric="euclidean",
        )

        result = analyzer.fit_predict(clustered_data)
        assert len(result.labels) == len(clustered_data)

    def test_hdbscan_clusters_have_members(self, clustered_data: np.ndarray):
        """每个发现的聚类应有成员。"""
        analyzer = ClusterAnalyzer(
            algorithm="hdbscan",
            min_cluster_size=5,
            metric="euclidean",
        )

        result = analyzer.fit_predict(clustered_data)

        for cluster in result.clusters:
            assert cluster.size > 0
            assert len(cluster.member_indices) == cluster.size
            assert cluster.centroid is not None
            assert len(cluster.centroid) == clustered_data.shape[1]


class TestSklearnFallbackClustering:
    """测试 sklearn 回退聚类算法。"""

    def test_sklearn_fallback_finds_clusters(self, small_clustered_data: np.ndarray):
        """sklearn 回退算法应能发现聚类。"""
        analyzer = ClusterAnalyzer(
            algorithm="hdbscan",  # 会尝试 hdbscan，失败则回退到 sklearn
            min_cluster_size=3,
            metric="euclidean",
        )

        # 如果 hdbscan 不可用，会回退到 sklearn
        result = analyzer.fit_predict(small_clustered_data)

        assert isinstance(result, ClusterResult)
        assert result.n_clusters >= 1
        assert len(result.labels) == len(small_clustered_data)


class TestClusterResultStructure:
    """测试 ClusterResult 模型结构完整性。"""

    def test_cluster_result_has_all_fields(self, clustered_data: np.ndarray):
        """ClusterResult 应包含所有预期字段。"""
        analyzer = ClusterAnalyzer(
            algorithm="hdbscan",
            min_cluster_size=5,
            metric="euclidean",
        )

        result = analyzer.fit_predict(clustered_data)

        # 检查所有字段存在
        assert hasattr(result, "labels")
        assert hasattr(result, "n_clusters")
        assert hasattr(result, "n_noise")
        assert hasattr(result, "clusters")

        # 检查类型
        assert isinstance(result.labels, list)
        assert isinstance(result.n_clusters, int)
        assert isinstance(result.n_noise, int)
        assert isinstance(result.clusters, list)

    def test_cluster_info_structure(self, clustered_data: np.ndarray):
        """ClusterInfo 应包含所有预期字段。"""
        analyzer = ClusterAnalyzer(
            algorithm="hdbscan",
            min_cluster_size=5,
            metric="euclidean",
        )

        result = analyzer.fit_predict(clustered_data)

        for cluster in result.clusters:
            assert hasattr(cluster, "cluster_id")
            assert hasattr(cluster, "size")
            assert hasattr(cluster, "centroid")
            assert hasattr(cluster, "member_indices")
            assert isinstance(cluster.cluster_id, int)
            assert isinstance(cluster.size, int)
            assert isinstance(cluster.centroid, list)

    def test_get_cluster_method(self, clustered_data: np.ndarray):
        """ClusterResult.get_cluster() 应能按 ID 获取聚类。"""
        analyzer = ClusterAnalyzer(
            algorithm="hdbscan",
            min_cluster_size=5,
            metric="euclidean",
        )

        result = analyzer.fit_predict(clustered_data)

        if result.clusters:
            first_cluster = result.clusters[0]
            found = result.get_cluster(first_cluster.cluster_id)
            assert found is not None
            assert found.cluster_id == first_cluster.cluster_id

        # 不存在的 cluster_id
        not_found = result.get_cluster(9999)
        assert not_found is None


class TestClusteringEdgeCases:
    """测试聚类边界情况。"""

    def test_single_point_raises(self):
        """单个点应抛出异常或返回噪声。"""
        analyzer = ClusterAnalyzer(algorithm="hdbscan", min_cluster_size=3)
        single_point = np.array([[1.0, 2.0, 3.0]])

        # 单点情况：HDBSCAN 会将所有点标记为噪声
        result = analyzer.fit_predict(single_point)
        assert len(result.labels) == 1
        assert result.labels[0] == -1  # 噪声

    def test_empty_raises(self):
        """空数据应抛出异常。"""
        analyzer = ClusterAnalyzer(algorithm="hdbscan")
        empty = np.array([]).reshape(0, 3)

        with pytest.raises(ValueError, match="[Ee]mpty"):
            analyzer.fit_predict(empty)

    def test_cosine_metric(self, clustered_data: np.ndarray):
        """使用余弦度量应能正常工作。"""
        analyzer = ClusterAnalyzer(
            algorithm="hdbscan",
            min_cluster_size=5,
            metric="cosine",
        )

        result = analyzer.fit_predict(clustered_data)
        assert isinstance(result, ClusterResult)
        assert len(result.labels) == len(clustered_data)
