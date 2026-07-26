"""E2E 测试共享 fixtures"""

import asyncio
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()


def pytest_collection_modifyitems(
    session: pytest.Session, config: pytest.Config, items: list[pytest.Item]
) -> None:
    """自动给 e2e 目录下所有测试打上 e2e marker，方便 hook 用 -m 'not e2e' 排除。"""
    e2e_marker = pytest.mark.e2e
    e2e_root = Path(__file__).parent
    for item in items:
        if e2e_root in item.path.parents:
            item.add_marker(e2e_marker)


@pytest.fixture(scope="session")
def api_key() -> str:
    """获取 API 密钥"""
    key = os.getenv("DEVCLOUD_TOKEN", "")
    if not key:
        pytest.skip("未配置 DEVCLOUD_TOKEN 环境变量")
    return key


@pytest.fixture(scope="session")
def api_base_url() -> str:
    """获取 API 基础 URL"""
    return os.getenv("API_BASE_URL", "https://dev.iwhalecloud.com")


@pytest.fixture(scope="session")
def api_path_prefix() -> str:
    """获取 API 路径前缀"""
    return os.getenv("API_PATH_PREFIX", "/portal/ai-gateway/devspace/rpc/v3/work-item")


@pytest.fixture(scope="session")
def test_data_file() -> Path:
    """测试数据文件路径"""
    return Path(__file__).parent.parent.parent / "data" / "测试用故障单号列表.xlsx"


@pytest.fixture(scope="session")
def small_test_ids(test_data_file: Path) -> list[str]:
    """返回少量测试用故障单号（用于快速 E2E 测试）"""
    import pandas as pd

    if not test_data_file.exists():
        pytest.skip(f"测试数据文件不存在: {test_data_file}")

    df = pd.read_excel(test_data_file)
    return [str(x) for x in df["故障单号"].head(3).tolist()]


@pytest.fixture(scope="session")
def output_dir() -> Path:
    """输出目录"""
    return Path(__file__).parent.parent.parent / "output" / "e2e"


