"""Tests for pipeline handlers — REQ-3, Issue #13.

Tests the three handler classes that split the monolithic pipeline:
- FetchHandler: data fetching from API/cache
- AnalyzeHandler: LLM-based analysis (labels, root cause)
- ReportHandler: rules checking and report generation
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.models import TaskInfo
from src.preprocessor.models import ProcessedTask, TextSegment

# --- Fixtures ---


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.api = MagicMock()
    config.api.base_url = "https://api.example.com"
    config.api.api_key = "test-key"
    config.api.timeout = 30
    config.api.retry = 3
    config.cache = MagicMock()
    config.cache.db_path = Path("/tmp/test_cache.db")
    config.cache.ttl = 3600
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
    return config


@pytest.fixture
def sample_task():
    return TaskInfo(
        task_id=12345,
        title="Test Task",
        description="Test Description",
        status="open",
        priority="medium",
        create_time=datetime.now(),
    )


@pytest.fixture
def sample_preprocessed():
    return ProcessedTask(
        task_id=12345,
        combined_text="Test combined text",
        segments=[
            TextSegment(task_id=12345, type="开发", content="dev content", metadata={}),
        ],
        metadata={"title": "Test Task"},
    )


# --- FetchHandler Tests ---


class TestFetchHandler:
    """Test FetchHandler responsibilities."""

    def test_import(self):
        """FetchHandler can be imported."""
        from src.analyzer.handlers.fetch import FetchHandler

        assert FetchHandler is not None

    def test_init_with_api_client(self):
        """FetchHandler can be initialized with API client."""
        from src.analyzer.handlers.fetch import FetchHandler

        mock_api = MagicMock()
        mock_cache = MagicMock()
        handler = FetchHandler(api_client=mock_api, cache_manager=mock_cache, use_cache=True)
        assert handler._api_client is mock_api

    @pytest.mark.asyncio
    async def test_fetch_task_from_api(self, sample_task):
        """FetchHandler fetches task from API when cache miss."""
        from src.analyzer.handlers.fetch import FetchHandler

        mock_api = MagicMock()
        mock_api.get_full_task = AsyncMock(return_value=sample_task)
        mock_cache = MagicMock()
        mock_cache.load_task.return_value = None

        handler = FetchHandler(api_client=mock_api, cache_manager=mock_cache, use_cache=True)
        result = await handler.fetch_task(12345)

        assert result is sample_task
        mock_api.get_full_task.assert_called_once_with(12345)

    @pytest.mark.asyncio
    async def test_fetch_task_from_cache(self, sample_task):
        """FetchHandler returns cached task when available."""
        from src.analyzer.handlers.fetch import FetchHandler

        mock_api = MagicMock()
        mock_cache = MagicMock()
        mock_cache.load_task.return_value = sample_task.model_dump(mode="json")

        handler = FetchHandler(api_client=mock_api, cache_manager=mock_cache, use_cache=True)
        result = await handler.fetch_task(12345)

        assert result is not None
        assert result.task_id == 12345
        mock_api.get_full_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetch_task_no_cache(self, sample_task):
        """FetchHandler skips cache when use_cache=False."""
        from src.analyzer.handlers.fetch import FetchHandler

        mock_api = MagicMock()
        mock_api.get_full_task = AsyncMock(return_value=sample_task)
        mock_cache = MagicMock()

        handler = FetchHandler(api_client=mock_api, cache_manager=mock_cache, use_cache=False)
        result = await handler.fetch_task(12345)

        assert result is sample_task
        mock_cache.load_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetch_tasks_bounds_concurrency_and_preserves_success_order(self):
        """Batch fetching limits active calls and keeps successful input order."""
        from src.analyzer.handlers.fetch import FetchHandler
        from src.api.client import APIClient

        class AsyncFakeAPI(APIClient):
            def __init__(self) -> None:
                super().__init__(base_url="https://api.example.com")
                self.active_calls = 0
                self.max_active_calls = 0

            async def get_full_task(self, task_id: int) -> TaskInfo:
                self.active_calls += 1
                self.max_active_calls = max(self.max_active_calls, self.active_calls)
                await asyncio.sleep(0)
                self.active_calls -= 1
                if task_id == 2:
                    raise RuntimeError("task fetch failed")
                return TaskInfo(
                    task_id=task_id,
                    title=f"Task {task_id}",
                    create_time=datetime.now(),
                )

        api = AsyncFakeAPI()
        handler = FetchHandler(api_client=api, use_cache=False, max_concurrency=2)

        results = await handler.fetch_tasks([1, 2, 3, 4])

        assert [task.task_id for task in results] == [1, 3, 4]
        assert api.max_active_calls == 2


# --- AnalyzeHandler Tests ---


class TestAnalyzeHandler:
    """Test AnalyzeHandler responsibilities."""

    def test_import(self):
        """AnalyzeHandler can be imported."""
        from src.analyzer.handlers.analyze import AnalyzeHandler

        assert AnalyzeHandler is not None

    def test_init(self):
        """AnalyzeHandler can be initialized."""
        from src.analyzer.handlers.analyze import AnalyzeHandler

        handler = AnalyzeHandler(llm_provider=None)
        assert handler._llm_provider is None

    @pytest.mark.asyncio
    async def test_generate_labels_no_provider(self, sample_task, sample_preprocessed):
        """generate_labels returns empty list when no LLM provider."""
        from src.analyzer.handlers.analyze import AnalyzeHandler

        handler = AnalyzeHandler(llm_provider=None)
        result = await handler.generate_labels(sample_task.model_dump(), sample_preprocessed)
        assert result == []

    @pytest.mark.asyncio
    async def test_analyze_root_cause_no_provider(self, sample_task, sample_preprocessed):
        """analyze_root_cause returns empty list when no LLM provider."""
        from src.analyzer.handlers.analyze import AnalyzeHandler

        handler = AnalyzeHandler(llm_provider=None)
        result = await handler.analyze_root_cause(sample_task.model_dump(), sample_preprocessed)
        assert result == []


# --- ReportHandler Tests ---


class TestReportHandler:
    """Test ReportHandler responsibilities."""

    def test_import(self):
        """ReportHandler can be imported."""
        from src.analyzer.handlers.report import ReportHandler

        assert ReportHandler is not None

    def test_check_rules(self):
        """ReportHandler delegates to RulesEngine."""
        from src.analyzer.handlers.report import ReportHandler

        mock_engine = MagicMock()
        mock_violation = MagicMock()
        mock_violation.rule_id = "R001"
        mock_violation.rule_name = "Test Rule"
        mock_violation.severity = "high"
        mock_violation.message = "Test violation"
        mock_violation.evidence = "evidence"
        mock_engine.check.return_value = [mock_violation]

        handler = ReportHandler(rules_engine=mock_engine)
        result = handler.check_rules({"title": "Test"})

        assert len(result) == 1
        assert result[0]["rule_id"] == "R001"

    def test_generate_report(self):
        """ReportHandler generates report string."""
        from src.analyzer.handlers.report import ReportHandler

        mock_generator = MagicMock()
        mock_generator.generate_single.return_value = "# Test Report"

        handler = ReportHandler(report_generator=mock_generator)
        result = handler.generate_report(
            task_data={"task_id": 12345},
            preprocessed={"segments": []},
            labels=[],
            root_causes=[],
        )

        assert result == "# Test Report"


# --- PipelineOrchestrator Tests ---


class TestPipelineOrchestrator:
    """Test PipelineOrchestrator composition."""

    def test_import(self):
        """PipelineOrchestrator can be imported."""
        from src.analyzer.orchestrator import PipelineOrchestrator

        assert PipelineOrchestrator is not None

    def test_init_with_handlers(self):
        """PipelineOrchestrator accepts handler instances."""
        from src.analyzer.handlers.analyze import AnalyzeHandler
        from src.analyzer.handlers.fetch import FetchHandler
        from src.analyzer.handlers.report import ReportHandler
        from src.analyzer.orchestrator import PipelineOrchestrator

        fetch = FetchHandler(api_client=MagicMock(), cache_manager=MagicMock())
        analyze = AnalyzeHandler(llm_provider=None)
        report = ReportHandler()

        orchestrator = PipelineOrchestrator(
            fetch_handler=fetch,
            analyze_handler=analyze,
            report_handler=report,
        )

        assert orchestrator._fetch_handler is fetch
        assert orchestrator._analyze_handler is analyze
        assert orchestrator._report_handler is report

    @pytest.mark.asyncio
    async def test_orchestrate_single_task(self, sample_task):
        """PipelineOrchestrator.run_single orchestrates all handlers."""
        from src.analyzer.handlers.analyze import AnalyzeHandler
        from src.analyzer.handlers.fetch import FetchHandler
        from src.analyzer.handlers.report import ReportHandler
        from src.analyzer.orchestrator import PipelineOrchestrator

        fetch = FetchHandler(api_client=MagicMock(), cache_manager=MagicMock())
        analyze = AnalyzeHandler(llm_provider=None)
        report = ReportHandler()

        with (
            patch.object(
                fetch, "fetch_task", new_callable=AsyncMock, return_value=sample_task
            ) as mock_fetch,
            patch.object(report, "check_rules", return_value=[]) as mock_check_rules,
            patch.object(
                report, "generate_report", return_value="# Report"
            ) as mock_generate_report,
        ):
            orchestrator = PipelineOrchestrator(
                fetch_handler=fetch,
                analyze_handler=analyze,
                report_handler=report,
            )

            from src.analyzer.pipeline import PipelineConfig

            config = PipelineConfig(
                use_llm=False,
                generate_labels=False,
                analyze_root_cause=False,
                check_rules=True,
                generate_report=True,
            )

            result = await orchestrator.run_single(12345, config)

            assert result.task_id == 12345
            assert result.error == ""
            mock_fetch.assert_called_once_with(12345)
            mock_check_rules.assert_called_once()
            mock_generate_report.assert_called_once()


# --- Backward Compatibility Tests ---


class TestBackwardCompatibility:
    """Ensure AnalysisPipeline still works as before."""

    def test_pipeline_still_importable(self):
        """AnalysisPipeline, PipelineConfig, PipelineResult still importable."""
        from src.analyzer.pipeline import AnalysisPipeline, PipelineConfig, PipelineResult

        assert AnalysisPipeline is not None
        assert PipelineConfig is not None
        assert PipelineResult is not None

    def test_pipeline_still_constructable(self, mock_config):
        """AnalysisPipeline can still be created with same constructor."""
        from src.analyzer.pipeline import AnalysisPipeline, PipelineConfig

        pipeline = AnalysisPipeline(config=mock_config, pipeline_config=PipelineConfig())
        assert pipeline is not None

    @pytest.mark.asyncio
    async def test_pipeline_run_single_still_works(self, mock_config, sample_task):
        """run_single still works with same signature."""
        from src.analyzer.pipeline import AnalysisPipeline, PipelineConfig

        pipeline_config = PipelineConfig(
            use_llm=False,
            generate_labels=False,
            analyze_root_cause=False,
            check_rules=True,
            generate_report=False,
        )
        pipeline = AnalysisPipeline(config=mock_config, pipeline_config=pipeline_config)

        with patch.object(pipeline, "_fetch_task", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = sample_task

            async with pipeline:
                result = await pipeline.run_single(12345)

        assert result.task_id == 12345
        assert result.error == ""

    def test_pipeline_internal_methods_still_exist(self, mock_config):
        """Internal methods still accessible for existing tests."""
        from src.analyzer.pipeline import AnalysisPipeline, PipelineConfig

        pipeline = AnalysisPipeline(config=mock_config, pipeline_config=PipelineConfig())

        # These methods must still exist for backward compat
        assert hasattr(pipeline, "_check_rules")
        assert hasattr(pipeline, "_generate_report")
        assert hasattr(pipeline, "_fetch_task")
        assert hasattr(pipeline, "_get_api_client")
        assert hasattr(pipeline, "_get_cache_manager")
        assert hasattr(pipeline, "_convert_api_to_existing_analysis")
