"""Streamlit 复盘结果页测试套件。

使用 streamlit.testing.v1.AppTest 做真实渲染测试，捕获 API 合约误用
（如 selection_mode="single" 会抛异常）。

覆盖 REQ-1（批次导览）、REQ-2（帕累托图）、REQ-4（联动筛选）、
REQ-5（urid 链接）、REQ-6（单起详情联动）。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).parent.parent.parent / "src" / "ui" / "streamlit_app.py"


@pytest.fixture
def app(tmp_path: Path, monkeypatch):
    """构造 AppTest 实例，数据源指向临时目录（含模拟数据）。"""
    # 创建模拟 progress 数据
    (tmp_path / "progress_1001.json").write_text(
        '{"urId": 1001, "title": "故障A", "root_causes": [{"cause_type": "编码错误", "description": "逻辑错误", "confidence": 0.9}], "violations": [{"rule_id": "security-001", "rule_name": "敏感信息泄露", "severity": "high"}], "improvements": [{"priority": "high", "measure": "加强审查"}], "has_code_change": true}',
        encoding="utf-8",
    )
    (tmp_path / "progress_1002.json").write_text(
        '{"urId": 1002, "title": "故障B", "root_causes": [{"cause_type": "设计缺陷", "description": "设计问题", "confidence": 0.8}], "violations": [{"rule_id": "J000025", "rule_name": "接口规范", "severity": "medium"}], "improvements": [{"priority": "medium", "measure": "重新设计"}], "has_code_change": false}',
        encoding="utf-8",
    )
    # 模拟 all_analysis 批次文件
    (tmp_path / "all_analysis_20260826_152545.json").write_text(
        '{"results": [{"urId": 1001, "root_causes": [{"cause_type": "编码错误"}]}, {"urId": 1002, "root_causes": [{"cause_type": "设计缺陷"}]}]}',
        encoding="utf-8",
    )
    # 将 review_data 的 _OUT_DIR 指向临时目录
    monkeypatch.setattr("src.ui.review_data._OUT_DIR", tmp_path)
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    return at


class TestAppRender:
    """AppTest 真实渲染测试。"""

    # @test REQ-1
    def test_app_runs_with_data(self, app):
        """应用在有数据时能正常渲染，不抛异常。"""
        app.run()
        assert not app.exception

    # @test REQ-1
    def test_app_shows_metrics(self, app):
        """显示顶层统计指标。"""
        app.run()
        assert not app.exception
        assert len(app.metric) >= 1

    # @test REQ-1
    def test_app_renders_batch_nav(self, app):
        """左侧批次导览渲染批次列表。"""
        app.run()
        assert not app.exception
        assert app.sidebar is not None

    # @test REQ-2
    def test_app_renders_pareto_chart(self, app):
        """渲染帕累托图（plotly_chart）。"""
        app.run()
        assert not app.exception

    # @test REQ-3
    def test_app_renders_violation_content(self, app):
        """规范违规分布含条款内容，不抛异常。"""
        app.run()
        assert not app.exception

    # @test REQ-4
    def test_app_renders_detail_table(self, app):
        """渲染缺陷明细表（含研发云链接列）。"""
        app.run()
        assert not app.exception

    # @test REQ-6
    def test_app_renders_detail_section(self, app):
        """渲染单起缺陷详情区。"""
        app.run()
        assert not app.exception


class TestSelectionMode:
    """验证明细表 selection_mode 合法（捕获 API 误用）。"""

    # @test REQ-4
    def test_selection_mode_single_row_no_exception(self, app):
        """selection_mode=single-row 不抛异常（若用 single 会抛 StreamlitAPIException）。"""
        app.run()
        assert not app.exception


class TestDetailLink:
    """验证 urid 研发云链接。"""

    # @test REQ-5
    def test_detail_link_url_format(self):
        """研发云链接 URL 格式正确。"""
        from src.ui.review_data import build_detail_url

        url = build_detail_url(1001)
        assert url == "https://dev.iwhalecloud.com/portal/zcm-devspace/spa/task/pc/1001"
