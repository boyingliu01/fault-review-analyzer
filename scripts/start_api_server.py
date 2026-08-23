"""启动 API 服务器"""

import os
import sys
from pathlib import Path

# 添加上级目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api.server import create_app, parse_environment_bool, parse_environment_list

_DEFAULT_CORS_METHODS = ("GET", "POST", "OPTIONS")
_DEFAULT_CORS_HEADERS = ("Content-Type", "X-API-Token")


def main() -> None:
    """主函数"""
    print("=" * 60)
    print("  Fault Review Analyzer API Server")
    print("=" * 60)

    # 从环境变量获取配置
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    allow_unauthenticated = parse_environment_bool("API_ALLOW_UNAUTHENTICATED")
    api_docs_enabled = parse_environment_bool("API_DOCS_ENABLED")
    allowed_origins = parse_environment_list("API_CORS_ORIGINS")
    allowed_methods = parse_environment_list("API_CORS_METHODS", _DEFAULT_CORS_METHODS)
    allowed_headers = parse_environment_list("API_CORS_HEADERS", _DEFAULT_CORS_HEADERS)

    # 检查是否有 API 令牌配置
    api_tokens_env = os.getenv("API_VALID_TOKENS", "")
    if api_tokens_env:
        valid_tokens = {token.strip() for token in api_tokens_env.split(",")}
        print(f"\n✓ API token authentication enabled ({len(valid_tokens)} tokens)")
    else:
        valid_tokens = None
        print("\n⚠️  No API tokens configured")

    if allow_unauthenticated:
        print("⚠️  Unauthenticated API access enabled (development mode)")

    print(f"✓ Starting server on {host}:{port}")

    print("\n" + "=" * 60)
    print("  Available endpoints:")
    print("=" * 60)
    print(f"  GET   http://{host}:{port}/")
    print(f"  GET   http://{host}:{port}/health")
    print(f"  POST  http://{host}:{port}/analyze")
    print(f"  POST  http://{host}:{port}/analyze/batch")
    print(f"  GET   http://{host}:{port}/clusters")
    print(f"  GET   http://{host}:{port}/clusters/{{cluster_id}}")
    print(f"  GET   http://{host}:{port}/reports/{{task_id}}")
    if api_docs_enabled:
        print("\n  API Docs:")
        print(f"  - Swagger: http://{host}:{port}/docs")
        print(f"  - ReDoc:   http://{host}:{port}/redoc")
    print("=" * 60 + "\n")

    # 创建应用
    app = create_app(
        valid_tokens=valid_tokens,
        rate_limit_requests=int(os.getenv("API_RATE_LIMIT", "60")),
        allow_unauthenticated=allow_unauthenticated,
        api_docs_enabled=api_docs_enabled,
        allowed_origins=allowed_origins,
        allowed_methods=allowed_methods,
        allowed_headers=allowed_headers,
    )

    # 启动服务器
    import uvicorn

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=False,
    )


if __name__ == "__main__":
    main()
