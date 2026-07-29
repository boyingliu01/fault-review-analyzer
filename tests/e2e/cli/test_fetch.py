"""CLI fetch 命令 E2E 测试"""

import subprocess
import sys
from pathlib import Path

import pytest

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


class TestCLIFetch:
    """CLI fetch 命令端到端测试"""

    def test_fetch_help(self):
        """测试 fetch 命令帮助信息"""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli.main", "fetch", "--help"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0
        assert "fetch" in result.stdout.lower()

    @pytest.mark.asyncio
    async def test_fetch_single_task(
        self, api_key: str, api_base_url: str, small_test_ids: list[str]
    ):
        """测试获取单个故障单"""
        from src.api.client import APIClient

        # api_key from fixture already contains "Bearer " prefix
        async with APIClient(
            base_url=api_base_url,
            token=api_key,
            api_path_prefix="/portal/ai-gateway/devspace/rpc/v3/work-item",
        ) as client:
            task = await client.get_task(int(small_test_ids[0]))
            assert task is not None
            assert str(task.task_id) == small_test_ids[0]

    @pytest.mark.asyncio
    async def test_fetch_multiple_tasks(
        self, api_key: str, api_base_url: str, small_test_ids: list[str]
    ):
        """测试批量获取多个故障单"""
        from src.api.client import APIClient

        # api_key from fixture already contains "Bearer " prefix
        async with APIClient(
            base_url=api_base_url,
            token=api_key,
            api_path_prefix="/portal/ai-gateway/devspace/rpc/v3/work-item",
        ) as client:
            tasks = []
            for task_id in small_test_ids[:2]:
                try:
                    task = await client.get_task(int(task_id))
                    if task:
                        tasks.append(task)
                except Exception as e:
                    print(f"获取任务 {task_id} 失败: {e}")

            assert len(tasks) >= 1, "至少成功获取一个任务"
