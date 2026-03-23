"""E2E 测试 Playwright 配置"""

import pytest


def pytest_runtest_setup(item):
    """E2E 测试 setup"""
    # 为带 @pytest.mark.ui 标记的测试确保 Playwright 可用
    if "ui" in [mark.name for mark in item.iter_markers()]:
        # 确保 chromium 可用
        pass


def pytest_runtest_teardown(item):
    """E2E 测试 teardown"""
    pass
