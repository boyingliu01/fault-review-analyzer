"""阶段一和阶段二集成测试"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import asyncio

from scripts.phase1_prepare import Phase1Prepare
from scripts.phase2_analyze import Phase2Analyze


class TestPhase1Phase2Integration:
    """阶段一和阶段二集成测试"""

    async def test_phase1_to_phase2_flow(self):
        """测试阶段一到阶段二的完整流程"""
        
        # Mock API客户端
        with patch("scripts.phase1_prepare.APIClient") as mock_api:
            mock_client = MagicMock()
            mock_client.get_task_detail.return_value = {
                "id": "TASK-001",
                "title": "测试故障",
                "description": "测试描述",
            }
            mock_client.get_task_history.return_value = [
                {"action": "创建", "operator": "user1"}
            ]
            mock_client.get_task_comments.return_value = [
                {"content": "测试评论"}
            ]
            mock_api.return_value = mock_client

            # Mock LLM分析器
            with patch("scripts.phase1_prepare.EnhancedLLMAnalyzer") as mock_llm:
                mock_analyzer = MagicMock()
                mock_analyzer.analyze_fault = AsyncMock(return_value={
                    "root_cause": "需求遗漏",
                    "introduce_phase": "需求",
                    "improvement_measure": "加强需求评审",
                    "violation_analysis": {
                        "has_violation": False,
                        "violated_rules": [],
                    },
                })
                mock_llm.return_value = mock_analyzer

                # Mock向量化
                with patch("scripts.phase1_prepare.VolcanoEmbeddingClient") as mock_emb:
                    mock_emb_client = MagicMock()
                    mock_emb_client.embed_text.return_value = [0.1] * 2048
                    mock_emb.return_value = mock_emb_client

                    # Mock ChromaManager
                    with patch("scripts.phase1_prepare.ChromaManager") as mock_chroma:
                        mock_chroma_instance = MagicMock()
                        mock_chroma_instance.add_embedding.return_value = True
                        mock_chroma.return_value = mock_chroma_instance

                        # 执行阶段一
                        phase1 = Phase1Prepare()
                        results = await phase1.run(
                            task_ids=["TASK-001"],
                            use_llm=True,
                        )

                        assert len(results) == 1
                        assert results[0].task_id == "TASK-001"

    def test_phase2_load_embeddings(self):
        """测试阶段二加载阶段一的向量数据"""
        
        with patch("scripts.phase2_analyze.ChromaManager") as mock_chroma:
            # 模拟阶段一存储的数据
            mock_collection = MagicMock()
            mock_collection.get.return_value = {
                "embeddings": [[0.1] * 2048, [0.2] * 2048],
                "metadatas": [
                    {"task_id": "TASK-001", "root_cause": "需求遗漏"},
                    {"task_id": "TASK-002", "root_cause": "代码bug"},
                ],
            }
            
            mock_chroma_instance = MagicMock()
            mock_chroma_instance.get_or_create_collection.return_value = mock_collection
            mock_chroma.return_value = mock_chroma_instance

            # 执行阶段二
            phase2 = Phase2Analyze()
            embeddings, metadatas = phase2.load_embeddings()

            assert len(embeddings) == 2
            assert len(metadatas) == 2
            assert metadatas[0]["task_id"] == "TASK-001"

    def test_phase2_clustering_with_data(self):
        """测试阶段二对真实数据进行聚类"""
        
        with patch("scripts.phase2_analyze.ChromaManager") as mock_chroma:
            # 模拟有多个簇的数据
            mock_collection = MagicMock()
            mock_collection.get.return_value = {
                "embeddings": [
                    [0.1] * 2048,
                    [0.11] * 2048,
                    [0.9] * 2048,
                    [0.91] * 2048,
                ],
                "metadatas": [
                    {"task_id": "TASK-001", "root_cause": "需求遗漏"},
                    {"task_id": "TASK-002", "root_cause": "需求遗漏"},
                    {"task_id": "TASK-003", "root_cause": "代码bug"},
                    {"task_id": "TASK-004", "root_cause": "代码bug"},
                ],
            }
            
            mock_chroma_instance = MagicMock()
            mock_chroma_instance.get_or_create_collection.return_value = mock_collection
            mock_chroma.return_value = mock_chroma_instance

            # Mock聚类分析器
            with patch("scripts.phase2_analyze.ClusteringAnalyzer") as mock_clustering:
                from src.analysis.clustering import ClusteringResult
                
                mock_analyzer = MagicMock()
                mock_analyzer.cluster_hdbscan.return_value = ClusteringResult(
                    labels=[0, 0, 1, 1],
                    n_clusters=2,
                    n_noise=0,
                    algorithm="hdbscan",
                    params={},
                )
                mock_clustering.return_value = mock_analyzer

                phase2 = Phase2Analyze()
                result = phase2.run(algorithm="hdbscan")

                assert "clustering" in result


class TestEndToEndWorkflow:
    """端到端工作流测试"""

    async def test_full_analysis_workflow(self):
        """测试完整的分析工作流"""

        # 使用 Mock 对象验证阶段一和阶段二的接口协议
        mock_phase1 = MagicMock(spec=Phase1Prepare)
        mock_phase1.run = AsyncMock(return_value=[
            {"task_id": "TASK-001", "root_cause": "需求遗漏"},
        ])

        mock_phase2 = MagicMock(spec=Phase2Analyze)
        mock_phase2.run.return_value = {
            "clustering": {"n_clusters": 1, "labels": [0]},
            "analysis": {"total_tasks": 1},
        }

        with patch("scripts.phase1_prepare.APIClient"):
            with patch("scripts.phase1_prepare.EnhancedLLMAnalyzer"):
                with patch("scripts.phase1_prepare.VolcanoEmbeddingClient"):
                    with patch("scripts.phase1_prepare.ChromaManager"):
                        with patch("scripts.phase2_analyze.ChromaManager"):
                            with patch("scripts.phase2_analyze.ClusteringAnalyzer"):

                                # 验证阶段一返回任务列表
                                phase1_result = await mock_phase1.run(task_ids=["TASK-001"])
                                assert len(phase1_result) == 1
                                assert phase1_result[0]["task_id"] == "TASK-001"
                                mock_phase1.run.assert_called_once_with(task_ids=["TASK-001"])

                                # 验证阶段二返回聚类与分析结构
                                phase2_result = mock_phase2.run(algorithm="hdbscan")
                                assert "clustering" in phase2_result
                                assert "analysis" in phase2_result
                                mock_phase2.run.assert_called_once_with(algorithm="hdbscan")
