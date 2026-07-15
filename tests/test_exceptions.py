"""Tests for unified exception hierarchy (REQ-1, Issue #9)."""

import pytest

from src.core.exceptions import (
    AnalysisError,
    ClusteringError,
    ConfigurationError,
    DataProcessingError,
    EmbeddingError,
    FaultAnalyzerError,
    LabelingError,
    PreprocessingError,
    ReportGenerationError,
    RootCauseError,
    RulesEngineError,
)


class TestFaultAnalyzerError:
    """Test base exception class."""

    def test_base_error_with_message(self) -> None:
        """Base error stores message correctly."""
        error = FaultAnalyzerError("something went wrong")
        assert str(error) == "something went wrong"
        assert error.error_code == "ANALYZER_000"
        assert error.context == {}

    def test_base_error_with_error_code(self) -> None:
        """Base error stores custom error code."""
        error = FaultAnalyzerError("bad config", error_code="CONFIG_001")
        assert error.error_code == "CONFIG_001"

    def test_base_error_with_context(self) -> None:
        """Base error stores context dict."""
        ctx = {"task_id": 12345, "phase": "analyze"}
        error = FaultAnalyzerError("failed", context=ctx)
        assert error.context == ctx
        assert error.context["task_id"] == 12345

    def test_base_error_is_exception(self) -> None:
        """Base error is a proper Exception."""
        error = FaultAnalyzerError("test")
        assert isinstance(error, Exception)

    def test_base_error_can_be_raised_and_caught(self) -> None:
        """Base error can be raised and caught as Exception."""
        with pytest.raises(FaultAnalyzerError):
            raise FaultAnalyzerError("test error")


class TestAnalysisError:
    """Test analysis-specific errors."""

    def test_analysis_error_inherits_base(self) -> None:
        """AnalysisError inherits from FaultAnalyzerError."""
        error = AnalysisError("analysis failed")
        assert isinstance(error, FaultAnalyzerError)
        assert isinstance(error, Exception)

    def test_clustering_error_inherits_analysis(self) -> None:
        """ClusteringError inherits from AnalysisError."""
        error = ClusteringError("no clusters found")
        assert isinstance(error, AnalysisError)
        assert isinstance(error, FaultAnalyzerError)

    def test_labeling_error_inherits_analysis(self) -> None:
        """LabelingError inherits from AnalysisError."""
        error = LabelingError("LLM timeout")
        assert isinstance(error, AnalysisError)

    def test_root_cause_error_inherits_analysis(self) -> None:
        """RootCauseError inherits from AnalysisError."""
        error = RootCauseError("insufficient data")
        assert isinstance(error, AnalysisError)


class TestReportGenerationError:
    """Test report generation errors."""

    def test_report_error_inherits_base(self) -> None:
        """ReportGenerationError inherits from FaultAnalyzerError."""
        error = ReportGenerationError("template not found")
        assert isinstance(error, FaultAnalyzerError)

    def test_report_error_with_format_context(self) -> None:
        """Report error can include format context."""
        error = ReportGenerationError(
            "unsupported format",
            context={"format": "xml"},
        )
        assert error.context["format"] == "xml"


class TestConfigurationError:
    """Test configuration errors."""

    def test_config_error_inherits_base(self) -> None:
        """ConfigurationError inherits from FaultAnalyzerError."""
        error = ConfigurationError("missing API key")
        assert isinstance(error, FaultAnalyzerError)


class TestDataProcessingError:
    """Test data processing errors."""

    def test_data_processing_error_inherits_base(self) -> None:
        """DataProcessingError inherits from FaultAnalyzerError."""
        error = DataProcessingError("invalid data format")
        assert isinstance(error, FaultAnalyzerError)

    def test_embedding_error_inherits_data_processing(self) -> None:
        """EmbeddingError inherits from DataProcessingError."""
        error = EmbeddingError("dimension mismatch")
        assert isinstance(error, DataProcessingError)
        assert isinstance(error, FaultAnalyzerError)

    def test_preprocessing_error_inherits_data_processing(self) -> None:
        """PreprocessingError inherits from DataProcessingError."""
        error = PreprocessingError("empty input")
        assert isinstance(error, DataProcessingError)


class TestRulesEngineError:
    """Test rules engine errors."""

    def test_rules_error_inherits_base(self) -> None:
        """RulesEngineError inherits from FaultAnalyzerError."""
        error = RulesEngineError("rule not found")
        assert isinstance(error, FaultAnalyzerError)


class TestErrorHierarchyCatching:
    """Test that errors can be caught at different hierarchy levels."""

    def test_catch_all_with_base_error(self) -> None:
        """All custom errors catchable with FaultAnalyzerError."""
        errors = [
            AnalysisError("a"),
            ClusteringError("b"),
            ReportGenerationError("c"),
            ConfigurationError("d"),
            DataProcessingError("e"),
            RulesEngineError("f"),
        ]
        for error in errors:
            with pytest.raises(FaultAnalyzerError):
                raise error

    def test_catch_analysis_errors_specifically(self) -> None:
        """Analysis sub-errors catchable with AnalysisError."""
        for error_cls in [ClusteringError, LabelingError, RootCauseError]:
            with pytest.raises(AnalysisError):
                raise error_cls("test")

    def test_catch_data_processing_errors_specifically(self) -> None:
        """Data processing sub-errors catchable with DataProcessingError."""
        for error_cls in [EmbeddingError, PreprocessingError]:
            with pytest.raises(DataProcessingError):
                raise error_cls("test")

    def test_api_errors_not_in_hierarchy(self) -> None:
        """API errors are separate (not part of FaultAnalyzerError)."""
        from src.api.exceptions import APIError

        api_error = APIError("api fail")
        assert not isinstance(api_error, FaultAnalyzerError)
