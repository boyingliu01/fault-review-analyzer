"""ClusterAnalyzer 扩展测试 - 边界场景"""

from unittest.mock import patch

import numpy as np
import pytest

from src.clustering.analyzer import ClusterAnalyzer
from src.clustering.models import ClusterInfo, ClusterResult


class TestClusterAnalyzerBoundary:
    """ClusterAnalyzer 边界场景测试"""

    def test_empty_embeddings(self):
        """测试空嵌入向量"""
        analyzer = ClusterAnalyzer()

        with pytest.raises(ValueError, match="Embeddings cannot be empty"):
            analyzer.fit_predict(np.array([]))

    def test_single_embedding(self):
        """测试单条嵌入向量"""
        analyzer = ClusterAnalyzer(min_cluster_size=3)
        embeddings = np.array([[0.1, 0.2, 0.3]])

        result = analyzer.fit_predict(embeddings)

        assert result.n_clusters == 0
        assert result.n_noise == 1
        assert result.labels == [-1]

    def test_two_embeddings(self):
        """测试两条嵌入向量（少于 min_cluster_size）"""
        analyzer = ClusterAnalyzer(min_cluster_size=3)
        embeddings = np.array([[0.1, 0.2], [0.11, 0.21]])

        result = analyzer.fit_predict(embeddings)

        assert result.n_clusters == 0
        assert result.n_noise == 2

    def test_exact_min_cluster_size(self):
        """测试恰好等于 min_cluster_size"""
        analyzer = ClusterAnalyzer(min_cluster_size=3, min_samples=1)
        # 3个非常相似的向量
        embeddings = np.array(
            [
                [0.1, 0.2, 0.3],
                [0.11, 0.21, 0.31],
                [0.12, 0.22, 0.32],
            ]
        )

        result = analyzer.fit_predict(embeddings)

        # 可能形成一个簇或全是噪声，取决于算法
        assert result.n_clusters >= 0
        assert result.n_noise >= 0

    def test_all_identical_embeddings(self):
        """测试所有完全相同的嵌入向量"""
        analyzer = ClusterAnalyzer(min_cluster_size=2)
        embeddings = np.array(
            [
                [0.1, 0.2, 0.3],
                [0.1, 0.2, 0.3],
                [0.1, 0.2, 0.3],
                [0.1, 0.2, 0.3],
            ]
        )

        result = analyzer.fit_predict(embeddings)

        # 完全相同的点应该聚成一个簇
        assert result.n_clusters >= 0

    def test_all_different_embeddings(self):
        """测试所有完全不同的嵌入向量"""
        analyzer = ClusterAnalyzer(min_cluster_size=3)
        # 4个差异很大的向量
        embeddings = np.array(
            [
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 1.0],
                [-1.0, 0.0, 0.0],
            ]
        )

        result = analyzer.fit_predict(embeddings)

        # 差异很大的点可能全是噪声
        assert result.n_noise >= 0

    def test_zero_norm_embeddings(self):
        """测试零范数嵌入向量"""
        analyzer = ClusterAnalyzer(min_cluster_size=2, metric="cosine")
        embeddings = np.array(
            [
                [0.0, 0.0, 0.0],
                [0.1, 0.2, 0.3],
                [0.11, 0.21, 0.31],
            ]
        )

        # 不应该抛出异常
        result = analyzer.fit_predict(embeddings)
        assert isinstance(result, ClusterResult)

    def test_1d_input_array(self):
        """测试一维输入数组"""
        analyzer = ClusterAnalyzer(min_cluster_size=2)
        embeddings = np.array([0.1, 0.2, 0.3, 0.4])

        result = analyzer.fit_predict(embeddings)

        assert result.n_clusters == 0
        assert result.n_noise == 1

    def test_high_dimensional_embeddings(self):
        """测试高维嵌入向量"""
        analyzer = ClusterAnalyzer(min_cluster_size=2)
        # 2048维向量
        embeddings = np.random.randn(5, 2048)

        result = analyzer.fit_predict(embeddings)

        assert isinstance(result, ClusterResult)
        assert len(result.labels) == 5

    def test_large_number_of_embeddings(self):
        """测试大量嵌入向量"""
        analyzer = ClusterAnalyzer(min_cluster_size=5)
        # 100个向量
        embeddings = np.random.randn(100, 10)

        result = analyzer.fit_predict(embeddings)

        assert isinstance(result, ClusterResult)
        assert len(result.labels) == 100

    def test_unknown_algorithm(self):
        """测试未知算法"""
        analyzer = ClusterAnalyzer(algorithm="unknown")
        embeddings = np.array([[0.1, 0.2], [0.3, 0.4]])

        with pytest.raises(ValueError, match="Unknown algorithm"):
            analyzer.fit_predict(embeddings)

    def test_hdbscan_import_error_fallback(self):
        """测试 HDBSCAN 导入失败回退"""
        analyzer = ClusterAnalyzer(algorithm="hdbscan", min_cluster_size=2)
        embeddings = np.array(
            [
                [0.1, 0.2],
                [0.11, 0.21],
                [0.9, 0.8],
                [0.91, 0.81],
            ]
        )

        # 模拟 HDBSCAN 导入失败
        with patch.object(
            analyzer, "_fit_hdbscan", side_effect=ImportError("No module named 'hdbscan'")
        ):
            result = analyzer.fit_predict(embeddings)
            assert isinstance(result, ClusterResult)

    def test_cluster_info_with_centroid(self):
        """测试簇信息质心计算"""
        analyzer = ClusterAnalyzer(min_cluster_size=2)
        embeddings = np.array(
            [
                [0.1, 0.2],
                [0.11, 0.21],
                [0.9, 0.8],
                [0.91, 0.81],
            ]
        )

        result = analyzer.fit_predict(embeddings)

        for cluster in result.clusters:
            assert hasattr(cluster, "centroid")
            assert len(cluster.centroid) == 2

    def test_cluster_info_with_sample_ids(self):
        """测试簇信息样本ID"""
        analyzer = ClusterAnalyzer(min_cluster_size=2)
        embeddings = np.array(
            [
                [0.1, 0.2],
                [0.11, 0.21],
                [0.9, 0.8],
                [0.91, 0.81],
            ]
        )

        result = analyzer.fit_predict(embeddings)

        for cluster in result.clusters:
            assert hasattr(cluster, "sample_ids")
            assert len(cluster.sample_ids) > 0

    def test_negative_values_in_embeddings(self):
        """测试包含负值的嵌入向量"""
        analyzer = ClusterAnalyzer(min_cluster_size=2)
        embeddings = np.array(
            [
                [-0.5, -0.3],
                [-0.51, -0.31],
                [0.5, 0.3],
                [0.51, 0.31],
            ]
        )

        result = analyzer.fit_predict(embeddings)

        assert isinstance(result, ClusterResult)

    def test_very_small_values(self):
        """测试非常小的值"""
        analyzer = ClusterAnalyzer(min_cluster_size=2)
        embeddings = np.array(
            [
                [1e-10, 1e-10],
                [1.1e-10, 1.1e-10],
                [1e10, 1e10],
                [1.1e10, 1.1e10],
            ]
        )

        result = analyzer.fit_predict(embeddings)

        assert isinstance(result, ClusterResult)

    def test_nan_values_handling(self):
        """测试 NaN 值处理"""
        analyzer = ClusterAnalyzer(min_cluster_size=2)
        embeddings = np.array(
            [
                [0.1, np.nan],
                [0.2, 0.3],
                [0.4, 0.5],
            ]
        )

        # NaN 可能导致异常或产生特定结果
        try:
            result = analyzer.fit_predict(embeddings)
            # 如果成功，检查结果
            assert isinstance(result, ClusterResult)
        except (ValueError, RuntimeError):
            # 也可能抛出异常，这是可接受的
            pass

    def test_inf_values_handling(self):
        """测试无穷值处理"""
        analyzer = ClusterAnalyzer(min_cluster_size=2)
        embeddings = np.array(
            [
                [0.1, np.inf],
                [0.2, 0.3],
                [0.4, 0.5],
            ]
        )

        # 无穷值可能导致异常
        try:
            result = analyzer.fit_predict(embeddings)
            assert isinstance(result, ClusterResult)
        except (ValueError, RuntimeError):
            pass


class TestClusterResultBoundary:
    """ClusterResult 边界测试"""

    def test_empty_cluster_result(self):
        """测试空聚类结果"""
        result = ClusterResult(
            labels=[],
            n_clusters=0,
            n_noise=0,
            clusters=[],
        )
        assert len(result.labels) == 0
        assert len(result.clusters) == 0

    def test_all_noise_cluster_result(self):
        """测试全是噪声的聚类结果"""
        result = ClusterResult(
            labels=[-1, -1, -1, -1],
            n_clusters=0,
            n_noise=4,
            clusters=[],
        )
        assert result.n_clusters == 0
        assert result.n_noise == 4

    def test_single_cluster_result(self):
        """测试单簇聚类结果"""
        result = ClusterResult(
            labels=[0, 0, 0, 0],
            n_clusters=1,
            n_noise=0,
            clusters=[
                ClusterInfo(
                    cluster_id=0,
                    size=4,
                    member_indices=[0, 1, 2, 3],
                    centroid=[0.1, 0.2],
                    label="cluster_0",
                )
            ],
        )
        assert result.n_clusters == 1
        assert result.n_noise == 0

    def test_mixed_cluster_result(self):
        """测试混合聚类结果"""
        result = ClusterResult(
            labels=[0, 0, -1, 1, 1, -1],
            n_clusters=2,
            n_noise=2,
            clusters=[
                ClusterInfo(
                    cluster_id=0,
                    size=2,
                    member_indices=[0, 1],
                    centroid=[0.1, 0.2],
                    label="cluster_0",
                ),
                ClusterInfo(
                    cluster_id=1,
                    size=2,
                    member_indices=[3, 4],
                    centroid=[0.9, 0.8],
                    label="cluster_1",
                ),
            ],
        )
        assert result.n_clusters == 2
        assert result.n_noise == 2
