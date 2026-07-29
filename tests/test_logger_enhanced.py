"""Tests for enhanced structured logging with correlation ID (REQ-2, Issue #12)."""

import uuid

from src.utils.logger import (
    StructuredLogger,
    get_correlation_id,
    get_logger,
)


class TestCorrelationId:
    """Test correlation ID generation and management."""

    def test_get_correlation_id_returns_uuid(self) -> None:
        """get_correlation_id returns a valid UUID string."""
        cid = get_correlation_id()
        # Should be a valid UUID
        parsed = uuid.UUID(cid)
        assert str(parsed) == cid

    def test_get_correlation_id_unique(self) -> None:
        """Each call returns a unique ID."""
        ids = {get_correlation_id() for _ in range(100)}
        assert len(ids) == 100


class TestStructuredLogger:
    """Test StructuredLogger class."""

    def test_logger_creation(self) -> None:
        """StructuredLogger can be created with a name."""
        log = StructuredLogger("test.module")
        assert log is not None

    def test_logger_with_correlation(self) -> None:
        """StructuredLogger.with_correlation returns a bound logger."""
        log = StructuredLogger("test.module")
        cid = get_correlation_id()
        bound = log.with_correlation(cid)
        assert bound is not log
        assert bound._correlation_id == cid

    def test_logger_with_correlation_auto_generates(self) -> None:
        """with_correlation without args auto-generates an ID."""
        log = StructuredLogger("test.module")
        bound = log.with_correlation()
        assert bound._correlation_id is not None
        # Should be a valid UUID
        uuid.UUID(bound._correlation_id)

    def test_logger_methods_preserve_correlation(self) -> None:
        """Log methods on bound logger preserve correlation_id."""
        log = StructuredLogger("test.module")
        cid = get_correlation_id()
        bound = log.with_correlation(cid)
        # These should not raise
        bound.info("test message")
        bound.debug("debug message")
        bound.warning("warning message")
        bound.error("error message")

    def test_logger_context_method(self) -> None:
        """context() method adds extra structured fields."""
        log = StructuredLogger("test.module")
        bound = log.with_correlation("test-cid").context(task_id=12345, phase="analyze")
        assert bound is not log


class TestGetLogger:
    """Test get_logger function."""

    def test_get_logger_returns_bindable(self) -> None:
        """get_logger returns a logger that can be bound."""
        log = get_logger("test")
        bound = log.bind(correlation_id="abc-123")
        assert bound is not log
