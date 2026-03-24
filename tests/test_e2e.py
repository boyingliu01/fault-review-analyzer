"""端到端测试 - 从API获取真实数据并测试完整流程"""

import os
from pathlib import Path

import pandas as pd
import pytest

from src.api.client import APIClient
from src.preprocessor.processor import DataPreprocessor

# 测试数据文件路径
TEST_DATA_FILE = Path(__file__).parent.parent / "data" / "测试用故障单号列表.xlsx"

# 从环境变量获取API配置
API_BASE_URL = os.getenv("API_BASE_URL", "https://dev.iwhalecloud.com")
DEVCLOUD_TOKEN = os.getenv("DEVCLOUD_TOKEN", "")
API_PATH_PREFIX = os.getenv("API_PATH_PREFIX", "/portal/ai-gateway/devspace/rpc/v3/work-item")


@pytest.fixture
def test_task_ids() -> list[int]:
    """从测试数据文件加载故障单号列表"""
    if not TEST_DATA_FILE.exists():
        pytest.skip(f"测试数据文件不存在: {TEST_DATA_FILE}")

    df = pd.read_excel(TEST_DATA_FILE)
    # 取前5个任务ID用于测试
    return df["故障单号"].head(5).tolist()


@pytest.mark.asyncio
async def test_e2e_fetch_and_preprocess(test_task_ids: list[int]) -> None:
    """端到端测试：从API获取数据并预处理"""
    if not DEVCLOUD_TOKEN:
        pytest.skip("未配置 DEVCLOUD_TOKEN 环境变量")

    async with APIClient(
        base_url=API_BASE_URL,
        token=f"Bearer {DEVCLOUD_TOKEN}",
        api_path_prefix=API_PATH_PREFIX,
    ) as client:
        tasks = []
        for task_id in test_task_ids:
            try:
                task = await client.get_task(int(task_id))
                tasks.append(task)
            except Exception as e:
                # 记录失败但不中断测试
                print(f"获取任务 {task_id} 失败: {e}")

        # 至少成功获取一个任务
        assert len(tasks) > 0, "未能成功获取任何任务"

        # 测试预处理器
        preprocessor = DataPreprocessor()
        processed = preprocessor.process_batch(tasks)

        assert len(processed) == len(tasks)
        for p in processed:
            assert p.combined_text, "combined_text不应为空"
            assert len(p.combined_text) <= 8000, "combined_text不应超过8000字符"
