"""Phase2 分析 E2E 测试"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.phase2_analyze import Phase2Analyze


def make_mock_config() -> MagicMock:
    """构造最小可用的 ConfigManager mock"""
    config = MagicMock()
    config.clustering.algorithm = "hdbscan"
    config.clustering.min_cluster_size = 2
    config.clustering.min_samples = 1
    config.clustering.metric = "cosine"
    return config


class TestPhase2Analyze:
    """阶段二分析 E2E 测试"""

    @pytest.fixture
    def config(self) -> MagicMock:
        """获取 mock 配置管理器"""
        return make_mock_config()

    @pytest.fixture
    def phase2(self, config: MagicMock) -> Phase2Analyze:
        """创建 Phase2 实例（使用 mock）"""
        with patch("scripts.phase2_analyze.ChromaManager") as mock_chroma, \
             patch("scripts.phase2_analyze.ClusterAnalyzer") as mock_cluster:
            mock_chroma.return_value = MagicMock()
            mock_cluster.return_value = MagicMock()
            return Phase2Analyze(config)

    def test_phase2_init(self, phase2: Phase2Analyze):
        """测试 Phase2 初始化"""
        assert phase2 is not None
        assert phase2.cluster_analyzer is not None

    def test_phase2_load_embeddings_empty(self, phase2: Phase2Analyze):
        """测试加载空的 embeddings"""
        mock_collection = MagicMock()
        mock_collection.get.return_value = {
            "embeddings": [],
            "metadatas": [],
            "documents": [],
        }
        phase2.chroma_manager.get_or_create_collection.return_value = mock_collection

        embeddings, metadatas = phase2.load_embeddings()
        assert len(embeddings) == 0
        assert len(metadatas) == 0

    def test_phase2_load_embeddings_with_data(self, phase2: Phase2Analyze):
        """测试加载带数据的 embeddings"""
        mock_collection = MagicMock()
        mock_collection.get.return_value = {
            "embeddings": [[0.1] * 128, [0.2] * 128],
            "metadatas": [
                {"task_id": "TASK-001", "root_cause": "需求遗漏"},
                {"task_id": "TASK-002", "root_cause": "代码bug"},
            ],
            "documents": ["doc1", "doc2"],
        }
        phase2.chroma_manager.get_or_create_collection.return_value = mock_collection

        embeddings, metadatas = phase2.load_embeddings()
        assert len(embeddings) == 2
        assert len(metadatas) == 2

    def test_phase2_run_with_mock_data(self, phase2: Phase2Analyze):
        """测试完整运行流程（使用 mock 数据）"""
        import numpy as np

        # Mock load_embeddings to return numpy arrays
        phase2.load_embeddings = MagicMock(return_value=(
            np.array([[0.1] * 128, [0.11] * 128, [0.9] * 128]),
            [
                {"task_id": "TASK-001", "root_cause": "需求遗漏"},
                {"task_id": "TASK-002", "root_cause": "需求遗漏"},
                {"task_id": "TASK-003", "root_cause": "代码bug"},
            ],
        ))

        # Mock clustering - return a proper result with numpy array
        mock_cluster_result = MagicMock()
        mock_cluster_result.labels = np.array([0, 0, 1])
        mock_cluster_result.n_clusters = 2
        mock_cluster_result.n_noise = 0
        mock_cluster_result.silhouette_score = 0.75
        phase2.cluster_analyzer.fit_predict.return_value = mock_cluster_result

        result = phase2.run(algorithm="hdbscan")

        assert "clustering" in result
        assert "analysis" in result

    def test_phase2_run_clustering_with_mock(self, phase2: Phase2Analyze):
        """测试聚类分析（使用 mock）"""
        import numpy as np

        mock_embeddings = np.array([[0.1] * 128, [0.11] * 128, [0.9] * 128])

        from src.core.models import ClusteringResult
        mock_result = MagicMock(spec=ClusteringResult)
        mock_result.labels = [0, 0, 1]
        mock_result.n_clusters = 2
        mock_result.n_noise = 0
        mock_result.silhouette_score = 0.75
        mock_result.algorithm = "hdbscan"
        phase2.cluster_analyzer.fit_predict.return_value = mock_result

        result = phase2.run_clustering(mock_embeddings)

        assert result.labels == [0, 0, 1]
        assert result.n_clusters == 2


class TestPhase2GenerateReport:
    """Phase2 报告生成 E2E 测试"""

    @pytest.fixture
    def phase2(self) -> Phase2Analyze:
        """创建带 mock config 的 Phase2Analyze"""
        config = make_mock_config()
        with patch("scripts.phase2_analyze.ChromaManager") as mock_chroma, \
             patch("scripts.phase2_analyze.ClusterAnalyzer") as mock_cluster:
            mock_chroma.return_value = MagicMock()
            mock_cluster.return_value = MagicMock()
            return Phase2Analyze(config)

    def test_generate_report_creates_file(self, phase2: Phase2Analyze, tmp_path: Path):
        """测试报告生成并写入文件"""
        from src.core.models import ClusteringResult

        mock_clustering = MagicMock(spec=ClusteringResult)
        mock_clustering.silhouette_score = 0.75
        mock_clustering.algorithm = "hdbscan"

        analysis_result = {
            "total_tasks": 5,
            "total_clusters": 2,
            "noise_count": 0,
            "violation_count": 1,
            "actionable_count": 1,
            "clusters": {
                0: {
                    "count": 3,
                    "violations": 1,
                    "actionable": 1,
                    "task_ids": ["TASK-001", "TASK-002", "TASK-003"],
                    "root_causes": ["需求遗漏"],
                },
                1: {
                    "count": 2,
                    "violations": 0,
                    "actionable": 0,
                    "task_ids": ["TASK-004", "TASK-005"],
                    "root_causes": ["代码bug"],
                },
            },
        }

        output_file = tmp_path / "report.md"
        content = phase2.generate_report(mock_clustering, analysis_result, str(output_file))

        assert output_file.exists()
        assert len(content) > 0
        assert "cluster" in content.lower() or "聚类" in content
