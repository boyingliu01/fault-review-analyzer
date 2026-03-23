"""E2E 测试 fixtures"""

import os
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def env_vars():
    """环境变量 fixture"""
    return {
        "API_API_KEY": os.getenv("API_API_KEY", ""),
        "API_BASE_URL": os.getenv("API_BASE_URL", "https://dev.iwhalecloud.com"),
        "API_PATH_PREFIX": os.getenv(
            "API_PATH_PREFIX", "/portal/ai-gateway/devspace/rpc/v3/work-item"
        ),
        "LLM_PROVIDER": os.getenv("LLM_PROVIDER", "volcengine"),
    }


@pytest.fixture(scope="session")
def project_root() -> Path:
    """项目根目录"""
    return Path(__file__).parent.parent.parent


@pytest.fixture(scope="session")
def chroma_persist_dir(project_root: Path) -> Path:
    """Chroma 持久化目录"""
    return project_root / "data" / "chroma"


@pytest.fixture(scope="session")
def test_output_dir(project_root: Path) -> Path:
    """测试输出目录"""
    output = project_root / "output" / "e2e"
    output.mkdir(parents=True, exist_ok=True)
    return output
