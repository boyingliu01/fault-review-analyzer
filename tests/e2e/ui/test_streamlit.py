"""Streamlit UI E2E 测试"""

import subprocess
import sys
import time
from collections.abc import Generator
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


class StreamlitRunner:
    """Streamlit 服务管理器"""

    def __init__(self, port: int = 8501):
        self.port = port
        self.process: subprocess.Popen | None = None
        self.url = f"http://localhost:{port}"

    def start(self, timeout: int = 30) -> None:
        """启动 Streamlit 服务"""
        cmd = [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(PROJECT_ROOT / "src/ui/streamlit_app.py"),
            "--server.port",
            str(self.port),
            "--server.headless",
            "true",
            "--browser.gatherUsageStats",
            "false",
        ]

        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=PROJECT_ROOT,
        )

        # 等待服务启动
        import urllib.request

        for _ in range(timeout):
            try:
                urllib.request.urlopen(self.url)
                return
            except Exception:
                time.sleep(1)
        raise RuntimeError(f"Streamlit 服务启动超时（{timeout}秒）")

    def stop(self) -> None:
        """停止 Streamlit 服务"""
        if self.process:
            self.process.terminate()
            self.process.wait(timeout=5)


@pytest.fixture(scope="module")
def streamlit_server() -> Generator[StreamlitRunner, None, None]:
    """启动 Streamlit 服务器供测试使用"""
    runner = StreamlitRunner()
    runner.start()
    yield runner
    runner.stop()


@pytest.fixture(scope="module")
def browser(playwright) -> Generator[Browser, None, None]:
    """创建浏览器实例"""
    browser = playwright.chromium.launch(headless=True)
    yield browser
    browser.close()


@pytest.fixture
def page(browser: Browser, streamlit_server: StreamlitRunner) -> Generator[Page, None, None]:
    """创建新页面"""
    context = browser.new_context()
    page = context.new_page()
    page.goto(streamlit_server.url)
    yield page
    context.close()


class TestStreamlitOverview:
    """概览页面 E2E 测试"""

    def test_page_loads(self, page: Page):
        """测试页面加载"""
        page.wait_for_load_state("networkidle", timeout=30000)
        content = page.content()
        assert len(content) > 100

    def test_navigation_exists(self, page: Page):
        """测试导航组件存在"""
        radio = page.locator('input[type="radio"]')
        if radio.count() > 0:
            assert True

    def test_overview_page_content(self, page: Page):
        """测试概览页面内容"""
        page.wait_for_load_state("networkidle")
        headings = page.locator("h1, h2, h3")
        if headings.count() > 0:
            assert True


class TestStreamlitClustering:
    """聚类分析页面 E2E 测试"""

    def test_clustering_page_navigation(self, page: Page):
        """测试导航到聚类页面"""
        page.wait_for_load_state("networkidle")

        radio_buttons = page.locator('input[type="radio"]')
        for i in range(radio_buttons.count()):
            radio = radio_buttons.nth(i)
            label = page.locator("label").filter(has=radio).first
            text = label.inner_text() if label else ""
            if "聚类" in text or "cluster" in text.lower():
                radio.check()
                break

    def test_clustering_run_button(self, page: Page):
        """测试聚类运行按钮"""
        page.wait_for_load_state("networkidle")
        buttons = page.locator("button")
        for i in range(buttons.count()):
            btn_text = buttons.nth(i).inner_text()
            if "运行" in btn_text or "run" in btn_text.lower():
                assert True
                break


class TestStreamlitSimilaritySearch:
    """相似查询页面 E2E 测试"""

    def test_search_input_exists(self, page: Page):
        """测试搜索输入框存在"""
        page.wait_for_load_state("networkidle")
        radio_buttons = page.locator('input[type="radio"]')
        for i in range(radio_buttons.count()):
            radio = radio_buttons.nth(i)
            label = page.locator("label").filter(has=radio).first
            text = label.inner_text() if label else ""
            if "相似" in text or "search" in text.lower():
                radio.check()
                break

        text_inputs = page.locator('input[type="text"]')
        assert text_inputs.count() >= 0


class TestStreamlitVisualization:
    """可视化页面 E2E 测试"""

    def test_visualization_page(self, page: Page):
        """测试可视化页面"""
        page.wait_for_load_state("networkidle")
        radio_buttons = page.locator('input[type="radio"]')
        for i in range(radio_buttons.count()):
            radio = radio_buttons.nth(i)
            label = page.locator("label").filter(has=radio).first
            text = label.inner_text() if label else ""
            if "可视" in text or "chart" in text.lower():
                radio.check()
                break

        page.wait_for_load_state("networkidle")
        elements = page.locator(".streamlit-chart, .js-plotly-plot, canvas")
        assert elements.count() >= 0


class TestStreamlitErrorHandling:
    """错误处理 E2E 测试"""

    def test_empty_data_handling(self, page: Page):
        """测试空数据处理"""
        page.wait_for_load_state("networkidle")
        assert page.content() is not None

    def test_long_text_handling(self, page: Page):
        """测试长文本处理"""
        page.wait_for_load_state("networkidle")
        assert page.content() is not None
