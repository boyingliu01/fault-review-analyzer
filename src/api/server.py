"""FastAPI 服务 - 故障复盘分析 API 服务器"""

import os
from collections.abc import AsyncGenerator, Awaitable, Callable, Sequence
from contextlib import asynccontextmanager
from typing import Final

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from src.api.middleware import RateLimiter, TokenValidator, setup_middleware
from src.api.routes import analyze, clusters, feedback, health, reports

_DEFAULT_CORS_METHODS: Final = ("GET", "POST", "OPTIONS")
_DEFAULT_CORS_HEADERS: Final = ("Content-Type", "X-API-Token")
_API_DOCS_PATHS: Final = frozenset(("/docs", "/redoc", "/openapi.json"))


def parse_environment_list(name: str, default: tuple[str, ...] = ()) -> tuple[str, ...]:
    """Parse a comma-separated environment variable into non-empty values."""
    value = os.getenv(name)
    if value is None:
        return default
    return tuple(item for raw_item in value.split(",") if (item := raw_item.strip()))


def parse_environment_bool(name: str, default: bool = False) -> bool:
    """Parse an environment variable that accepts only true or false."""
    value = os.getenv(name)
    if value is None:
        return default
    if value == "true":
        return True
    if value == "false":
        return False
    raise ValueError(f"{name} must be 'true' or 'false'")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI 生命周期管理

    Args:
        app: FastAPI 应用实例
    """
    # 启动事件
    logger.info("Starting Fault Review Analyzer API Server...")

    # 初始化资源
    # 可以在这里初始化数据库连接、加载模型等

    yield

    # 关闭事件
    logger.info("Shutting down Fault Review Analyzer API Server...")

    # 清理资源
    # 可以在这里关闭数据库连接、释放资源等


def create_app(
    valid_tokens: set[str] | None = None,
    rate_limit_requests: int = 60,
    allow_unauthenticated: bool = False,
    allowed_origins: Sequence[str] | None = None,
    allowed_methods: Sequence[str] | None = None,
    allowed_headers: Sequence[str] | None = None,
    api_docs_enabled: bool = False,
) -> FastAPI:
    """
    创建 FastAPI 应用

    Args:
        valid_tokens: 有效的 API Token 集合
        rate_limit_requests: 每分钟请求限制数
        allow_unauthenticated: 是否显式允许无认证访问
        allowed_origins: 允许跨域访问的显式来源
        allowed_methods: 允许跨域访问的 HTTP 方法
        allowed_headers: 允许跨域访问的请求头
        api_docs_enabled: 是否启用 API 文档端点

    Returns:
        FastAPI: 配置好的 FastAPI 应用实例
    """
    app = FastAPI(
        title="Fault Review Analyzer API",
        description="AI驱动的故障复盘分析工具 API 服务",
        version="0.1.0",
        docs_url="/docs" if api_docs_enabled else None,
        redoc_url="/redoc" if api_docs_enabled else None,
        openapi_url="/openapi.json" if api_docs_enabled else None,
        openapi_tags=[
            {
                "name": "Health",
                "description": "健康检查接口",
            },
            {
                "name": "Analysis",
                "description": "任务分析接口",
            },
            {
                "name": "Clusters",
                "description": "聚类管理接口",
            },
            {
                "name": "Reports",
                "description": "报告获取接口",
            },
            {
                "name": "Feedback",
                "description": "反馈管理接口",
            },
        ],
        lifespan=lifespan,
    )

    cors_origins = tuple(allowed_origins) if allowed_origins is not None else ()
    cors_methods = tuple(allowed_methods) if allowed_methods is not None else _DEFAULT_CORS_METHODS
    cors_headers = tuple(allowed_headers) if allowed_headers is not None else _DEFAULT_CORS_HEADERS

    # 认证和速率限制中间件
    token_validator = TokenValidator(valid_tokens, allow_unauthenticated)
    rate_limiter = RateLimiter(requests_per_minute=rate_limit_requests)
    setup_middleware(app, token_validator, rate_limiter, allow_unauthenticated)

    if not api_docs_enabled:

        @app.middleware("http")
        async def hide_disabled_docs(
            request: Request,
            call_next: Callable[[Request], Awaitable[Response]],
        ) -> Response:
            if request.url.path in _API_DOCS_PATHS:
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content={"detail": "Not Found"},
                )
            return await call_next(request)

    # CORS 中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=bool(cors_origins) and "*" not in cors_origins,
        allow_methods=cors_methods,
        allow_headers=cors_headers,
    )

    # 注册路由
    app.include_router(health.router, prefix="")
    app.include_router(analyze.router, prefix="")
    app.include_router(clusters.router, prefix="")
    app.include_router(reports.router, prefix="")
    app.include_router(feedback.router, prefix="")

    @app.get("/", tags=["Root"])
    async def root() -> dict[str, str]:
        """根路径"""
        response = {
            "message": "Welcome to Fault Review Analyzer API",
            "health": "/health",
        }
        if api_docs_enabled:
            response["docs"] = "/docs"
        return response

    return app


def main() -> None:
    """
    启动服务器的主函数

    使用方式:
        python -m src.api.server
    """
    import uvicorn

    # 从环境变量获取配置
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    valid_tokens_env = os.getenv("API_VALID_TOKENS", "")
    rate_limit = int(os.getenv("API_RATE_LIMIT", "60"))
    allow_unauthenticated = parse_environment_bool("API_ALLOW_UNAUTHENTICATED")
    api_docs_enabled = parse_environment_bool("API_DOCS_ENABLED")
    allowed_origins = parse_environment_list("API_CORS_ORIGINS")
    allowed_methods = parse_environment_list("API_CORS_METHODS", _DEFAULT_CORS_METHODS)
    allowed_headers = parse_environment_list("API_CORS_HEADERS", _DEFAULT_CORS_HEADERS)

    # 解析有效 tokens
    valid_tokens = None
    if valid_tokens_env:
        valid_tokens = {token.strip() for token in valid_tokens_env.split(",")}

    # 创建应用
    app = create_app(
        valid_tokens=valid_tokens,
        rate_limit_requests=rate_limit,
        allow_unauthenticated=allow_unauthenticated,
        api_docs_enabled=api_docs_enabled,
        allowed_origins=allowed_origins,
        allowed_methods=allowed_methods,
        allowed_headers=allowed_headers,
    )

    # 启动服务器
    logger.info(f"Starting server on {host}:{port}")
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
