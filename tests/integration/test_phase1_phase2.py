"""阶段一和阶段二集成测试"""

from unittest.mock import AsyncMock, MagicMock, patch

from scripts.phase1_prepare import Phase1Prepare
from scripts.phase2_analyze import Phase2Analyze


def make_mock_config() -> MagicMock:
    """构造最小可用的 ConfigManager mock"""
    config = MagicMock()
    config.embedding.provider = "volcengine"
    config.embedding.model = "doubao-embedding-vision-251215"
    config.embedding.api_key = "test-key"
    config.embedding.base_url = "https://example.com"
    config.clustering.algorithm = "hdbscan"
    config.clustering.min_cluster_size = 2
    config.clustering.min_samples = 1
    config.clustering.metric = "cosine"
    return config


class TestPhase1Phase2Integration:
    """阶段一和阶段二集成测试"""

    async def test_phase1_to_phase2_flow(self):
        """测试阶段一到阶段二的完整流程（mock 内部组件）"""
        from src.core.models import EmbeddingResult

        mock_result = EmbeddingResult(
            task_id="TASK-001",
            embedding=[0.1] * 1536,
            text="测试文本",
            media_type="text",
            metadata={"title": "测试故障"},
        )

        with (
            patch("scripts.phase1_prepare.EnhancedLLMAnalyzer"),
            patch("scripts.phase1_prepare.EmbeddingGenerator"),
            patch("scripts.phase1_prepare.ChromaManager"),
            patch("scripts.phase1_prepare.StandardsManager"),
            patch("scripts.phase1_prepare.CodeChangeAnalyzer"),
        ):
            config = make_mock_config()
            phase1 = Phase1Prepare(config)
            # 直接 mock process_single_task 避免依赖网络
            phase1.process_single_task = AsyncMock(return_value=mock_result)

            results = await phase1.run(task_ids=["TASK-001"], use_llm=False)

            assert len(results) == 1
            assert results[0].task_id == "TASK-001"

    def test_phase2_load_embeddings(self):
        """测试阶段二加载阶段一的向量数据"""
        with patch("scripts.phase2_analyze.ChromaManager") as mock_chroma:
            mock_collection = MagicMock()
            mock_collection.get.return_value = {
                "embeddings": [[0.1] * 1536, [0.2] * 1536],
                "metadatas": [
                    {"task_id": "TASK-001", "root_cause": "需求遗漏"},
                    {"task_id": "TASK-002", "root_cause": "代码bug"},
                ],
                "documents": ["doc1", "doc2"],
            }
            mock_chroma_instance = MagicMock()
            mock_chroma_instance.get_or_create_collection.return_value = mock_collection
            mock_chroma.return_value = mock_chroma_instance

            phase2 = Phase2Analyze(make_mock_config())
            embeddings, metadatas = phase2.load_embeddings()

            assert len(embeddings) == 2
            assert len(metadatas) == 2
            assert metadatas[0]["task_id"] == "TASK-001"

    def test_phase2_clustering_with_data(self):
        """测试阶段二对真实数据进行聚类"""
        with patch("scripts.phase2_analyze.ChromaManager") as mock_chroma:
            mock_collection = MagicMock()
            mock_collection.get.return_value = {
                "embeddings": [[0.1] * 1536, [0.11] * 1536, [0.9] * 1536, [0.91] * 1536],
                "metadatas": [
                    {"task_id": "TASK-001", "root_cause": "需求遗漏"},
                    {"task_id": "TASK-002", "root_cause": "需求遗漏"},
                    {"task_id": "TASK-003", "root_cause": "代码bug"},
                    {"task_id": "TASK-004", "root_cause": "代码bug"},
                ],
                "documents": ["d1", "d2", "d3", "d4"],
            }
            mock_chroma_instance = MagicMock()
            mock_chroma_instance.get_or_create_collection.return_value = mock_collection
            mock_chroma.return_value = mock_chroma_instance

            # ClusterAnalyzer 是 phase2 实际使用的类
            with patch("scripts.phase2_analyze.ClusterAnalyzer") as mock_cls:
                mock_analyzer = MagicMock()
                mock_fit_result = MagicMock()
                mock_fit_result.labels = [0, 0, 1, 1]
                mock_fit_result.n_clusters = 2
                mock_fit_result.n_noise = 0
                mock_fit_result.silhouette_score = 0.65
                mock_fit_result.algorithm = "hdbscan"
                mock_fit_result.model_dump.return_value = {
                    "labels": [0, 0, 1, 1],
                    "n_clusters": 2,
                    "n_noise": 0,
                    "silhouette_score": 0.65,
                    "algorithm": "hdbscan",
                }
                mock_analyzer.fit.return_value = mock_fit_result
                mock_cls.return_value = mock_analyzer

                phase2 = Phase2Analyze(make_mock_config())
                result = phase2.run(algorithm="hdbscan")

                assert "clustering" in result
                assert "analysis" in result


class TestPhase2GenerateReport:
    """测试 Phase2Analyze.generate_report 报告生成逻辑"""

    def _make_phase2(self) -> Phase2Analyze:
        """构造带 mock config 和 mock ChromaManager 的 Phase2Analyze"""
        with patch("scripts.phase2_analyze.ChromaManager"):
            return Phase2Analyze(make_mock_config())

    def test_generate_report_truncates_long_task_id_list(self, tmp_path):
        """超过10个task_id时，报告应显示截断提示行"""
        from src.core.models import ClusteringResult

        phase2 = self._make_phase2()

        mock_clustering = MagicMock(spec=ClusteringResult)
        mock_clustering.silhouette_score = 0.75
        mock_clustering.algorithm = "hdbscan"

        analysis_result = {
            "total_tasks": 15,
            "total_clusters": 1,
            "noise_count": 0,
            "violation_count": 3,
            "actionable_count": 2,
            "clusters": {
                0: {
                    "count": 15,
                    "violations": 3,
                    "actionable": 2,
                    "task_ids": [f"TASK-{i:03d}" for i in range(15)],
                    "root_causes": [],
                }
            },
        }

        output_file = tmp_path / "report.md"
        content = phase2.generate_report(mock_clustering, analysis_result, str(output_file))

        assert "(共 15 个)" in content
        assert "TASK-000" in content
        assert "TASK-009" in content
        # 第11个以后的不应直接出现（被截断至前10个）
        assert "TASK-010" not in content

    def test_generate_report_no_truncation_for_small_cluster(self, tmp_path):
        """不超过10个task_id时，不显示截断提示行"""
        from src.core.models import ClusteringResult

        phase2 = self._make_phase2()

        mock_clustering = MagicMock(spec=ClusteringResult)
        mock_clustering.silhouette_score = 0.5
        mock_clustering.algorithm = "kmeans"

        analysis_result = {
            "total_tasks": 3,
            "total_clusters": 1,
            "noise_count": 0,
            "violation_count": 0,
            "actionable_count": 0,
            "clusters": {
                0: {
                    "count": 3,
                    "violations": 0,
                    "actionable": 0,
                    "task_ids": ["TASK-001", "TASK-002", "TASK-003"],
                    "root_causes": [],
                }
            },
        }

        output_file = tmp_path / "report.md"
        content = phase2.generate_report(mock_clustering, analysis_result, str(output_file))

        assert "(共 3 个)" not in content


class TestEndToEndWorkflow:
    """端到端工作流测试（纯接口协议验证，不依赖真实组件）"""

    async def test_full_analysis_workflow(self):
        """验证阶段一和阶段二的接口协议"""
        mock_phase1 = MagicMock(spec=Phase1Prepare)
        mock_phase1.run = AsyncMock(
            return_value=[
                {"task_id": "TASK-001", "root_cause": "需求遗漏"},
            ]
        )

        mock_phase2 = MagicMock(spec=Phase2Analyze)
        mock_phase2.run.return_value = {
            "clustering": {"n_clusters": 1, "labels": [0]},
            "analysis": {"total_tasks": 1},
        }

        phase1_result = await mock_phase1.run(task_ids=["TASK-001"])
        assert len(phase1_result) == 1
        assert phase1_result[0]["task_id"] == "TASK-001"
        mock_phase1.run.assert_called_once_with(task_ids=["TASK-001"])

        phase2_result = mock_phase2.run(algorithm="hdbscan")
        assert "clustering" in phase2_result
        assert "analysis" in phase2_result
        mock_phase2.run.assert_called_once_with(algorithm="hdbscan")
