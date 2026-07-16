"""Unified exception hierarchy for Fault Review Analyzer.

Provides a structured exception hierarchy for consistent error handling
across all modules. Each exception includes an error_code for programmatic
handling and a context dict for debugging information.

Issue: #9 — Pipeline 错误处理框架
"""

from __future__ import annotations

from typing import Any


class FaultAnalyzerError(Exception):
    """Base exception for all Fault Review Analyzer errors.

    All custom exceptions in the project should inherit from this class,
    enabling callers to catch all analyzer-related errors with a single
    except clause.

    Attributes:
        message: Human-readable error description.
        error_code: Machine-readable error code (e.g., "ANALYZER_001").
        context: Additional debugging information.
    """

    def __init__(
        self,
        message: str = "An unexpected error occurred",
        *,
        error_code: str = "ANALYZER_000",
        context: dict[str, Any] | None = None,
    ) -> None:
        self.message = message
        self.error_code = error_code
        self.context: dict[str, Any] = context or {}
        super().__init__(self.message)

    def __str__(self) -> str:
        return self.message

    def to_dict(self) -> dict[str, Any]:
        """Serialize error to dict for logging/API responses."""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "context": self.context,
        }


# --- Analysis Errors ---


class AnalysisError(FaultAnalyzerError):
    """Error during fault analysis (clustering, labeling, root cause)."""

    def __init__(
        self,
        message: str = "Analysis failed",
        *,
        error_code: str = "ANALYSIS_000",
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, error_code=error_code, context=context)


class ClusteringError(AnalysisError):
    """Error during HDBSCAN clustering phase."""

    def __init__(
        self,
        message: str = "Clustering failed",
        *,
        error_code: str = "CLUSTER_000",
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, error_code=error_code, context=context)


class LabelingError(AnalysisError):
    """Error during LLM label generation."""

    def __init__(
        self,
        message: str = "Label generation failed",
        *,
        error_code: str = "LABEL_000",
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, error_code=error_code, context=context)


class RootCauseError(AnalysisError):
    """Error during root cause analysis."""

    def __init__(
        self,
        message: str = "Root cause analysis failed",
        *,
        error_code: str = "ROOTCAUSE_000",
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, error_code=error_code, context=context)


# --- Report Errors ---


class ReportGenerationError(FaultAnalyzerError):
    """Error during report generation."""

    def __init__(
        self,
        message: str = "Report generation failed",
        *,
        error_code: str = "REPORT_000",
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, error_code=error_code, context=context)


# --- Configuration Errors ---


class ConfigurationError(FaultAnalyzerError):
    """Error in configuration (missing keys, invalid values)."""

    def __init__(
        self,
        message: str = "Configuration error",
        *,
        error_code: str = "CONFIG_000",
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, error_code=error_code, context=context)


# --- Data Processing Errors ---


class DataProcessingError(FaultAnalyzerError):
    """Error during data preprocessing or transformation."""

    def __init__(
        self,
        message: str = "Data processing failed",
        *,
        error_code: str = "DATA_000",
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, error_code=error_code, context=context)


class EmbeddingError(DataProcessingError):
    """Error during embedding generation."""

    def __init__(
        self,
        message: str = "Embedding generation failed",
        *,
        error_code: str = "EMBED_000",
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, error_code=error_code, context=context)


class PreprocessingError(DataProcessingError):
    """Error during data preprocessing."""

    def __init__(
        self,
        message: str = "Preprocessing failed",
        *,
        error_code: str = "PREPROCESS_000",
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, error_code=error_code, context=context)


# --- Rules Engine Errors ---


class RulesEngineError(FaultAnalyzerError):
    """Error in rules engine (rule evaluation, conflict detection)."""

    def __init__(
        self,
        message: str = "Rules engine error",
        *,
        error_code: str = "RULES_000",
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, error_code=error_code, context=context)
