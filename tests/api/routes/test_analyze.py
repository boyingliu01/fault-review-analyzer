"""Unit tests for /analyze and /analyze/batch routes."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from loguru import logger

from src.analyzer.pipeline import PipelineResult
from src.api.server import create_app


@pytest.fixture
def client():
    """Create test client with a valid token."""
    app = create_app(valid_tokens={"test-token-123"})
    return TestClient(app)


def _headers() -> dict[str, str]:
    """Return auth headers."""
    return {"X-API-Token": "test-token-123"}


@pytest.fixture
def mock_pipeline():
    """Return a mock AnalysisPipeline class that works as an async context manager."""
    with patch("src.api.routes.analyze.AnalysisPipeline") as mock_cls:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_cls.return_value = mock_instance
        yield mock_cls, mock_instance


# ---------------------------------------------------------------------------
# convert_pipeline_result_to_response
# ---------------------------------------------------------------------------


class TestConvertPipelineResultToResponse:
    """Tests for the convert_pipeline_result_to_response helper."""

    def test_success_result(self):
        """A PipelineResult with no error maps to status=completed."""
        from src.api.routes.analyze import convert_pipeline_result_to_response

        result = PipelineResult(
            task_id=12345,
            labels=[{"name": "oom", "confidence": 0.9}],
            root_causes=[{"cause_type": "logic", "description": "bad query"}],
            deep_root_causes={"layer1": "analysis"},
            violations=[
                {
                    "rule_id": "R1",
                    "rule_name": "test",
                    "severity": "high",
                    "message": "violated",
                }
            ],
            report="<html>report</html>",
            error="",
        )

        resp = convert_pipeline_result_to_response("12345", result)
        assert resp.status == "completed"
        assert resp.error == ""
        assert len(resp.labels) == 1
        assert resp.labels[0]["name"] == "oom"
        assert len(resp.root_causes) == 1
        assert resp.deep_root_causes == {"layer1": "analysis"}
        assert len(resp.violations) == 1
        assert resp.violations[0]["rule_id"] == "R1"
        assert resp.report == "<html>report</html>"

    def test_failure_result(self):
        """A PipelineResult with an error maps to status=failed."""
        from src.api.routes.analyze import convert_pipeline_result_to_response

        result = PipelineResult(task_id=12345, error="Task not found")

        resp = convert_pipeline_result_to_response("12345", result)
        assert resp.status == "failed"
        assert resp.error == "Task not found"
        assert resp.labels == []
        assert resp.root_causes == []
        assert resp.report == ""

    def test_empty_labels_and_root_causes(self):
        """When labels/root_causes are None, they default to empty lists."""
        from src.api.routes.analyze import convert_pipeline_result_to_response

        result = PipelineResult(task_id=12345, report="minimal", error="")

        resp = convert_pipeline_result_to_response("12345", result)
        assert resp.status == "completed"
        assert resp.labels == []
        assert resp.root_causes == []
        assert resp.deep_root_causes == {}
        assert resp.violations == []
        assert resp.suggestions == []


# ---------------------------------------------------------------------------
# POST /analyze
# ---------------------------------------------------------------------------


class TestAnalyzeTask:
    """Tests for the analyze_task endpoint."""

    def test_happy_path(self, client, mock_pipeline):
        """Full happy path: pipeline returns a completed result."""
        _, mock_instance = mock_pipeline
        mock_instance.run_single.return_value = PipelineResult(
            task_id=12345,
            labels=[
                {
                    "name": "config",
                    "confidence": 0.85,
                    "category": "defect",
                    "description": "misconfiguration",
                }
            ],
            root_causes=[
                {
                    "cause_type": "environment",
                    "description": "wrong env var",
                    "evidence": ["log"],
                    "confidence": 0.9,
                }
            ],
            report="<html>ok</html>",
            error="",
        )

        response = client.post("/analyze", json={"task_id": "12345"}, headers=_headers())
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert len(data["labels"]) == 1
        assert data["labels"][0]["name"] == "config"
        assert len(data["root_causes"]) == 1
        assert data["report"] == "<html>ok</html>"

    def test_happy_path_with_options(self, client, mock_pipeline):
        """Happy path with explicit analysis options."""
        _, mock_instance = mock_pipeline
        mock_instance.run_single.return_value = PipelineResult(
            task_id=999, labels=[], root_causes=[], report="done", error=""
        )

        response = client.post(
            "/analyze",
            json={
                "task_id": 999,
                "options": {"use_cache": False, "use_llm": True},
            },
            headers=_headers(),
        )
        assert response.status_code == 200
        assert response.json()["status"] == "completed"

    def test_pipeline_error_is_redacted_from_response_and_logs(self, client, mock_pipeline):
        """Unexpected pipeline errors expose only stable response and log metadata."""
        _, mock_instance = mock_pipeline
        sentinel_secret = "SENTINEL-SECRET-analyze-single"
        mock_instance.run_single.side_effect = RuntimeError(sentinel_secret)
        log_messages: list[str] = []
        sink_id = logger.add(log_messages.append, format="{message} {extra}")

        try:
            response = client.post("/analyze", json={"task_id": "12345"}, headers=_headers())
        finally:
            logger.remove(sink_id)

        assert response.status_code == 500
        data = response.json()
        assert data["detail"]["error"] == "AnalysisFailed"
        assert data["detail"]["message"] == "Analysis failed due to an internal error"
        assert sentinel_secret not in response.text
        assert any("RuntimeError" in message and "12345" in message for message in log_messages)
        assert all(sentinel_secret not in message for message in log_messages)

    def test_pipeline_result_with_error_returns_200(self, client, mock_pipeline):
        """When pipeline succeeds but the result has an error field, returns 200 with status=failed."""
        _, mock_instance = mock_pipeline
        mock_instance.run_single.return_value = PipelineResult(
            task_id=12345, error="Task 12345 not found"
        )

        response = client.post("/analyze", json={"task_id": "12345"}, headers=_headers())
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["error"] == "Task 12345 not found"

    def test_task_id_as_integer(self, client, mock_pipeline):
        """Task ID passed as integer is accepted."""
        _, mock_instance = mock_pipeline
        mock_instance.run_single.return_value = PipelineResult(
            task_id=42, labels=[], root_causes=[], report="ok", error=""
        )

        response = client.post("/analyze", json={"task_id": 42}, headers=_headers())
        assert response.status_code == 200

    def test_missing_task_id_rejected(self, client):
        """Missing required field returns 422 Unprocessable Entity."""
        response = client.post("/analyze", json={}, headers=_headers())
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /analyze/batch
# ---------------------------------------------------------------------------


class TestAnalyzeBatch:
    """Tests for the analyze_batch endpoint."""

    def test_happy_path(self, client, mock_pipeline):
        """Batch analysis with 2 tasks returns 200."""
        _, mock_instance = mock_pipeline
        mock_instance.run_batch.return_value = [
            PipelineResult(task_id=1, labels=[], root_causes=[], report="r1", error=""),
            PipelineResult(task_id=2, labels=[], root_causes=[], report="r2", error=""),
        ]

        response = client.post("/analyze/batch", json={"task_ids": [1, 2]}, headers=_headers())
        assert response.status_code == 200
        data = response.json()
        assert data["total_requested"] == 2
        assert data["total_completed"] == 2
        assert data["total_failed"] == 0
        assert len(data["results"]) == 2

    def test_batch_with_failures(self, client, mock_pipeline):
        """Batch with one success and one failure."""
        _, mock_instance = mock_pipeline
        mock_instance.run_batch.return_value = [
            PipelineResult(task_id=1, labels=[], root_causes=[], report="ok", error=""),
            PipelineResult(task_id=2, error="Task 2 not found"),
        ]

        response = client.post("/analyze/batch", json={"task_ids": [1, 2]}, headers=_headers())
        assert response.status_code == 200
        data = response.json()
        assert data["total_completed"] == 1
        assert data["total_failed"] == 1

    def test_empty_task_ids_rejected(self, client):
        """Empty task_ids list triggers FastAPI min_length validation."""
        response = client.post("/analyze/batch", json={"task_ids": []}, headers=_headers())
        assert response.status_code == 422

    def test_missing_task_ids_rejected(self, client):
        """Missing task_ids field returns 422."""
        response = client.post("/analyze/batch", json={}, headers=_headers())
        assert response.status_code == 422

    def test_more_than_fifty_unique_task_ids_rejected_before_pipeline(self, client, mock_pipeline):
        """More than 50 unique task IDs are rejected before pipeline construction."""
        mock_cls, _ = mock_pipeline

        response = client.post(
            "/analyze/batch",
            json={"task_ids": list(range(1, 52))},
            headers=_headers(),
        )

        assert response.status_code == 422
        mock_cls.assert_not_called()

    def test_duplicate_task_ids_are_coerced_and_deduplicated_in_first_seen_order(
        self, client, mock_pipeline
    ):
        """Equivalent task IDs run once in first-seen order."""
        _, mock_instance = mock_pipeline
        mock_instance.run_batch.return_value = [
            PipelineResult(task_id=1, labels=[], root_causes=[], report="r1", error=""),
            PipelineResult(task_id=2, labels=[], root_causes=[], report="r2", error=""),
        ]

        response = client.post(
            "/analyze/batch",
            json={"task_ids": [1, "1", 2, 1]},
            headers=_headers(),
        )

        assert response.status_code == 200
        assert response.json()["total_requested"] == 2
        mock_instance.run_batch.assert_awaited_once_with([1, 2])

    def test_batch_exception_is_redacted_from_response_and_logs(self, client, mock_pipeline):
        """Unexpected batch errors expose only stable response and log metadata."""
        _, mock_instance = mock_pipeline
        sentinel_secret = "SENTINEL-SECRET-analyze-batch"
        mock_instance.run_batch.side_effect = TimeoutError(sentinel_secret)
        log_messages: list[str] = []
        sink_id = logger.add(log_messages.append, format="{message} {extra}")

        try:
            response = client.post("/analyze/batch", json={"task_ids": [1]}, headers=_headers())
        finally:
            logger.remove(sink_id)

        assert response.status_code == 500
        data = response.json()
        assert data["detail"]["error"] == "BatchAnalysisFailed"
        assert data["detail"]["message"] == "Batch analysis failed due to an internal error"
        assert sentinel_secret not in response.text
        assert any("TimeoutError" in message and "1" in message for message in log_messages)
        assert all(sentinel_secret not in message for message in log_messages)
