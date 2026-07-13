"""API 认证中间件"""

import time
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from loguru import logger


class RateLimiter:
    """速率限制器"""

    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, identifier: str) -> tuple[bool, int]:
        """
        检查请求是否允许

        Args:
            identifier: 标识符（token 或 IP）

        Returns:
            (是否允许, 剩余请求数)
        """
        now = time.time()
        one_minute_ago = now - 60

        # 清理一分钟前的记录
        self.requests[identifier] = [
            t for t in self.requests[identifier] if t > one_minute_ago
        ]

        # 检查是否超限
        if len(self.requests[identifier]) >= self.requests_per_minute:
            return False, 0

        # 记录当前请求
        self.requests[identifier].append(now)
        remaining = self.requests_per_minute - len(self.requests[identifier])
        return True, remaining


class TokenValidator:
    """Token 验证器"""

    def __init__(self, valid_tokens: set[str] | None = None):
        self.valid_tokens = valid_tokens or set()

    def is_valid(self, token: str) -> bool:
        """验证 token 是否有效"""
        if not self.valid_tokens:
            # 如果没有配置有效 token，则允许所有请求（开发模式）
            return True
        return token in self.valid_tokens


def setup_middleware(
    app: FastAPI,
    token_validator: TokenValidator | None = None,
    rate_limiter: RateLimiter | None = None,
) -> None:
    """
    设置中间件

    Args:
        app: FastAPI 应用实例
        token_validator: Token 验证器
        rate_limiter: 速率限制器
    """
    if token_validator is None:
        token_validator = TokenValidator()

    if rate_limiter is None:
        rate_limiter = RateLimiter()

    @app.middleware("http")
    async def auth_middleware(request: Request, call_next: Callable) -> Any:
        """认证中间件"""
        # 跳过健康检查和根路径的认证
        if request.url.path == "/health" or request.url.path == "/":
            return await call_next(request)

        # 从 Header 或 Query 参数获取 Token
        token = request.headers.get("X-API-Token") or request.query_params.get(
            "api_token"
        )

        if not token:
            logger.warning(f"Missing API token for request: {request.url.path}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "Unauthorized",
                    "message": "Missing API token",
                    "detail": {},
                    "timestamp": time.time(),
                },
            )

        # 验证 Token
        if not token_validator.is_valid(token):
            logger.warning(f"Invalid API token for request: {request.url.path}")
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": "Forbidden",
                    "message": "Invalid API token",
                    "detail": {},
                    "timestamp": time.time(),
                },
            )

        # 速率限制
        identifier = token or request.client.host if request.client else "unknown"
        allowed, remaining = rate_limiter.is_allowed(identifier)

        if not allowed:
            logger.warning(f"Rate limit exceeded for: {identifier}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Too Many Requests",
                    "message": "Rate limit exceeded",
                    "detail": {"retry_after": 60},
                    "timestamp": time.time(),
                },
            )

        # 继续处理请求
        response = await call_next(request)

        # 添加速率限制头
        response.headers["X-RateLimit-Limit"] = str(rate_limiter.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response

    @app.middleware("http")
    async def logging_middleware(request: Request, call_next: Callable) -> Any:
        """日志中间件"""
        start_time = time.time()

        # 记录请求
        logger.info(
            f"Request: {request.method} {request.url.path} "
            f"from {request.client.host if request.client else 'unknown'}"
        )

        try:
            response = await call_next(request)
            process_time = (time.time() - start_time) * 1000

            # 记录响应
            logger.info(
                f"Response: {response.status_code} for {request.method} {request.url.path} "
                f"in {process_time:.2f}ms"
            )

            return response

        except Exception as e:
            process_time = (time.time() - start_time) * 1000
            logger.error(
                f"Error processing {request.method} {request.url.path}: {str(e)} "
                f"in {process_time:.2f}ms"
            )
            raise
