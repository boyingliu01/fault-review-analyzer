"""模型可解释性模块 - 提供SHAP值和特征重要性分析"""

import numpy as np
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from pathlib import Path
from loguru import logger

try:
    import shap
except ImportError:
    shap = None
    logger.warning("SHAP not installed. Some explainability features will be disabled.")

try:
    import matplotlib.pyplot as plt
    import plotly.graph_objects as go
    import plotly.express as px
except ImportError:
    plt = None
    go = None
    px = None
    logger.warning("Plotting libraries not installed. Visualization features will be disabled.")


@dataclass
class FeatureImportance:
    """特征重要性结果"""

    feature_name: str
    importance: float
    importance_std: float = 0.0
    shap_value: float = 0.0
    direction: str = "unknown"


@dataclass
class SHAPResult:
    """SHAP分析结果"""

    base_value: float
    shap_values: np.ndarray
    feature_names: List[str]
    prediction: Optional[float] = None


@dataclass
class ClusteringExplanation:
    """聚类解释"""

    cluster_id: int
    cluster_label: str = ""
    top_features: List[FeatureImportance] = field(default_factory=list)
    representative_samples: List[int] = field(default_factory=list)
    shap_analysis: Optional[SHAPResult] = None
    explanation_text: str = ""
    visualization_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelExplanation:
    """完整模型解释"""

    global_feature_importance: List[FeatureImportance] = field(default_factory=list)
    local_explanations: Dict[int, ClusteringExplanation] = field(default_factory=dict)
    summary_plot_path: Optional[str] = None
    force_plot_paths: Dict[int, str] = field(default_factory=dict)


class SHAPExplainer:
    """SHAP解释器封装"""

    def __init__(
        self,
        model: Optional[Any] = None,
        background_data: Optional[np.ndarray] = None,
        feature_names: Optional[List[str]] = None,
    ):
        if shap is None:
            raise ImportError("SHAP is not installed. Install with: pip install shap")

        self.model = model
        self.background_data = background_data
        self.feature_names = feature_names or []
        self.explainer = None
        self._initialize_explainer()

    def _initialize_explainer(self) -> None:
        """初始化SHAP解释器"""
        try:
            if self.model is not None and self.background_data is not None:
                if hasattr(self.model, "predict_proba"):
                    self.explainer = shap.KernelExplainer(
                        self.model.predict_proba, self.background_data
                    )
                elif hasattr(self.model, "predict"):
                    self.explainer = shap.KernelExplainer(
                        self.model.predict, self.background_data
                    )
                else:
                    self.explainer = shap.KernelExplainer(self.model, self.background_data)
        except Exception as e:
            logger.warning(f"Failed to initialize SHAP explainer: {e}")
            self.explainer = None

    def explain_local(
        self,
        X: np.ndarray,
        nsamples: int = 100,
    ) -> SHAPResult:
        """
        解释单个样本预测

        Args:
            X: 要解释的样本数据
            nsamples: 采样数量

        Returns:
            SHAP分析结果
        """
        if self.explainer is None:
            raise ValueError("Explainer not initialized")

        try:
            shap_values = self.explainer.shap_values(X, nsamples=nsamples)
            base_value = self.explainer.expected_value

            if isinstance(shap_values, list):
                shap_values = shap_values[0]

            return SHAPResult(
                base_value=base_value,
                shap_values=np.array(shap_values),
                feature_names=self.feature_names,
            )
        except Exception as e:
            logger.error(f"Failed to compute local SHAP values: {e}")
            raise

    def explain_global(
        self,
        X: np.ndarray,
        nsamples: int = 100,
    ) -> Tuple[List[FeatureImportance], np.ndarray]:
        """
        全局特征重要性分析

        Args:
            X: 数据集
            nsamples: 采样数量

        Returns:
            (特征重要性列表, SHAP值矩阵)
        """
        if self.explainer is None:
            raise ValueError("Explainer not initialized")

        try:
            shap_values = self.explainer.shap_values(X, nsamples=nsamples)

            if isinstance(shap_values, list):
                shap_values = shap_values[0]

            shap_values = np.array(shap_values)

            feature_importance = self._calculate_feature_importance(shap_values)

            return feature_importance, shap_values
        except Exception as e:
            logger.error(f"Failed to compute global SHAP values: {e}")
            raise

    def _calculate_feature_importance(
        self,
        shap_values: np.ndarray,
    ) -> List[FeatureImportance]:
        """
        计算特征重要性

        Args:
            shap_values: SHAP值矩阵

        Returns:
            特征重要性列表
        """
        mean_abs_shap = np.mean(np.abs(shap_values), axis=0)
        std_shap = np.std(shap_values, axis=0)
        mean_shap = np.mean(shap_values, axis=0)

        features = []
        for i, (mean_abs, std, mean) in enumerate(zip(mean_abs_shap, std_shap, mean_shap)):
            feature_name = self.feature_names[i] if i < len(self.feature_names) else f"feature_{i}"
            direction = "positive" if mean > 0 else "negative"
            features.append(
                FeatureImportance(
                    feature_name=feature_name,
                    importance=float(mean_abs),
                    importance_std=float(std),
                    shap_value=float(mean),
                    direction=direction,
                )
            )

        return sorted(features, key=lambda x: x.importance, reverse=True)


class ClusteringExplainabilityAnalyzer:
    """聚类可解释性分析器"""

    def __init__(
        self,
        embeddings: Optional[np.ndarray] = None,
        labels: Optional[np.ndarray] = None,
        feature_names: Optional[List[str]] = None,
    ):
        self.embeddings = embeddings
        self.labels = labels
        self.feature_names = feature_names or []
        self.shap_explainer: Optional[SHAPExplainer] = None

    def analyze_feature_importance(
        self,
        embeddings: Optional[np.ndarray] = None,
        labels: Optional[np.ndarray] = None,
        top_n: int = 10,
    ) -> ModelExplanation:
        """
        分析聚类特征重要性

        Args:
            embeddings: 嵌入向量
            labels: 聚类标签
            top_n: 保留的重要特征数量

        Returns:
            模型解释结果
        """
        X = embeddings if embeddings is not None else self.embeddings
        y = labels if labels is not None else self.labels

        if X is None or y is None:
            raise ValueError("Embeddings and labels must be provided")

        explanation = ModelExplanation()

        explanation.global_feature_importance = self._calculate_global_importance(X, y, top_n)
        explanation.local_explanations = self._calculate_cluster_explanations(X, y, top_n)

        return explanation

    def _calculate_global_importance(
        self,
        X: np.ndarray,
        y: np.ndarray,
        top_n: int,
    ) -> List[FeatureImportance]:
        """计算全局特征重要性"""
        importance_scores = np.zeros(X.shape[1])

        unique_labels = np.unique(y)
        unique_labels = unique_labels[unique_labels != -1]

        for label in unique_labels:
            cluster_data = X[y == label]
            other_data = X[y != label]

            if len(cluster_data) == 0 or len(other_data) == 0:
                continue

            for i in range(X.shape[1]):
                diff = np.abs(np.mean(cluster_data[:, i]) - np.mean(other_data[:, i]))
                importance_scores[i] += diff

        importance_scores /= max(len(unique_labels), 1)

        features = []
        for i, score in enumerate(importance_scores):
            feature_name = self.feature_names[i] if i < len(self.feature_names) else f"feature_{i}"
            features.append(
                FeatureImportance(
                    feature_name=feature_name,
                    importance=float(score),
                    direction="positive" if score > 0 else "neutral",
                )
            )

        return sorted(features, key=lambda x: x.importance, reverse=True)[:top_n]

    def _calculate_cluster_explanations(
        self,
        X: np.ndarray,
        y: np.ndarray,
        top_n: int,
    ) -> Dict[int, ClusteringExplanation]:
        """计算各个聚类的解释"""
        explanations = {}

        unique_labels = np.unique(y)
        unique_labels = unique_labels[unique_labels != -1]

        for cluster_id in unique_labels:
            cluster_mask = y == cluster_id
            cluster_data = X[cluster_mask]
            other_data = X[~cluster_mask]

            top_features = self._get_cluster_feature_importance(
                cluster_data, other_data, top_n
            )

            rep_indices = self._find_representative_samples(cluster_data)

            explanation = ClusteringExplanation(
                cluster_id=int(cluster_id),
                top_features=top_features,
                representative_samples=[int(i) for i in rep_indices],
                explanation_text=self._generate_explanation_text(top_features),
            )

            explanations[int(cluster_id)] = explanation

        return explanations

    def _get_cluster_feature_importance(
        self,
        cluster_data: np.ndarray,
        other_data: np.ndarray,
        top_n: int,
    ) -> List[FeatureImportance]:
        """获取单个聚类的特征重要性"""
        importance_scores = []

        for i in range(cluster_data.shape[1]):
            cluster_mean = np.mean(cluster_data[:, i])
            other_mean = np.mean(other_data[:, i])
            diff = np.abs(cluster_mean - other_mean)
            cluster_std = np.std(cluster_data[:, i])

            feature_name = self.feature_names[i] if i < len(self.feature_names) else f"feature_{i}"
            direction = "positive" if cluster_mean > other_mean else "negative"

            importance_scores.append(
                FeatureImportance(
                    feature_name=feature_name,
                    importance=float(diff),
                    importance_std=float(cluster_std),
                    shap_value=float(cluster_mean - other_mean),
                    direction=direction,
                )
            )

        return sorted(importance_scores, key=lambda x: x.importance, reverse=True)[:top_n]

    def _find_representative_samples(
        self,
        cluster_data: np.ndarray,
        n_samples: int = 3,
    ) -> np.ndarray:
        """找到聚类中的代表性样本（靠近中心的样本）"""
        if len(cluster_data) <= n_samples:
            return np.arange(len(cluster_data))

        center = np.mean(cluster_data, axis=0)
        distances = np.linalg.norm(cluster_data - center, axis=1)
        return np.argsort(distances)[:n_samples]

    def _generate_explanation_text(self, top_features: List[FeatureImportance]) -> str:
        """生成解释文本"""
        if not top_features:
            return "没有足够的特征用于解释。"

        text = "该聚类主要由以下特征驱动：\n"
        for i, feature in enumerate(top_features[:5]):
            direction_text = "正向" if feature.direction == "positive" else "负向"
            text += f"{i+1}. {feature.feature_name} (重要性: {feature.importance:.4f}, {direction_text})\n"

        return text


class ExplainabilityVisualizer:
    """可解释性可视化工具"""

    def __init__(self, output_dir: Path = Path("./output/explainability")):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def plot_feature_importance(
        self,
        features: List[FeatureImportance],
        title: str = "Feature Importance",
        top_n: int = 15,
    ) -> Optional[Any]:
        """
        绘制特征重要性图

        Args:
            features: 特征重要性列表
            title: 图表标题
            top_n: 显示的特征数量

        Returns:
            Plotly图表对象
        """
        if go is None:
            logger.warning("Plotly not installed. Cannot create visualization.")
            return None

        display_features = features[:top_n]

        fig = go.Figure(
            data=[
                go.Bar(
                    x=[f.importance for f in display_features],
                    y=[f.feature_name for f in display_features],
                    orientation="h",
                    marker_color=[
                        "#2ECC71" if f.direction == "positive" else "#E74C3C"
                        for f in display_features
                    ],
                )
            ]
        )

        fig.update_layout(
            title=title,
            xaxis_title="Importance",
            yaxis_title="Feature",
            yaxis=dict(autorange="reversed"),
            height=min(400, len(display_features) * 30 + 100),
        )

        return fig

    def plot_cluster_comparison(
        self,
        explanations: Dict[int, ClusteringExplanation],
        feature_name: str,
    ) -> Optional[Any]:
        """
        绘制聚类比较图

        Args:
            explanations: 聚类解释字典
            feature_name: 要比较的特征名称

        Returns:
            Plotly图表对象
        """
        if go is None:
            return None

        cluster_ids = []
        importances = []

        for cluster_id, explanation in explanations.items():
            for feature in explanation.top_features:
                if feature.feature_name == feature_name:
                    cluster_ids.append(f"Cluster {cluster_id}")
                    importances.append(feature.importance)
                    break

        fig = go.Figure(
            data=[
                go.Bar(
                    x=cluster_ids,
                    y=importances,
                    marker_color="#3498DB",
                )
            ]
        )

        fig.update_layout(
            title=f"Feature: {feature_name} across clusters",
            xaxis_title="Cluster",
            yaxis_title="Importance",
        )

        return fig

    def save_summary_report(
        self,
        explanation: ModelExplanation,
        output_path: Optional[Path] = None,
    ) -> str:
        """
        保存摘要报告

        Args:
            explanation: 模型解释结果
            output_path: 输出路径

        Returns:
            报告文件路径
        """
        if output_path is None:
            output_path = self.output_dir / "explanation_report.html"

        content = self._generate_html_report(explanation)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        return str(output_path)

    def _generate_html_report(self, explanation: ModelExplanation) -> str:
        """生成HTML报告"""
        html_parts = [
            "<html>",
            "<head><title>Model Explanation Report</title>",
            "<style>",
            "body { font-family: Arial, sans-serif; margin: 20px; }",
            "h1 { color: #2c3e50; }",
            "h2 { color: #34495e; margin-top: 30px; }",
            "table { border-collapse: collapse; width: 100%; margin: 15px 0; }",
            "th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }",
            "th { background-color: #f2f2f2; }",
            ".cluster { border: 1px solid #ddd; padding: 15px; margin: 15px 0; border-radius: 5px; }",
            "</style>",
            "</head>",
            "<body>",
            "<h1>Model Explanation Report</h1>",
            "<h2>Global Feature Importance</h2>",
            self._feature_table_to_html(explanation.global_feature_importance),
            "<h2>Cluster Explanations</h2>",
        ]

        for cluster_id, cluster_exp in explanation.local_explanations.items():
            html_parts.append(f'<div class="cluster">')
            html_parts.append(f"<h3>Cluster {cluster_id}</h3>")
            html_parts.append(f"<p><strong>Explanation:</strong> {cluster_exp.explanation_text}</p>")
            html_parts.append("<h4>Top Features:</h4>")
            html_parts.append(self._feature_table_to_html(cluster_exp.top_features))
            html_parts.append(f"<p><strong>Representative samples:</strong> {cluster_exp.representative_samples}</p>")
            html_parts.append("</div>")

        html_parts.extend(["</body>", "</html>"])

        return "\n".join(html_parts)

    def _feature_table_to_html(self, features: List[FeatureImportance]) -> str:
        """将特征列表转换为HTML表格"""
        if not features:
            return "<p>No features available.</p>"

        html = ["<table><thead><tr>", "<th>Feature</th>", "<th>Importance</th>", "<th>Direction</th>"]

        if any(f.importance_std > 0 for f in features):
            html.append("<th>Std Dev</th>")

        html.append("</tr></thead><tbody>")

        for feature in features:
            html.append(f"<tr>")
            html.append(f"<td>{feature.feature_name}</td>")
            html.append(f"<td>{feature.importance:.6f}</td>")
            html.append(f"<td>{feature.direction}</td>")
            if any(f.importance_std > 0 for f in features):
                html.append(f"<td>{feature.importance_std:.6f}</td>")
            html.append("</tr>")

        html.append("</tbody></table>")
        return "".join(html)
