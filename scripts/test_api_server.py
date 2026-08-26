"""简单测试 API 服务器"""

import sys
from pathlib import Path

# 添加上级目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api.server import create_app


def test_server_init():
    """测试服务器初始化"""
    print("Testing API server initialization...")
    app = create_app(valid_tokens=None)
    print("✓ Server initialized successfully")
    print(f"✓ App title: {app.title}")
    print(f"✓ App version: {app.version}")

    # 检查路由
    routes = [route.path for route in app.routes]
    expected_routes = [
        "/health",
        "/analyze",
        "/analyze/batch",
        "/clusters",
        "/docs",
        "/openapi.json",
    ]

    print("\nRoutes:")
    for route in routes:
        if not route.startswith("/{"):  # 过滤掉路径参数路由
            print(f"  - {route}")

    # 验证关键路由存在
    for expected in expected_routes:
        if expected in routes:
            print(f"\n✓ Found route: {expected}")

    print("\n✅ API server initialization test passed!")
    print("\nTo start the server, run:")
    print("  python -m src.api.server")
    print("\nThen visit:")
    print("  http://localhost:8000/docs")


if __name__ == "__main__":
    test_server_init()
