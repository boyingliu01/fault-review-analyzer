"""FastAPI 服务 - 故障复盘分析 API 服务器"""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from src.api.middleware import RateLimiter, TokenValidator, setup_middleware
from src.api.routes import analyze, clusters, feedback, health, reports


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
) -> FastAPI:
    """
    创建 FastAPI 应用

    Args:
        valid_tokens: 有效的 API Token 集合
        rate_limit_requests: 每分钟请求限制数
        allow_unauthenticated: 是否显式允许无认证访问

    Returns:
        FastAPI: 配置好的 FastAPI 应用实例
    """
    app = FastAPI(
        title="Fault Review Analyzer API",
        description="AI驱动的故障复盘分析工具 API 服务",
        version="0.1.0",
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

    # CORS 中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生产环境应设置具体的允许域名
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 认证和速率限制中间件
    token_validator = TokenValidator(valid_tokens, allow_unauthenticated)
    rate_limiter = RateLimiter(requests_per_minute=rate_limit_requests)
    setup_middleware(app, token_validator, rate_limiter, allow_unauthenticated)

    # 注册路由
    app.include_router(health.router, prefix="")
    app.include_router(analyze.router, prefix="")
    app.include_router(clusters.router, prefix="")
    app.include_router(reports.router, prefix="")
    app.include_router(feedback.router, prefix="")

    @app.get("/", tags=["Root"])
    async def root() -> dict[str, str]:
        """根路径"""
        return {
            "message": "Welcome to Fault Review Analyzer API",
            "docs": "/docs",
            "health": "/health",
        }

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

    # 解析有效 tokens
    valid_tokens = None
    if valid_tokens_env:
        valid_tokens = {token.strip() for token in valid_tokens_env.split(",")}

    # 创建应用
    app = create_app(
        valid_tokens=valid_tokens,
        rate_limit_requests=rate_limit,
        allow_unauthenticated=allow_unauthenticated,
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
