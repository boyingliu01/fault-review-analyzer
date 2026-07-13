"""聚类分析模块测试"""

import numpy as np

from src.analysis.clustering import (
    ClusteringAnalyzer,
    _prepare_embeddings,
)
from src.clustering.models import ClusterResult


class TestPrepareEmbeddings:
    """嵌入向量准备测试"""

    def test_prepare_embeddings(self):
        """测试准备嵌入向量"""
        embeddings = [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]
        result = _prepare_embeddings(embeddings)

        assert isinstance(result, np.ndarray)
        assert result.shape == (3, 2)

    def test_prepare_embeddings_empty(self):
        """测试空嵌入向量"""
        result = _prepare_embeddings([])

        assert isinstance(result, np.ndarray)
        assert len(result) == 0


class TestClusteringAnalyzer:
    """聚类分析器测试"""

    def test_create_analyzer(self):
        """测试创建分析器"""
        analyzer = ClusteringAnalyzer()
        assert analyzer is not None

    def test_cluster_hdbscan(self):
        """测试 HDBSCAN 聚类"""
        analyzer = ClusteringAnalyzer()

        # 创建测试数据 - 两个明显的簇
        embeddings = [
            [0.1] * 10,
            [0.11] * 10,
            [0.12] * 10,
            [0.9] * 10,
            [0.91] * 10,
            [0.92] * 10,
        ]

        result = analyzer.cluster_hdbscan(
            embeddings,
            min_cluster_size=2,
            min_samples=1,
        )

        assert isinstance(result, ClusterResult)
        assert result.metadata.get("algorithm") == "hdbscan"
        assert result.n_clusters >= 1
        assert len(result.labels) == 6

    def test_cluster_hdbscan_empty(self):
        """测试 HDBSCAN 空数据"""
        analyzer = ClusteringAnalyzer()
        result = analyzer.cluster_hdbscan([])

        assert result.n_clusters == 0
        assert result.n_noise == 0
        assert len(result.labels) == 0

    def test_cluster_kmeans(self):
        """测试 K-Means 聚类"""
        analyzer = ClusteringAnalyzer()

        embeddings = [
            [0.1] * 10,
            [0.11] * 10,
            [0.9] * 10,
            [0.91] * 10,
        ]

        result = analyzer.cluster_kmeans(embeddings, n_clusters=2)

        assert isinstance(result, ClusterResult)
        assert result.metadata.get("algorithm") == "kmeans"
        assert result.n_clusters == 2
        assert len(result.labels) == 4
        assert result.n_noise == 0  # K-Means 没有噪声点

    def test_cluster_kmeans_empty(self):
        """测试 K-Means 空数据"""
        analyzer = ClusteringAnalyzer()
        result = analyzer.cluster_kmeans([])

        assert result.n_clusters == 0
        assert len(result.labels) == 0

    def test_cluster_hierarchical(self):
        """测试层次聚类"""
        analyzer = ClusteringAnalyzer()

        embeddings = [
            [0.1] * 10,
            [0.11] * 10,
            [0.9] * 10,
            [0.91] * 10,
        ]

        result = analyzer.cluster_hierarchical(embeddings, n_clusters=2)

        assert isinstance(result, ClusterResult)
        assert result.metadata.get("algorithm") == "hierarchical"
        assert result.n_clusters == 2
        assert len(result.labels) == 4

    def test_cluster_hierarchical_empty(self):
        """测试层次聚类空数据"""
        analyzer = ClusteringAnalyzer()
        result = analyzer.cluster_hierarchical([])

        assert result.n_clusters == 0
        assert len(result.labels) == 0

    def test_analyze_clusters(self):
        """测试聚类结果分析"""
        analyzer = ClusteringAnalyzer()

        labels = [0, 0, 1, 1, -1]
        metadatas = [
            {"task_id": "T1", "root_cause": "需求遗漏"},
            {"task_id": "T2", "root_cause": "需求遗漏"},
            {"task_id": "T3", "root_cause": "代码bug"},
            {"task_id": "T4", "root_cause": "代码bug"},
            {"task_id": "T5", "root_cause": "其他"},
        ]

        analysis = analyzer.analyze_clusters(labels, metadatas)

        assert analysis["n_clusters"] == 2
        assert analysis["n_noise"] == 1
        assert 0 in analysis["clusters"]
        assert 1 in analysis["clusters"]

        # 检查簇 0
        cluster_0 = analysis["clusters"][0]
        assert cluster_0["size"] == 2
        assert cluster_0["most_common_root_cause"] == "需求遗漏"

    def test_analyze_clusters_empty(self):
        """测试空聚类分析"""
        analyzer = ClusteringAnalyzer()
        analysis = analyzer.analyze_clusters([], [])

        assert analysis == {}

    def test_cluster_kmeans_adjust_clusters(self):
        """测试 K-Means 自动调整簇数量"""
        analyzer = ClusteringAnalyzer()

        # 只有 3 个样本，但请求 5 个簇
        embeddings = [[0.1] * 10, [0.2] * 10, [0.3] * 10]

        result = analyzer.cluster_kmeans(embeddings, n_clusters=5)

        # 应该自动调整为 3 个簇
        assert result.n_clusters == 3
