"""Tests for the refactored AnalysisPipeline class."""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.analyzer.pipeline import AnalysisPipeline, PipelineConfig, PipelineResult
from src.api.models import TaskInfo
from src.config.manager import ConfigManager


class TestAnalysisPipelineRefactored:
    """Tests for the refactored AnalysisPipeline methods."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def config_manager(self, temp_dir):
        """Create a ConfigManager with test configuration."""
        config_data = {
            "api": {
                "base_url": "https://api.example.com",
                "timeout": 30,
                "retry": 3,
                "api_key": "test-api-key",
                "api_path_prefix": "/api/v1",
            },
            "llm": {
                "provider": "openai",
                "model": "gpt-4",
                "api_key": "test-llm-key",
                "temperature": 0.7,
                "max_tokens": 4096,
            },
            "embedding": {
                "provider": "openai",
                "model": "text-embedding-3-small",
                "api_key": "test-embedding-key",
                "batch_size": 100,
            },
            "clustering": {
                "algorithm": "hdbscan",
                "min_cluster_size": 5,
                "min_samples": 3,
                "metric": "cosine",
            },
            "cache": {
                "enabled": True,
                "ttl": 86400,
                "storage": "sqlite",
                "db_path": str(temp_dir / "cache.db"),
            },
            "output": {"format": "markdown", "directory": str(temp_dir / "output")},
        }
        return ConfigManager(config=config_data)

    @pytest.fixture
    def pipeline_config(self):
        """Create PipelineConfig for testing."""
        return PipelineConfig(
            use_cache=True,
            use_llm=False,
            generate_labels=True,
            analyze_root_cause=True,
            check_rules=False,
            generate_report=False,
        )

    @pytest.fixture
    def sample_task_info(self):
        """Create sample TaskInfo for testing."""
        return TaskInfo(
            task_id=12345,
            title="测试故障单",
            description="系统发生故障的描述",
            status="resolved",
            priority="high",
            create_time=datetime(2024, 1, 15, 10, 30, 0),
            resolve_time=datetime(2024, 1, 16, 14, 45, 0),
        )

    @pytest.fixture
    def sample_processed_task(self):
        """Create sample processed task data (using mock)."""
        mock_processed = MagicMock()
        mock_processed.task_id = 12345
        mock_processed.combined_text = "测试故障单 系统发生故障的描述"
        mock_processed.segments = [
            MagicMock(type="标题", content="测试故障单", metadata={}),
            MagicMock(type="描述", content="系统发生故障的描述", metadata={}),
        ]
        mock_processed.metadata = {
            "title": "测试故障单",
        }
        return mock_processed

    @pytest.fixture
    def sample_labels(self):
        """Create sample labels for testing."""
        return [
            {
                "name": "系统稳定性",
                "category": "性能",
                "confidence": 0.85,
                "description": "系统稳定性问题",
            },
            {"name": "用户交互", "category": "交互", "confidence": 0.75},
        ]

    @pytest.fixture
    def sample_root_causes(self):
        """Create sample root causes for testing."""
        return [
            {
                "cause_type": "代码缺陷",
                "description": "处理请求时未检查空值",
                "evidence": ["代码第100行未进行空值判断"],
                "confidence": 0.9,
            }
        ]

    @pytest.mark.asyncio
    @patch("src.analyzer.pipeline.AnalysisPipeline._fetch_task")
    async def test_fetch_task_data(
        self, mock_fetch_task, config_manager, pipeline_config, sample_task_info
    ):
        """Test _fetch_task_data method delegating to _fetch_task."""
        mock_fetch_task.return_value = sample_task_info

        pipeline = AnalysisPipeline(config_manager, pipeline_config)
        result = await pipeline._fetch_task_data(12345)

        assert result == sample_task_info
        mock_fetch_task.assert_called_once_with(12345)

    @pytest.mark.asyncio
    async def test_prepare_task_data(self, config_manager, pipeline_config, sample_task_info):
        """Test _prepare_task_data method."""
        pipeline = AnalysisPipeline(config_manager, pipeline_config)
        result = PipelineResult(task_id=12345)

        # Mock the preprocessor
        mock_preprocessed = MagicMock()
        mock_preprocessed.task_id = 12345
        mock_preprocessed.combined_text = "测试故障单 系统发生故障的描述"
        mock_preprocessed.segments = []
        mock_preprocessed.metadata = {"title": "测试故障单"}

        with patch.object(pipeline._preprocessor, "process", return_value=mock_preprocessed):
            preprocessed = await pipeline._prepare_task_data(sample_task_info, result)

            assert result.task_data == sample_task_info.model_dump()
            assert result.preprocessed is not None
            assert result.preprocessed["task_id"] == 12345
            assert "combined_text" in result.preprocessed
            assert "segments" in result.preprocessed
            assert preprocessed == mock_preprocessed

    @pytest.mark.asyncio
    async def test_analyze_with_llm_disabled(self, config_manager, sample_task_info):
        """Test _analyze_with_llm when LLM is disabled."""
        pipeline_config = PipelineConfig(use_llm=False)
        pipeline = AnalysisPipeline(config_manager, pipeline_config)
        result = PipelineResult(task_id=12345)

        mock_processed = MagicMock()
        await pipeline._analyze_with_llm(sample_task_info, mock_processed, result)

        # No changes to result when LLM is disabled
        assert result.labels is None
        assert result.root_causes is None
        assert result.deep_root_causes is None

    @pytest.mark.asyncio
    @patch("src.analyzer.pipeline.AnalysisPipeline._generate_labels")
    @patch("src.analyzer.pipeline.AnalysisPipeline._analyze_root_cause")
    @patch("src.analyzer.pipeline.AnalysisPipeline._analyze_root_cause_deep")
    async def test_analyze_with_llm_enabled(
        self,
        mock_deep_root_cause,
        mock_root_cause,
        mock_generate_labels,
        config_manager,
        sample_task_info,
        sample_labels,
        sample_root_causes,
    ):
        """Test _analyze_with_llm when LLM is enabled."""
        mock_generate_labels.return_value = sample_labels
        mock_root_cause.return_value = sample_root_causes
        mock_deep_root_cause.return_value = {"layer1": "deep analysis"}

        pipeline_config = PipelineConfig(
            use_llm=True,
            generate_labels=True,
            analyze_root_cause=True,
            analyze_root_cause_deep=True,
        )
        pipeline = AnalysisPipeline(config_manager, pipeline_config)
        result = PipelineResult(task_id=12345)

        mock_processed = MagicMock()
        await pipeline._analyze_with_llm(sample_task_info, mock_processed, result)

        assert result.labels == sample_labels
        assert result.root_causes == sample_root_causes
        assert result.deep_root_causes == {"layer1": "deep analysis"}
        mock_generate_labels.assert_called_once()
        mock_root_cause.assert_called_once()
        mock_deep_root_cause.assert_called_once()

    def test_check_and_generate_report_no_rules_no_report(self, config_manager, sample_task_info):
        """Test _check_and_generate_report with both checks disabled."""
        pipeline_config = PipelineConfig(check_rules=False, generate_report=False)
        pipeline = AnalysisPipeline(config_manager, pipeline_config)
        result = PipelineResult(task_id=12345)

        mock_processed = MagicMock()
        mock_preprocessed_dict: dict[str, list] = {"segments": []}
        result.preprocessed = mock_preprocessed_dict

        pipeline._check_and_generate_report(sample_task_info, mock_processed, result)

        assert result.violations is None
        assert result.report == ""

    @patch("src.analyzer.pipeline.AnalysisPipeline._check_rules")
    @patch("src.analyzer.pipeline.AnalysisPipeline._generate_report")
    def test_check_and_generate_report_with_rules_and_report(
        self, mock_generate_report, mock_check_rules, config_manager, sample_task_info
    ):
        """Test _check_and_generate_report with both checks enabled."""
        rule_violation = {
            "rule_id": "R001",
            "rule_name": "Test Rule",
            "severity": "high",
            "message": "Test message",
        }
        code_violation = {
            "rule_id": "CODE001",
            "rule_name": "Code Change Rule",
            "severity": "medium",
            "message": "Code change message",
        }
        sample_violations = [rule_violation]
        expected_violations = [rule_violation, code_violation]
        sample_report_content = "Test Report Content"

        mock_check_rules.return_value = sample_violations
        mock_generate_report.return_value = sample_report_content

        pipeline_config = PipelineConfig(check_rules=True, generate_report=True)
        pipeline = AnalysisPipeline(config_manager, pipeline_config)
        result = PipelineResult(task_id=12345, violations=[code_violation])

        mock_processed = MagicMock()
        mock_preprocessed_dict: dict[str, list] = {"segments": []}
        result.preprocessed = mock_preprocessed_dict
        result.labels = []
        result.root_causes = []

        pipeline._check_and_generate_report(sample_task_info, mock_processed, result)

        assert result.violations == expected_violations
        assert result.report == sample_report_content
        mock_check_rules.assert_called_once()
        mock_generate_report.assert_called_once()
        assert mock_generate_report.call_args.kwargs["violations"] == expected_violations

    @pytest.mark.asyncio
    @patch("src.analyzer.pipeline.AnalysisPipeline._fetch_task_data")
    @patch("src.analyzer.pipeline.AnalysisPipeline._prepare_task_data")
    @patch("src.analyzer.pipeline.AnalysisPipeline._analyze_with_llm")
    @patch("src.analyzer.pipeline.AnalysisPipeline._check_and_generate_report")
    async def test_run_single_refactored(
        self,
        mock_check_report,
        mock_analyze_llm,
        mock_prepare,
        mock_fetch_data,
        config_manager,
        pipeline_config,
        sample_task_info,
    ):
        """Test the full refactored run_single pipeline."""
        mock_fetch_data.return_value = sample_task_info
        mock_prepare.return_value = MagicMock()

        pipeline = AnalysisPipeline(config_manager, pipeline_config)
        result = await pipeline.run_single(12345)

        assert result.task_id == 12345
        mock_fetch_data.assert_called_once_with(12345)
        mock_prepare.assert_called_once()
        mock_analyze_llm.assert_called_once()
        mock_check_report.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.analyzer.pipeline.AnalysisPipeline._fetch_task_data")
    async def test_run_single_task_not_found(
        self, mock_fetch_data, config_manager, pipeline_config
    ):
        """Test run_single when task is not found."""
        mock_fetch_data.return_value = None

        pipeline = AnalysisPipeline(config_manager, pipeline_config)
        result = await pipeline.run_single(99999)

        assert result.task_id == 99999
        assert "not found" in result.error
        mock_fetch_data.assert_called_once_with(99999)

    @pytest.mark.asyncio
    @patch("src.analyzer.pipeline.AnalysisPipeline._fetch_task_data")
    async def test_run_single_handles_exception(
        self, mock_fetch_data, config_manager, pipeline_config
    ):
        """Test run_single handles exceptions gracefully."""
        test_error = "Test error message"
        mock_fetch_data.side_effect = Exception(test_error)

        pipeline = AnalysisPipeline(config_manager, pipeline_config)
        result = await pipeline.run_single(12345)

        assert result.task_id == 12345
        assert result.error == test_error
