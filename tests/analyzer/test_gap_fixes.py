"""Tests for GAP fixes G1-G4 (functional GAP analysis remediation).

Covers:
- G1: run_clustering persists embeddings to ChromaDB
- G2: run_clustering generates semantic cluster labels
- G3: AnalyzeHandler.analyze_root_cause_deep runs real deep root cause analysis
- G4: run_single produces improvement recommendations
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.analysis.root_cause.models import ExistingFaultAnalysis
from src.analyzer.pipeline import AnalysisPipeline, PipelineConfig
from src.api.models import TaskInfo


def _make_task(task_id: int, title: str = "Task") -> TaskInfo:
    return TaskInfo(
        task_id=task_id,
        title=title,
        description=f"Description {task_id}",
        status="open",
        priority="medium",
        create_time=datetime.now(),
    )


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.api = MagicMock()
    config.api.base_url = "https://api.example.com"
    config.llm = MagicMock()
    config.llm.api_key = ""
    config.llm.model = "gpt-4"
    config.llm.base_url = ""
    config.llm.temperature = 0.7
    config.llm.max_tokens = 4096
    config.embedding = MagicMock()
    config.embedding.provider = "openai"
    config.embedding.model = "text-embedding-3-small"
    config.embedding.api_key = ""
    config.embedding.base_url = ""
    config.embedding.batch_size = 100
    config.clustering = MagicMock()
    config.clustering.algorithm = "hdbscan"
    config.clustering.min_cluster_size = 2
    config.clustering.min_samples = 1
    config.clustering.metric = "cosine"
    config.cache = MagicMock()
    config.cache.db_path = "./data/cache/test.db"
    config.cache.ttl = 3600
    return config


# --- G1: ChromaDB embedding persistence ---


class TestChromaPersistence:
    @pytest.mark.asyncio
    async def test_run_clustering_persists_embeddings(self, mock_config):
        """G1: run_clustering stores embeddings to ChromaDB via _store_cluster_embeddings."""
        pipeline = AnalysisPipeline(
            config=mock_config,
            pipeline_config=PipelineConfig(use_llm=False),
        )
        mock_tasks = [_make_task(1), _make_task(2)]

        mock_emb_gen = MagicMock()
        mock_emb_gen.embed_batch = AsyncMock(return_value=[[0.1] * 128, [0.2] * 128])

        mock_cluster = MagicMock()
        mock_cluster.fit_predict.return_value = MagicMock(labels=[0, 0])

        mock_chroma = MagicMock()
        mock_chroma.add_batch_embeddings.return_value = {"1": True, "2": True}

        with (
            patch.object(pipeline, "_fetch_task", new_callable=AsyncMock) as mock_fetch,
            patch.object(pipeline, "_get_embedding_generator", return_value=mock_emb_gen),
            patch.object(pipeline, "_get_cluster_analyzer", return_value=mock_cluster),
            patch.object(pipeline, "_get_chroma_manager", return_value=mock_chroma),
        ):
            mock_fetch.side_effect = lambda tid: next(
                (t for t in mock_tasks if t.task_id == tid), None
            )
            result = await pipeline.run_clustering([1, 2])

        mock_chroma.add_batch_embeddings.assert_called_once()
        assert result["embeddings_stored"] == 2

    @pytest.mark.asyncio
    async def test_run_clustering_skips_storage_when_disabled(self, mock_config):
        """G1: store_embeddings=False skips ChromaDB persistence."""
        pipeline = AnalysisPipeline(
            config=mock_config,
            pipeline_config=PipelineConfig(use_llm=False, store_embeddings=False),
        )
        mock_tasks = [_make_task(1), _make_task(2)]

        mock_emb_gen = MagicMock()
        mock_emb_gen.embed_batch = AsyncMock(return_value=[[0.1] * 128, [0.2] * 128])
        mock_cluster = MagicMock()
        mock_cluster.fit_predict.return_value = MagicMock(labels=[0, 0])
        mock_chroma = MagicMock()

        with (
            patch.object(pipeline, "_fetch_task", new_callable=AsyncMock) as mock_fetch,
            patch.object(pipeline, "_get_embedding_generator", return_value=mock_emb_gen),
            patch.object(pipeline, "_get_cluster_analyzer", return_value=mock_cluster),
            patch.object(pipeline, "_get_chroma_manager", return_value=mock_chroma),
        ):
            mock_fetch.side_effect = lambda tid: next(
                (t for t in mock_tasks if t.task_id == tid), None
            )
            result = await pipeline.run_clustering([1, 2])

        mock_chroma.add_batch_embeddings.assert_not_called()
        assert result["embeddings_stored"] == 0

    @pytest.mark.asyncio
    async def test_run_clustering_chroma_unavailable_degrades(self, mock_config):
        """G1: ChromaDB unavailable → clustering still succeeds (graceful degradation)."""
        pipeline = AnalysisPipeline(
            config=mock_config,
            pipeline_config=PipelineConfig(use_llm=False),
        )
        mock_tasks = [_make_task(1), _make_task(2)]

        mock_emb_gen = MagicMock()
        mock_emb_gen.embed_batch = AsyncMock(return_value=[[0.1] * 128, [0.2] * 128])
        mock_cluster = MagicMock()
        mock_cluster.fit_predict.return_value = MagicMock(labels=[0, 0])

        with (
            patch.object(pipeline, "_fetch_task", new_callable=AsyncMock) as mock_fetch,
            patch.object(pipeline, "_get_embedding_generator", return_value=mock_emb_gen),
            patch.object(pipeline, "_get_cluster_analyzer", return_value=mock_cluster),
            patch.object(pipeline, "_get_chroma_manager", return_value=None),
        ):
            mock_fetch.side_effect = lambda tid: next(
                (t for t in mock_tasks if t.task_id == tid), None
            )
            result = await pipeline.run_clustering([1, 2])

        assert "tasks" in result
        assert result["embeddings_stored"] == 0


# --- G2: Cluster semantic labels ---


class TestClusterLabels:
    @pytest.mark.asyncio
    async def test_run_clustering_generates_cluster_labels(self, mock_config):
        """G2: run_clustering produces cluster_labels for non-noise clusters."""
        mock_config.llm.api_key = "test-key"
        pipeline = AnalysisPipeline(
            config=mock_config,
            pipeline_config=PipelineConfig(use_llm=True, generate_labels=True),
        )
        mock_tasks = [_make_task(1), _make_task(2)]

        mock_emb_gen = MagicMock()
        mock_emb_gen.embed_batch = AsyncMock(return_value=[[0.1] * 128, [0.2] * 128])
        mock_cluster = MagicMock()
        mock_cluster.fit_predict.return_value = MagicMock(labels=[0, 0])

        mock_label_gen = MagicMock()
        mock_label_gen.is_available = True
        mock_result = MagicMock()
        mock_result.summary = "数据库问题"
        mock_result.labels = []
        mock_label_gen.generate_for_cluster = AsyncMock(return_value=mock_result)

        with (
            patch.object(pipeline, "_fetch_task", new_callable=AsyncMock) as mock_fetch,
            patch.object(pipeline, "_get_embedding_generator", return_value=mock_emb_gen),
            patch.object(pipeline, "_get_cluster_analyzer", return_value=mock_cluster),
            patch.object(pipeline, "_get_chroma_manager", return_value=None),
            patch.object(pipeline, "_label_generator", mock_label_gen, create=True),
        ):
            mock_fetch.side_effect = lambda tid: next(
                (t for t in mock_tasks if t.task_id == tid), None
            )
            result = await pipeline.run_clustering([1, 2])

        assert result["cluster_labels"] == {0: "数据库问题"}
        mock_label_gen.generate_for_cluster.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_clustering_no_llm_skips_labels(self, mock_config):
        """G2: use_llm=False → no cluster labels generated."""
        pipeline = AnalysisPipeline(
            config=mock_config,
            pipeline_config=PipelineConfig(use_llm=False),
        )
        mock_tasks = [_make_task(1), _make_task(2)]

        mock_emb_gen = MagicMock()
        mock_emb_gen.embed_batch = AsyncMock(return_value=[[0.1] * 128, [0.2] * 128])
        mock_cluster = MagicMock()
        mock_cluster.fit_predict.return_value = MagicMock(labels=[0, 0])

        with (
            patch.object(pipeline, "_fetch_task", new_callable=AsyncMock) as mock_fetch,
            patch.object(pipeline, "_get_embedding_generator", return_value=mock_emb_gen),
            patch.object(pipeline, "_get_cluster_analyzer", return_value=mock_cluster),
            patch.object(pipeline, "_get_chroma_manager", return_value=None),
        ):
            mock_fetch.side_effect = lambda tid: next(
                (t for t in mock_tasks if t.task_id == tid), None
            )
            result = await pipeline.run_clustering([1, 2])

        assert result["cluster_labels"] == {}


# --- G3: Deep root cause analysis ---


class TestDeepRootCauseHandler:
    @pytest.mark.asyncio
    async def test_analyze_root_cause_deep_runs_real_analysis(self):
        """G3: analyze_root_cause_deep runs DeepRootCauseAnalyzer, not a placeholder."""
        from src.analyzer.handlers.analyze import AnalyzeHandler

        mock_provider = MagicMock()
        mock_api = MagicMock()
        mock_api.get_fault_analysis = AsyncMock(
            return_value={
                "apiDevTaskAnalysis": {"catalog": "开发", "conclusion": "结论"},
                "apiTestTaskAnalysis": {},
            }
        )
        handler = AnalyzeHandler(llm_provider=mock_provider, api_client=mock_api)

        mock_deep = MagicMock()
        from src.analysis.root_cause.models import RootCauseAnalysisResult

        mock_deep.analyze = AsyncMock(
            return_value=RootCauseAnalysisResult(
                problem_category="并发问题",
                initial_cause="竞态条件",
                deep_root_causes=[],
                actionable_improvements=[],
                checklist_recommendations=["补充并发场景测试"],
            )
        )

        with patch.object(handler, "_get_deep_root_cause_analyzer", return_value=mock_deep):
            result = await handler.analyze_root_cause_deep(
                {"task_no": "12345", "title": "并发故障", "description": "描述"}
            )

        assert result["problem_category"] == "并发问题"
        assert result["checklist_recommendations"] == ["补充并发场景测试"]
        mock_api.get_fault_analysis.assert_called_once_with("12345")

    @pytest.mark.asyncio
    async def test_analyze_root_cause_deep_no_provider_returns_empty(self):
        """G3: no LLM provider → empty dict, no crash."""
        from src.analyzer.handlers.analyze import AnalyzeHandler

        handler = AnalyzeHandler(llm_provider=None)
        result = await handler.analyze_root_cause_deep({"task_no": "12345"})
        assert result == {}

    def test_convert_api_to_existing_analysis(self):
        """G3: API data converts to ExistingFaultAnalysis."""
        from src.analyzer.handlers.analyze import AnalyzeHandler

        handler = AnalyzeHandler(llm_provider=None)
        result = handler._convert_api_to_existing_analysis(
            {
                "apiDevTaskAnalysis": {"catalog": "开发", "reason": "原因"},
                "apiTestTaskAnalysis": {"catalog": "测试"},
            }
        )
        assert isinstance(result, ExistingFaultAnalysis)
        assert result.dev_catalog == "开发"
        assert result.test_catalog == "测试"


# --- G4: Improvement recommendations ---


class TestImprovements:
    @pytest.mark.asyncio
    async def test_run_single_generates_improvements(self, mock_config):
        """G4: run_single populates improvements from root causes."""
        mock_config.llm.api_key = "test-key"
        pipeline = AnalysisPipeline(
            config=mock_config,
            pipeline_config=PipelineConfig(
                use_llm=True,
                generate_labels=False,
                analyze_root_cause=True,
                check_rules=False,
                generate_report=False,
            ),
        )

        mock_task = _make_task(12345, title="并发故障")

        with (
            patch.object(pipeline, "_fetch_task", new_callable=AsyncMock) as mock_fetch,
            patch.object(
                pipeline,
                "_analyze_root_cause",
                new_callable=AsyncMock,
                return_value=[
                    {
                        "cause_type": "并发问题",
                        "description": "竞态条件",
                        "evidence": "",
                        "confidence": 0.9,
                    }
                ],
            ),
            patch.object(pipeline, "_create_llm_provider", return_value=MagicMock()),
        ):
            mock_fetch.return_value = mock_task
            result = await pipeline.run_single(12345)

        assert result.improvements is not None
        assert len(result.improvements) > 0
        assert "measure" in result.improvements[0]
        assert "priority" in result.improvements[0]

    @pytest.mark.asyncio
    async def test_run_single_no_root_causes_empty_improvements(self, mock_config):
        """G4: no root causes → improvements is empty list, no crash."""
        pipeline = AnalysisPipeline(
            config=mock_config,
            pipeline_config=PipelineConfig(use_llm=False, check_rules=False),
        )
        mock_task = _make_task(12345)

        with patch.object(pipeline, "_fetch_task", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_task
            result = await pipeline.run_single(12345)

        assert result.improvements == []
