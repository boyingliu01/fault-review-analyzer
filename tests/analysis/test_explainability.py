"""模型可解释性模块测试"""

from pathlib import Path

import numpy as np
import pytest

from src.analysis.explainability import (
    ClusteringExplainabilityAnalyzer,
    ClusteringExplanation,
    ExplainabilityVisualizer,
    FeatureImportance,
    ModelExplanation,
    SHAPResult,
)


@pytest.fixture
def sample_embeddings() -> np.ndarray:
    """生成样本嵌入向量"""
    np.random.seed(42)
    n_samples = 100
    n_features = 20

    X = np.random.randn(n_samples, n_features)
    return X


@pytest.fixture
def sample_labels() -> np.ndarray:
    """生成样本聚类标签"""
    np.random.seed(42)
    n_samples = 100
    labels = np.zeros(n_samples, dtype=int)
    labels[0:30] = 0
    labels[30:60] = 1
    labels[60:90] = 2
    labels[90:] = -1
    return labels


@pytest.fixture
def feature_names() -> list[str]:
    """生成特征名称"""
    return [f"feature_{i}" for i in range(20)]


class TestFeatureImportance:
    """特征重要性测试"""

    def test_feature_importance_creation(self):
        """测试特征重要性创建"""
        feature = FeatureImportance(
            feature_name="test_feature",
            importance=0.85,
            importance_std=0.1,
            shap_value=0.5,
            direction="positive",
        )

        assert feature.feature_name == "test_feature"
        assert feature.importance == 0.85
        assert feature.importance_std == 0.1
        assert feature.shap_value == 0.5
        assert feature.direction == "positive"


class TestSHAPResult:
    """SHAP结果测试"""

    def test_shap_result_creation(self):
        """测试SHAP结果创建"""
        shap_values = np.array([0.1, -0.2, 0.3])
        result = SHAPResult(
            base_value=0.5,
            shap_values=shap_values,
            feature_names=["f1", "f2", "f3"],
            prediction=0.6,
        )

        assert result.base_value == 0.5
        assert np.array_equal(result.shap_values, shap_values)
        assert result.feature_names == ["f1", "f2", "f3"]
        assert result.prediction == 0.6


class TestClusteringExplanation:
    """聚类解释测试"""

    def test_clustering_explanation_creation(self):
        """测试聚类解释创建"""
        features = [
            FeatureImportance(feature_name="f1", importance=0.9),
            FeatureImportance(feature_name="f2", importance=0.7),
        ]

        explanation = ClusteringExplanation(
            cluster_id=1,
            cluster_label="测试聚类",
            top_features=features,
            representative_samples=[0, 1, 2],
            explanation_text="测试解释文本",
        )

        assert explanation.cluster_id == 1
        assert explanation.cluster_label == "测试聚类"
        assert len(explanation.top_features) == 2
        assert explanation.representative_samples == [0, 1, 2]
        assert explanation.explanation_text == "测试解释文本"


class TestModelExplanation:
    """模型解释测试"""

    def test_model_explanation_creation(self):
        """测试模型解释创建"""
        global_features = [
            FeatureImportance(feature_name="f1", importance=0.9),
            FeatureImportance(feature_name="f2", importance=0.8),
        ]

        cluster_exp = ClusteringExplanation(
            cluster_id=0,
            top_features=[global_features[0]],
        )

        explanation = ModelExplanation(
            global_feature_importance=global_features,
            local_explanations={0: cluster_exp},
        )

        assert len(explanation.global_feature_importance) == 2
        assert 0 in explanation.local_explanations


class TestClusteringExplainabilityAnalyzer:
    """聚类可解释性分析器测试"""

    def test_initialization(self):
        """测试初始化"""
        analyzer = ClusteringExplainabilityAnalyzer()
        assert analyzer is not None

    def test_analyze_feature_importance(
        self,
        sample_embeddings: np.ndarray,
        sample_labels: np.ndarray,
        feature_names: list[str],
    ):
        """测试分析特征重要性"""
        analyzer = ClusteringExplainabilityAnalyzer(
            feature_names=feature_names,
        )

        explanation = analyzer.analyze_feature_importance(
            sample_embeddings,
            sample_labels,
            top_n=10,
        )

        assert isinstance(explanation, ModelExplanation)
        assert len(explanation.global_feature_importance) > 0
        assert len(explanation.global_feature_importance) <= 10

        for feature in explanation.global_feature_importance:
            assert feature.feature_name is not None
            assert feature.importance >= 0

    def test_global_importance_sorted(
        self,
        sample_embeddings: np.ndarray,
        sample_labels: np.ndarray,
    ):
        """测试全局重要性排序"""
        analyzer = ClusteringExplainabilityAnalyzer()
        explanation = analyzer.analyze_feature_importance(
            sample_embeddings,
            sample_labels,
            top_n=15,
        )

        importances = [f.importance for f in explanation.global_feature_importance]
        assert importances == sorted(importances, reverse=True)

    def test_cluster_explanations(
        self,
        sample_embeddings: np.ndarray,
        sample_labels: np.ndarray,
    ):
        """测试聚类解释"""
        analyzer = ClusteringExplainabilityAnalyzer()
        explanation = analyzer.analyze_feature_importance(
            sample_embeddings,
            sample_labels,
        )

        unique_labels = np.unique(sample_labels)
        non_noise_labels = unique_labels[unique_labels != -1]

        assert len(explanation.local_explanations) == len(non_noise_labels)

        for cluster_id, cluster_exp in explanation.local_explanations.items():
            assert cluster_exp.cluster_id == cluster_id
            assert len(cluster_exp.top_features) > 0
            assert cluster_exp.explanation_text != ""
            assert len(cluster_exp.representative_samples) > 0

    def test_representative_samples(
        self,
        sample_embeddings: np.ndarray,
        sample_labels: np.ndarray,
    ):
        """测试代表性样本"""
        analyzer = ClusteringExplainabilityAnalyzer()
        explanation = analyzer.analyze_feature_importance(
            sample_embeddings,
            sample_labels,
        )

        for cluster_exp in explanation.local_explanations.values():
            for sample_idx in cluster_exp.representative_samples:
                assert sample_idx >= 0
                assert sample_idx < len(sample_embeddings)

    def test_explanation_text_generation(
        self,
        sample_embeddings: np.ndarray,
        sample_labels: np.ndarray,
    ):
        """测试解释文本生成"""
        analyzer = ClusteringExplainabilityAnalyzer()
        explanation = analyzer.analyze_feature_importance(
            sample_embeddings,
            sample_labels,
        )

        for cluster_exp in explanation.local_explanations.values():
            assert "特征" in cluster_exp.explanation_text
            assert "重要性" in cluster_exp.explanation_text

    def test_noise_cluster_ignored(
        self,
        sample_embeddings: np.ndarray,
    ):
        """测试噪声点被忽略"""
        labels = np.full(len(sample_embeddings), -1)
        analyzer = ClusteringExplainabilityAnalyzer()
        explanation = analyzer.analyze_feature_importance(
            sample_embeddings,
            labels,
        )

        assert len(explanation.local_explanations) == 0


class TestExplainabilityVisualizer:
    """可解释性可视化工具测试"""

    def test_initialization(self, tmp_path: Path):
        """测试初始化"""
        output_dir = tmp_path / "explainability"
        visualizer = ExplainabilityVisualizer(output_dir=output_dir)
        assert visualizer is not None
        assert output_dir.exists()

    def test_plot_feature_importance(self):
        """测试绘制特征重要性图"""
        features = [
            FeatureImportance(
                feature_name=f"feature_{i}",
                importance=0.9 - i * 0.1,
                direction="positive" if i % 2 == 0 else "negative",
            )
            for i in range(10)
        ]

        visualizer = ExplainabilityVisualizer()
        fig = visualizer.plot_feature_importance(
            features,
            title="Test Feature Importance",
            top_n=5,
        )

        if fig is not None:
            assert fig.layout.title.text == "Test Feature Importance"
            assert len(fig.data) == 1

    def test_plot_cluster_comparison(self):
        """测试绘制聚类比较图"""
        explanations = {
            0: ClusteringExplanation(
                cluster_id=0,
                top_features=[
                    FeatureImportance(feature_name="test_feature", importance=0.8)
                ],
            ),
            1: ClusteringExplanation(
                cluster_id=1,
                top_features=[
                    FeatureImportance(feature_name="test_feature", importance=0.5)
                ],
            ),
        }

        visualizer = ExplainabilityVisualizer()
        fig = visualizer.plot_cluster_comparison(explanations, "test_feature")

        if fig is not None:
            assert "test_feature" in fig.layout.title.text

    def test_save_summary_report(
        self,
        tmp_path: Path,
        sample_embeddings: np.ndarray,
        sample_labels: np.ndarray,
    ):
        """测试保存摘要报告"""
        analyzer = ClusteringExplainabilityAnalyzer()
        explanation = analyzer.analyze_feature_importance(
            sample_embeddings,
            sample_labels,
        )

        output_dir = tmp_path / "explainability"
        visualizer = ExplainabilityVisualizer(output_dir=output_dir)

        report_path = tmp_path / "report.html"
        saved_path = visualizer.save_summary_report(explanation, report_path)

        assert Path(saved_path).exists()

        with open(saved_path, encoding="utf-8") as f:
            content = f.read()
            assert "Model Explanation Report" in content
            assert "Global Feature Importance" in content
            assert "Cluster Explanations" in content


class TestWithStructuredData:
    """结构化数据测试"""

    @pytest.fixture
    def structured_embeddings(self) -> np.ndarray:
        """生成有结构的嵌入向量"""
        np.random.seed(42)
        n_samples = 90
        n_features = 10

        X = np.zeros((n_samples, n_features))

        cluster_centers = np.array([
            [1, 1, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 1, 1, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 1, 1, 0, 0, 0, 0],
        ])

        for i in range(n_samples):
            cluster_id = i // 30
            X[i] = cluster_centers[cluster_id] + np.random.randn(n_features) * 0.1

        return X

    @pytest.fixture
    def structured_labels(self) -> np.ndarray:
        """生成结构化标签"""
        labels = np.zeros(90, dtype=int)
        labels[0:30] = 0
        labels[30:60] = 1
        labels[60:90] = 2
        return labels

    def test_structured_data_importance(
        self,
        structured_embeddings: np.ndarray,
        structured_labels: np.ndarray,
    ):
        """测试结构化数据的特征重要性"""
        feature_names = [
            "cluster0_feature1", "cluster0_feature2",
            "cluster1_feature1", "cluster1_feature2",
            "cluster2_feature1", "cluster2_feature2",
            "noise1", "noise2", "noise3", "noise4",
        ]

        analyzer = ClusteringExplainabilityAnalyzer(feature_names=feature_names)
        explanation = analyzer.analyze_feature_importance(
            structured_embeddings,
            structured_labels,
            top_n=10,
        )

        top_feature_names = [f.feature_name for f in explanation.global_feature_importance]

        assert any("cluster0" in name for name in top_feature_names[:5])
        assert any("cluster1" in name for name in top_feature_names[:5])
        assert any("cluster2" in name for name in top_feature_names[:5])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
