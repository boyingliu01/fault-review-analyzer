"""启动 API 服务器"""

import os
import sys
from pathlib import Path

# 添加上级目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api.server import create_app


def main():
    """主函数"""
    print("=" * 60)
    print("  Fault Review Analyzer API Server")
    print("=" * 60)

    # 从环境变量获取配置
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))

    # 检查是否有 API 令牌配置
    api_tokens_env = os.getenv("API_VALID_TOKENS", "")
    if api_tokens_env:
        valid_tokens = set(t.strip() for t in api_tokens_env.split(","))
        print(f"\n✓ API token authentication enabled ({len(valid_tokens)} tokens)")
    else:
        valid_tokens = None
        print("\n⚠️  API token authentication disabled (development mode)")

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
    print("\n  API Docs:")
    print(f"  - Swagger: http://{host}:{port}/docs")
    print(f"  - ReDoc:   http://{host}:{port}/redoc")
    print("=" * 60 + "\n")

    # 创建应用
    app = create_app(
        valid_tokens=valid_tokens,
        rate_limit_requests=int(os.getenv("API_RATE_LIMIT", "60")),
    )

    # 启动服务器
    import uvicorn

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True,
    )


if __name__ == "__main__":
    main()
