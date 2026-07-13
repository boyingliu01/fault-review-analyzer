"""API 中间件测试"""

import time

from fastapi.testclient import TestClient

from src.api.middleware import RateLimiter, TokenValidator
from src.api.server import create_app


class TestTokenValidator:
    """Token 验证器测试"""

    def test_token_validator_with_valid_tokens(self):
        """测试 Token 验证器 - 配置有效 Token"""
        validator = TokenValidator(valid_tokens={"token1", "token2"})
        assert validator.is_valid("token1") is True
        assert validator.is_valid("token2") is True
        assert validator.is_valid("invalid") is False

    def test_token_validator_with_no_tokens(self):
        """测试 Token 验证器 - 无有效 Token（开发模式）"""
        validator = TokenValidator()
        assert validator.is_valid("any_token") is True
        assert validator.is_valid("") is True


class TestRateLimiter:
    """速率限制器测试"""

    def test_rate_limiter_under_limit(self):
        """测试速率限制 - 未超限"""
        limiter = RateLimiter(requests_per_minute=5)
        for _ in range(5):
            allowed, remaining = limiter.is_allowed("test_client")
            assert allowed is True
            assert remaining == 4 - _

    def test_rate_limiter_over_limit(self):
        """测试速率限制 - 超限"""
        limiter = RateLimiter(requests_per_minute=3)
        for _ in range(3):
            limiter.is_allowed("test_client")

        allowed, remaining = limiter.is_allowed("test_client")
        assert allowed is False
        assert remaining == 0

    def test_rate_limiter_different_identifiers(self):
        """测试速率限制 - 不同标识符"""
        limiter = RateLimiter(requests_per_minute=2)
        allowed1, remaining1 = limiter.is_allowed("client1")
        allowed2, remaining2 = limiter.is_allowed("client2")

        assert allowed1 is True
        assert allowed2 is True
        assert remaining1 == 1
        assert remaining2 == 1

    def test_rate_limiter_reset_after_window(self, monkeypatch):
        """测试速率限制 - 窗口过期后重置"""
        limiter = RateLimiter(requests_per_minute=1)

        # 第一个请求
        limiter.is_allowed("test_client")

        # 模拟 61 秒后
        future_time = time.time() + 61
        monkeypatch.setattr(time, "time", lambda: future_time)

        allowed, remaining = limiter.is_allowed("test_client")
        assert allowed is True
        assert remaining == 0  # 新的窗口


class TestMiddlewareSetup:
    """中间件配置测试"""

    def test_middleware_setup(self):
        """测试中间件设置"""
        app = create_app()
        assert hasattr(app, "middleware_stack")

    def test_middleware_with_token_validation(self):
        """测试带 Token 验证的中间件"""
        valid_tokens = {"test_token"}
        app = create_app(valid_tokens=valid_tokens)

        with TestClient(app) as client:
            # 未认证
            response = client.get("/clusters")
            assert response.status_code == 401

            # 无效 Token
            response = client.get("/clusters", headers={"X-API-Token": "invalid"})
            assert response.status_code == 403

            # 有效 Token
            response = client.get("/clusters", headers={"X-API-Token": "test_token"})
            assert response.status_code == 200

    def test_middleware_rate_limiting(self):
        """测试速率限制中间件"""
        # 设置严格的速率限制（1个请求/分钟）
        app = create_app(rate_limit_requests=1)

        with TestClient(app) as client:
            # 第一个请求通过
            response = client.get("/clusters", headers={"X-API-Token": "test"})
            assert response.status_code == 200

            # 第二个请求被拒绝
            response = client.get("/clusters", headers={"X-API-Token": "test"})
            assert response.status_code == 429

    def test_health_endpoint_no_auth(self):
        """测试健康检查接口无认证"""
        app = create_app(valid_tokens={"test_token"})

        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json()["status"] == "healthy"


class TestMiddlewareHeaders:
    """中间件响应头测试"""

    def test_rate_limit_headers(self):
        """测试速率限制响应头"""
        app = create_app(valid_tokens={"test_token"}, rate_limit_requests=10)

        with TestClient(app) as client:
            response = client.get("/clusters", headers={"X-API-Token": "test_token"})
            assert response.status_code == 200
            assert "X-RateLimit-Limit" in response.headers
            assert "X-RateLimit-Remaining" in response.headers
            assert int(response.headers["X-RateLimit-Limit"]) == 10
            assert int(response.headers["X-RateLimit-Remaining"]) == 9


class TestMiddlewareErrorHandling:
    """中间件错误处理测试"""

    def test_middleware_error_logging(self, caplog):
        """测试中间件日志记录"""
        # 无认证的应用
        app = create_app(valid_tokens=None)
        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200

    def test_token_from_query_parameter(self):
        """测试从查询参数获取 Token"""
        app = create_app(valid_tokens={"query_token"})

        with TestClient(app) as client:
            response = client.get("/clusters?api_token=query_token")
            assert response.status_code == 200
