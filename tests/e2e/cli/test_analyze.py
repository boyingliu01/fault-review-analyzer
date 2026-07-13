"""CLI analyze 命令 E2E 测试"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


class TestCLIAnalyze:
    """CLI analyze 命令端到端测试"""

    def test_analyze_help(self):
        """测试 analyze 命令帮助信息"""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli.main", "analyze", "--help"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0
        assert "analyze" in result.stdout.lower()

    def test_analyze_without_task_id(self):
        """测试未提供 task-id 时的错误处理"""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli.main", "analyze"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        # 应该显示错误或帮助信息
        assert result.returncode != 0 or "task-id" in result.stdout.lower()
