"""Tests for GAP fixes G8-G9 (functional GAP analysis remediation).

Covers:
- G8: get_full_task fetches fault_analysis (复盘结论) in standard fetch flow
- G9: REST API exposes /api/v1 prefix, /ready, /tasks/{id}/result, cluster analyze
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.models import TaskInfo
from src.api.server import create_app

# --- G8: get_full_task fetches fault_analysis ---


class TestFaultAnalysisInFullTask:
    @pytest.mark.asyncio
    async def test_get_full_task_includes_fault_analysis(self):
        """G8: get_full_task populates task.fault_analysis from API."""
        from src.api.client import APIClient

        client = APIClient(base_url="https://api.example.com")
        mock_task = MagicMock(spec=TaskInfo)
        mock_task.task_id = 12345

        with (
            patch.object(client, "get_task", new_callable=AsyncMock, return_value=mock_task),
            patch.object(client, "get_commits", new_callable=AsyncMock, return_value=[]),
            patch.object(
                client,
                "get_production_info",
                new_callable=AsyncMock,
                return_value=MagicMock(),
            ),
            patch.object(
                client,
                "get_fault_analysis",
                new_callable=AsyncMock,
                return_value={
                    "apiDevTaskAnalysis": {"catalog": "开发", "conclusion": "结论"},
                    "apiTestTaskAnalysis": {},
                },
            ) as mock_fault_analysis,
        ):
            result = await client.get_full_task(12345)

        assert result.fault_analysis == {
            "apiDevTaskAnalysis": {"catalog": "开发", "conclusion": "结论"},
            "apiTestTaskAnalysis": {},
        }
        mock_fault_analysis.assert_called_once_with("12345")

    @pytest.mark.asyncio
    async def test_get_full_task_fault_analysis_failure_degrades(self):
        """G8: get_fault_analysis failure → fault_analysis is None, no crash."""
        from src.api.client import APIClient

        client = APIClient(base_url="https://api.example.com")
        mock_task = MagicMock(spec=TaskInfo)
        mock_task.task_id = 12345

        with (
            patch.object(client, "get_task", new_callable=AsyncMock, return_value=mock_task),
            patch.object(client, "get_commits", new_callable=AsyncMock, return_value=[]),
            patch.object(
                client,
                "get_production_info",
                new_callable=AsyncMock,
                return_value=MagicMock(),
            ),
            patch.object(
                client,
                "get_fault_analysis",
                new_callable=AsyncMock,
                side_effect=RuntimeError("API down"),
            ),
        ):
            result = await client.get_full_task(12345)

        assert result.fault_analysis is None


# --- G9: REST API path alignment ---


@pytest.fixture
def client():
    """Create test client with a valid token."""
    app = create_app(valid_tokens={"test-token-123"})
    return TestClient(app)


def _headers() -> dict[str, str]:
    return {"X-API-Token": "test-token-123"}


class TestApiV1Prefix:
    """G9: routes are registered under /api/v1 prefix."""

    def test_health_under_api_v1(self, client):
        """GET /api/v1/health works."""
        response = client.get("/api/v1/health", headers=_headers())
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_health_root_still_works(self, client):
        """Legacy root /health still works (backward compat)."""
        response = client.get("/health", headers=_headers())
        assert response.status_code == 200

    def test_clusters_under_api_v1(self, client):
        """GET /api/v1/clusters works."""
        import src.api.routes.clusters as cluster_routes

        cluster_routes._cluster_cache = {}
        response = client.get("/api/v1/clusters", headers=_headers())
        assert response.status_code == 200
        assert response.json()["total_clusters"] == 0


class TestReadyEndpoint:
    """G9: /ready readiness endpoint exists."""

    def test_ready_under_root(self, client):
        """GET /ready works."""
        response = client.get("/ready", headers=_headers())
        assert response.status_code == 200
        assert response.json()["status"] == "ready"

    def test_ready_under_api_v1(self, client):
        """GET /api/v1/ready works."""
        response = client.get("/api/v1/ready", headers=_headers())
        assert response.status_code == 200
        assert response.json()["status"] == "ready"


class TestTaskResultEndpoint:
    """G9: GET /tasks/{id}/result endpoint."""

    def test_task_result_invalid_id(self, client):
        """Non-numeric task ID → 400."""
        response = client.get("/api/v1/tasks/abc/result", headers=_headers())
        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "InvalidTaskId"

    def test_task_result_task_not_found(self, client):
        """Task not found → 404."""
        with patch("src.api.routes.analyze.AnalysisPipeline") as mock_pipeline_cls:
            mock_pipeline = MagicMock()
            mock_result = MagicMock()
            mock_result.error = "Task 999 not found"
            mock_pipeline.run_single = AsyncMock(return_value=mock_result)
            mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
            mock_pipeline.__aexit__ = AsyncMock(return_value=None)
            mock_pipeline_cls.return_value = mock_pipeline

            response = client.get("/api/v1/tasks/999/result", headers=_headers())

        assert response.status_code == 404


class TestClusterAnalyzeEndpoint:
    """G9: POST /clusters/analyze populates cluster cache."""

    def test_empty_task_ids_returns_400(self, client):
        """Empty task_ids → 400."""
        response = client.post("/api/v1/clusters/analyze", json=[], headers=_headers())
        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "EmptyTaskIds"
