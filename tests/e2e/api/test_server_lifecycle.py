"""P1 E2E 测试: API Server 完整生命周期。

使用 FastAPI TestClient 测试完整请求链路，不 mock 内部组件。
关注端到端行为：启动 → 认证 → 分析 → 响应结构。
"""

import pytest
from fastapi.testclient import TestClient

from src.api.server import create_app


@pytest.fixture
def app_no_auth():
    """创建无 token 验证的 FastAPI 应用（开发模式）。"""
    return create_app(
        valid_tokens=None,
        rate_limit_requests=100,
        allow_unauthenticated=True,
    )


@pytest.fixture
def app_with_auth():
    """创建有 token 验证的 FastAPI 应用。"""
    return create_app(valid_tokens={"valid-token-123"}, rate_limit_requests=100)


@pytest.fixture
def app_rate_limited():
    """创建低速率限制的应用。"""
    return create_app(
        valid_tokens=None,
        rate_limit_requests=3,
        allow_unauthenticated=True,
    )


@pytest.fixture
def client_no_auth(app_no_auth):
    return TestClient(app_no_auth)


@pytest.fixture
def client_with_auth(app_with_auth):
    return TestClient(app_with_auth)


@pytest.fixture
def client_rate_limited(app_rate_limited):
    return TestClient(app_rate_limited)


class TestServerLifecycle:
    """测试服务器启动和基本生命周期。"""

    def test_server_starts_and_health_check(self, client_no_auth: TestClient):
        """服务器启动后 /health 应返回 200。"""
        response = client_no_auth.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data

    def test_root_endpoint_returns_welcome(self, client_no_auth: TestClient):
        """根路径应返回欢迎信息。"""
        response = client_no_auth.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "Welcome" in data["message"]

    def test_openapi_docs_available(self, client_no_auth: TestClient):
        """OpenAPI 文档应可访问（需要 token 因为中间件拦截）。"""
        response = client_no_auth.get(
            "/openapi.json",
            headers={"X-API-Token": "any"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "paths" in data
        assert "/health" in data["paths"]
        assert "/analyze" in data["paths"]


class TestServerAuthLifecycle:
    """测试认证完整链路。"""

    def test_health_no_auth_required(self, client_with_auth: TestClient):
        """/health 不需要认证。"""
        response = client_with_auth.get("/health")
        assert response.status_code == 200

    def test_root_no_auth_required(self, client_with_auth: TestClient):
        """/ 不需要认证。"""
        response = client_with_auth.get("/")
        assert response.status_code == 200

    def test_analyze_requires_token(self, client_with_auth: TestClient):
        """/analyze 缺少 token 应返回 401。"""
        response = client_with_auth.post(
            "/analyze",
            json={"task_id": "12345"},
        )
        assert response.status_code == 401
        data = response.json()
        assert "Missing API token" in data.get("message", "")

    def test_analyze_with_valid_token(self, client_with_auth: TestClient):
        """/analyze 带有效 token 应通过认证（不返回 401/403）。"""
        response = client_with_auth.post(
            "/analyze",
            json={"task_id": "12345", "options": {"use_cache": False, "use_llm": False}},
            headers={"X-API-Token": "valid-token-123"},
        )
        # 可能因 API 调用失败，但不应是 401/403
        assert response.status_code not in (401, 403)

    def test_analyze_with_invalid_token(self, client_with_auth: TestClient):
        """/analyze 带无效 token 应返回 403。"""
        response = client_with_auth.post(
            "/analyze",
            json={"task_id": "12345"},
            headers={"X-API-Token": "invalid-token"},
        )
        assert response.status_code == 403

    def test_query_param_token_does_not_authenticate(self, client_with_auth: TestClient):
        """通过 query 参数传递 token 应视为缺少认证。"""
        response = client_with_auth.post(
            "/analyze?api_token=valid-token-123",
            json={"task_id": "12345"},
        )
        assert response.status_code == 401


class TestServerRateLimiting:
    """测试速率限制完整链路。"""

    def test_rate_limit_headers_present(self, client_no_auth: TestClient):
        """响应应包含速率限制头。"""
        response = client_no_auth.post(
            "/analyze",
            json={"task_id": "12345"},
            headers={"X-API-Token": "any-token"},
        )
        # 速率限制头应在响应中（即使请求本身失败）
        assert "x-ratelimit-limit" in response.headers

    def test_rate_limit_exceeded(self, client_rate_limited: TestClient):
        """超过速率限制应返回 429。"""
        headers = {"X-API-Token": "test-client"}

        # 发送请求直到超限（使用 /clusters 端点避免真实 API 调用耗时）
        responses = []
        for _ in range(5):
            resp = client_rate_limited.get(
                "/clusters",
                headers=headers,
            )
            responses.append(resp.status_code)

        # 至少有一个应该是 429
        assert 429 in responses


class TestServerAnalyzeEndpoint:
    """测试分析端点的完整行为。"""

    def test_analyze_invalid_task_id_format(self, client_no_auth: TestClient):
        """无效 task_id 格式应返回合理错误。"""
        response = client_no_auth.post(
            "/analyze",
            json={"task_id": ""},
            headers={"X-API-Token": "any"},
        )
        # 应返回 422（验证错误）或 400/500
        assert response.status_code in (400, 422, 500)

    def test_analyze_response_structure(self, client_no_auth: TestClient):
        """分析端点应对无效请求返回合理错误（不等待真实 API 调用）。"""
        # 使用无效的 task_id 类型触发验证错误
        response = client_no_auth.post(
            "/analyze",
            json={"task_id": None},
            headers={"X-API-Token": "any"},
        )
        # 应返回验证错误
        assert response.status_code in (400, 422, 500)

    def test_batch_analyze_requires_nonempty_ids(self, client_no_auth: TestClient):
        """批量分析应要求非空的 task_ids。"""
        response = client_no_auth.post(
            "/analyze/batch",
            json={"task_ids": []},
            headers={"X-API-Token": "any"},
        )
        # 空列表应返回验证错误
        assert response.status_code == 422


class TestServerOpenAPISpec:
    """测试 OpenAPI 规范完整性。"""

    def test_all_expected_paths_present(self, client_no_auth: TestClient):
        """所有预期路径应在 OpenAPI 规范中。"""
        response = client_no_auth.get("/openapi.json", headers={"X-API-Token": "any"})
        data = response.json()
        paths = data.get("paths", {})

        expected_paths = ["/health", "/analyze", "/analyze/batch"]
        for path in expected_paths:
            assert path in paths, f"Path {path} not found in OpenAPI spec"

    def test_api_info_present(self, client_no_auth: TestClient):
        """API 信息应在 OpenAPI 规范中。"""
        response = client_no_auth.get("/openapi.json", headers={"X-API-Token": "any"})
        data = response.json()
        assert "info" in data
        assert "title" in data["info"]
        assert "Fault Review Analyzer" in data["info"]["title"]
