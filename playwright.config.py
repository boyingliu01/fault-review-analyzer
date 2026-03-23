"""Playwright 配置"""

import os
from pathlib import Path

from playwright.sync_api import sync_playwright


def pytest_configure(config):
    """配置 Playwright"""
    config.addinivalue_line("markers", "e2e: end-to-end tests")
    config.addinivalue_line("markers", "ui: UI tests requiring browser")
    config.addinivalue_line("markers", "slow: slow running tests")


def pytest_addoption(parser):
    """添加命令行选项"""
    parser.addoption(
        "--browser",
        action="store",
        default="chromium",
        help="Browser to use: chromium, firefox, or webkit",
    )
    parser.addoption(
        "--headed",
        action="store_true",
        default=False,
        help="Run tests in headed mode",
    )


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args, pytestconfig):
    """配置浏览器启动参数"""
    args = browser_type_launch_args or {}
    if pytestconfig.getoption("--headed"):
        args["headless"] = False
    else:
        args["headless"] = True
    return args


@pytest.fixture(scope="session")
def browser_type(browser_type_launch_args, pytestconfig):
    """获取浏览器类型"""
    return pytestconfig.getoption("--browser")


# Playwright 配置字典（供 Streamlit 测试使用）
PLAYWRIGHT_CONFIG = {
    "headless": True,
    "viewport": {"width": 1280, "height": 720},
    "ignore_https_errors": True,
    "screenshot": "only-on-failure",
    "video": "retain-on-failure",
    "trace": "on-first-retry",
}


# 测试标记
def pytest_collection_modifyitems(config, items):
    """修改测试项"""
    for item in items:
        # UI 测试标记
        if "ui" in item.nodeid or "streamlit" in item.nodeid.lower():
            item.add_marker("ui")
            item.add_marker("e2e")

        # Pipeline 测试标记
        if "pipeline" in item.nodeid or "phase" in item.nodeid.lower():
            item.add_marker("e2e")

        # CLI 测试标记
        if "cli" in item.nodeid:
            item.add_marker("e2e")
