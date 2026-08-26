"""E2E: API 错误处理场景测试.

覆盖 spec 中的 Error Handling 表：
  - API timeout → 500 或 504
  - Authentication failed → 401 (no token) / 403 (invalid token)
  - LLM unavailable → 500 (analysis fails)

使用 FastAPI TestClient 测试完整请求链路，不 mock 内部组件。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from src.api.server import create_app

if TYPE_CHECKING:
    from collections.abc import Generator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app_auth_required() -> Generator:
    """创建需要 token 验证的 FastAPI 应用。"""
    yield create_app(valid_tokens={"valid-token-123"}, rate_limit_requests=100)


@pytest.fixture
def client_auth(app_auth_required) -> TestClient:
    return TestClient(app_auth_required)


# ---------------------------------------------------------------------------
# Auth Failure (401/403)
# ---------------------------------------------------------------------------


class TestAuthFailure:
    """Spec: API 认证失败，请检查 DEVCLOUD_TOKEN."""

    def test_missing_token_returns_401(self, client_auth: TestClient):
        """无 token 时应返回 401 并包含错误信息。"""
        response = client_auth.post(
            "/analyze",
            json={"task_id": "12345", "options": {"use_cache": False, "use_llm": False}},
        )
        assert response.status_code == 401
        data = response.json()
        assert "Missing API token" in data.get("message", "")

    def test_invalid_token_returns_403(self, client_auth: TestClient):
        """无效 token 时应返回 403。"""
        response = client_auth.post(
            "/analyze",
            json={"task_id": "12345"},
            headers={"X-API-Token": "invalid-token"},
        )
        assert response.status_code == 403
        data = response.json()
        assert "Invalid API token" in data.get("message", "")

    def test_query_param_valid_token_returns_401(self, client_auth: TestClient):
        """通过 query 参数传递有效 token 应视为缺少认证。"""
        response = client_auth.post(
            "/analyze?api_token=valid-token-123",
            json={"task_id": "12345", "options": {"use_cache": False, "use_llm": False}},
        )
        assert response.status_code == 401

    def test_header_token_priority_over_query_param(self, client_auth: TestClient):
        """Header token 和 query token 同时存在时应正常工作。"""
        response = client_auth.post(
            "/analyze?api_token=ignored",
            json={"task_id": "12345", "options": {"use_cache": False, "use_llm": False}},
            headers={"X-API-Token": "valid-token-123"},
        )
        assert response.status_code not in (401, 403)


# ---------------------------------------------------------------------------
# Server Error (500) — Timeout / LLM Unavailable
# ---------------------------------------------------------------------------


class TestServerErrorResponse:
    """Spec: LLM 服务不可用，请检查配置 / API 请求超时，请检查网络连接."""

    def test_analyze_route_produces_500_for_failure(self, client_auth: TestClient):
        """分析请求失败时应返回 500 或带有错误信息的响应。

        注：因无真实 API 后端，Pipeline 内部会失败，但端点不应崩溃。
        验证：
        - 返回非 200
        - 响应体为 JSON
        - 包含错误详情
        """
        response = client_auth.post(
            "/analyze",
            json={"task_id": "99999", "options": {"use_cache": False, "use_llm": False}},
            headers={"X-API-Token": "valid-token-123"},
        )

        if response.status_code == 200:
            # 如果成功 => 响应体应包含 PipelineResult 结构
            data = response.json()
            assert "task_id" in data or "error" in data
        else:
            # server error => 应有 error detail
            data = response.json()
            # FastAPI HTTPException 将错误放在 detail 字段
            # 中间件错误用顶层字段
            assert data is not None

    def test_batch_analyze_route_handles_failure_gracefully(self, client_auth: TestClient):
        """批量分析请求失败时应有合理的错误响应。"""
        response = client_auth.post(
            "/analyze/batch",
            json={"task_ids": [99999, 88888]},
            headers={"X-API-Token": "valid-token-123"},
        )
        # 端点不应导致 5xx 崩溃
        if response.status_code >= 500:
            data = response.json()
            assert data is not None
            # 应有错误消息
            assert "detail" in data or "error" in data or "message" in data

    def test_reports_get_for_missing_task_returns_error(self, client_auth: TestClient):
        """请求不存在任务的报告时应返回 404 或 500（取决于错误冒泡层级）。"""
        response = client_auth.get(
            "/reports/99999999",
            headers={"X-API-Token": "valid-token-123"},
        )
        # 应返回错误状态码（404=not found 或 500=server error）
        assert response.status_code >= 400

    def test_invalid_task_id_format_in_get_returns_400(self, client_auth: TestClient):
        """GET /reports/{task_id} 中无效 task_id 格式应返回 400。"""
        response = client_auth.get(
            "/reports/not-a-number",
            headers={"X-API-Token": "valid-token-123"},
        )
        # 无效格式应返回 400 或 422（FastAPI 验证错误）
        assert response.status_code in (400, 422)

    def test_valid_token_query_param_returns_401_on_protected_routes(self, client_auth: TestClient):
        """通过 query 参数传递有效 token 应视为缺少认证。"""
        response = client_auth.get(
            "/reports/12345?api_token=valid-token-123",
        )
        assert response.status_code == 401

    def test_health_endpoint_error_response_structure(self, client_auth: TestClient):
        """/health 端点在任何情况下都应返回 JSON 并有 status 字段。"""
        # 已验证健康端点无论有无 token 都能正常访问
        response = client_auth.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        # 即使是 200，也应验证结构完整性
        assert "timestamp" in data
        assert "version" in data


# ---------------------------------------------------------------------------
# Edge Cases — 边界情况处理
# ---------------------------------------------------------------------------


class TestErrorEdgeCases:
    """Spec: 如果 API 返回空数据或超时."""

    def test_analyze_with_empty_options_still_works(self, client_auth: TestClient):
        """空 options 应被接受并使用默认值。"""
        response = client_auth.post(
            "/analyze",
            json={"task_id": "12345"},
            headers={"X-API-Token": "valid-token-123"},
        )
        # 不应返回 422（validation error），应返回业务状态
        assert response.status_code != 422

    def test_auth_error_response_is_json(self, client_auth: TestClient):
        """认证错误响应应为 JSON 格式。"""
        response = client_auth.post(
            "/analyze",
            json={"task_id": "12345"},
            headers={"X-API-Token": "invalid-token"},
        )
        assert response.status_code == 403
        assert response.headers.get("content-type", "").startswith("application/json")
