"""聚类散点图可视化测试套件"""

import pytest

from src.visualization.cluster_scatter import ClusterScatterVisualizer


class TestClusterScatterVisualizer:
    """聚类散点图可视化器测试套件"""

    def test_create_visualizer(self):
        """测试创建可视化器"""
        viz = ClusterScatterVisualizer()
        assert viz is not None

    def test_prepare_data(self):
        """测试数据准备"""
        viz = ClusterScatterVisualizer(n_neighbors=5)

        # 使用更多数据点避免UMAP错误
        embeddings = [[0.1 * i] * 2048 for i in range(10)]
        labels = [0, 0, 0, 1, 1, 1, 2, 2, 2, -1]
        task_ids = [f"TASK-{i:03d}" for i in range(1, 11)]

        result = viz.prepare_data(embeddings, labels, task_ids)

        assert "embeddings_2d" in result
        assert "labels" in result
        assert "task_ids" in result
        assert len(result["embeddings_2d"]) == 10
        assert result["embeddings_2d"].shape[1] == 2

    def test_prepare_data_with_metadata(self):
        """测试带元数据的数据准备"""
        viz = ClusterScatterVisualizer()

        embeddings = [[0.1] * 2048 for _ in range(5)]
        labels = [0, 0, 1, 1, -1]
        task_ids = [f"TASK-{i:03d}" for i in range(1, 6)]
        metadata = [
            {"root_cause": "需求遗漏", "is_violation": True},
            {"root_cause": "设计缺陷", "is_violation": False},
            {"root_cause": "代码bug", "is_violation": True},
            {"root_cause": "配置错误", "is_violation": False},
            {"root_cause": "其他", "is_violation": False},
        ]

        result = viz.prepare_data(embeddings, labels, task_ids, metadata)

        assert "metadata" in result
        assert len(result["metadata"]) == 5

    def test_create_scatter_plot(self, tmp_path):
        """测试创建散点图"""
        viz = ClusterScatterVisualizer()

        embeddings = [[0.1 * i] * 2048 for i in range(10)]
        labels = [0, 0, 0, 1, 1, 1, 2, 2, 2, -1]
        task_ids = [f"TASK-{i:03d}" for i in range(1, 11)]

        data = viz.prepare_data(embeddings, labels, task_ids)

        output_path = tmp_path / "scatter_plot.html"
        result = viz.create_scatter_plot(
            data,
            title="测试聚类散点图",
            output_path=str(output_path),
        )

        assert result is True
        assert output_path.exists()

    def test_create_scatter_plot_with_noise(self, tmp_path):
        """测试包含噪声点的散点图"""
        viz = ClusterScatterVisualizer()

        embeddings = [[0.1 * i] * 2048 for i in range(8)]
        labels = [0, 0, 1, 1, -1, -1, -1, -1]  # 4个噪声点
        task_ids = [f"TASK-{i:03d}" for i in range(1, 9)]

        data = viz.prepare_data(embeddings, labels, task_ids)

        output_path = tmp_path / "scatter_with_noise.html"
        result = viz.create_scatter_plot(data, output_path=str(output_path))

        assert result is True
        assert output_path.exists()

    def test_create_interactive_plot(self, tmp_path):
        """测试创建交互式散点图"""
        viz = ClusterScatterVisualizer()

        embeddings = [[0.1 * i] * 2048 for i in range(6)]
        labels = [0, 0, 1, 1, 2, 2]
        task_ids = [f"TASK-{i:03d}" for i in range(1, 7)]
        metadata = [{"root_cause": f"根因{i}", "is_violation": i % 2 == 0} for i in range(6)]

        data = viz.prepare_data(embeddings, labels, task_ids, metadata)

        output_path = tmp_path / "interactive_scatter.html"
        result = viz.create_scatter_plot(
            data,
            title="交互式聚类散点图",
            output_path=str(output_path),
            show_hover=True,
        )

        assert result is True

    def test_empty_embeddings(self):
        """测试空向量数据"""
        viz = ClusterScatterVisualizer()

        with pytest.raises(ValueError):
            viz.prepare_data([], [], [])

    def test_mismatched_lengths(self):
        """测试长度不匹配的数据"""
        viz = ClusterScatterVisualizer()

        embeddings = [[0.1] * 2048 for _ in range(3)]
        labels = [0, 1]  # 长度不匹配
        task_ids = ["TASK-001", "TASK-002", "TASK-003"]

        with pytest.raises(ValueError):
            viz.prepare_data(embeddings, labels, task_ids)

    def test_single_cluster(self, tmp_path):
        """测试单聚类情况"""
        viz = ClusterScatterVisualizer()

        embeddings = [[0.1] * 2048 for _ in range(5)]
        labels = [0, 0, 0, 0, 0]  # 只有一个聚类
        task_ids = [f"TASK-{i:03d}" for i in range(1, 6)]

        data = viz.prepare_data(embeddings, labels, task_ids)

        output_path = tmp_path / "single_cluster.html"
        result = viz.create_scatter_plot(data, output_path=str(output_path))

        assert result is True
