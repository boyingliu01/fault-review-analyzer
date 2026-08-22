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

    def test_token_validator_with_no_tokens_rejects_tokens_by_default(self):
        """测试 Token 验证器 - 无有效 Token 时默认拒绝"""
        validator = TokenValidator()
        assert validator.is_valid("any_token") is False

    def test_token_validator_allows_tokens_with_explicit_unauthenticated_opt_in(self):
        """测试 Token 验证器 - 显式开启无认证开发模式"""
        validator = TokenValidator(allow_unauthenticated=True)
        assert validator.is_valid("any_token") is True


class TestRateLimiter:
    """速率限制器测试"""

    def test_rate_limiter_caps_identifiers_examined_per_cleanup_call(self, monkeypatch):
        """测试速率限制 - 单次清理检查固定数量的标识符"""
        examined_identifiers = 0

        class TrackingTimestamps(list[float]):
            def __iter__(self):
                nonlocal examined_identifiers
                examined_identifiers += 1
                return super().__iter__()

        now = 0.0
        monkeypatch.setattr(time, "time", lambda: now)
        limiter = RateLimiter(requests_per_minute=2)
        for index in range(192):
            identifier = f"stale-{index}"
            limiter.is_allowed(identifier)
            limiter.requests[identifier] = TrackingTimestamps(limiter.requests[identifier])

        now = 61.0
        limiter.is_allowed("trigger")

        assert examined_identifiers <= 64
        assert any(identifier.startswith("stale-") for identifier in limiter.requests)

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

    def test_rate_limiter_evicts_high_cardinality_stale_identifiers(self, monkeypatch):
        """测试速率限制 - 淘汰大量过期标识符"""
        now = 0.0
        monkeypatch.setattr(time, "time", lambda: now)
        limiter = RateLimiter(requests_per_minute=2)
        stale_identifiers = {f"stale-{index}" for index in range(1_000)}
        for identifier in stale_identifiers:
            limiter.is_allowed(identifier)

        now = 61.0
        for index in range(len(stale_identifiers)):
            limiter.is_allowed(f"fresh-{index}")

        assert stale_identifiers.isdisjoint(limiter.requests)

    def test_rate_limiter_cleanup_preserves_active_identifier(self, monkeypatch):
        """测试速率限制 - 清理时保留活跃标识符"""
        now = 0.0
        monkeypatch.setattr(time, "time", lambda: now)
        limiter = RateLimiter(requests_per_minute=3)
        limiter.is_allowed("stale")

        now = 30.0
        limiter.is_allowed("active")

        now = 61.0
        limiter.is_allowed("trigger")
        allowed, remaining = limiter.is_allowed("active")

        assert "stale" not in limiter.requests
        assert "active" in limiter.requests
        assert allowed is True
        assert remaining == 1


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
        app = create_app(rate_limit_requests=1, allow_unauthenticated=True)

        with TestClient(app) as client:
            # 第一个请求通过
            response = client.get("/clusters", headers={"X-API-Token": "test"})
            assert response.status_code == 200

            # 第二个请求被拒绝
            response = client.get("/clusters", headers={"X-API-Token": "test"})
            assert response.status_code == 429

    def test_middleware_rejects_protected_endpoint_without_configured_tokens(self):
        """测试未配置 Token 时受保护接口默认关闭"""
        app = create_app()

        with TestClient(app) as client:
            response = client.get("/clusters")

        assert response.status_code == 401

    def test_middleware_rejects_unconfigured_token_by_default(self):
        """测试未配置有效 Token 时拒绝任意 Token"""
        app = create_app()

        with TestClient(app) as client:
            response = client.get("/clusters", headers={"X-API-Token": "unconfigured"})

        assert response.status_code == 403

    def test_middleware_allows_protected_endpoint_with_explicit_unauthenticated_opt_in(self):
        """测试显式开启无认证开发模式后允许访问受保护接口"""
        app = create_app(allow_unauthenticated=True)

        with TestClient(app) as client:
            response = client.get("/clusters")

        assert response.status_code == 200

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

    def test_middleware_error_logging(self):
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
