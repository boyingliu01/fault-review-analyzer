"""CLI report 命令 E2E 测试"""

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


class TestCLIReport:
    """CLI report 命令端到端测试"""

    def test_report_help(self):
        """测试 report 命令帮助信息"""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli.main", "report", "--help"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0
        assert "report" in result.stdout.lower()

    def test_report_without_task_id(self):
        """测试未提供 task-id 时的错误处理"""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli.main", "report"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode != 0 or "task-id" in result.stdout.lower()
