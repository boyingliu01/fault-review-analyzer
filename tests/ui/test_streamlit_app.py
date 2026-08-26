"""Streamlit 复盘结果页测试套件。

测试精简后的复盘分析界面（仅保留复盘结果展示，数据来自 output/progress_*.json）。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.ui.streamlit_app import FaultAnalysisUI


class TestFaultAnalysisUI:
    """复盘分析 UI 测试"""

    def test_create_ui(self):
        """测试创建 UI 实例（不依赖 ChromaDB）。"""
        ui = FaultAnalysisUI()
        assert ui is not None

    @patch("src.ui.streamlit_app.st")
    def test_render_review_no_data(self, mock_st):
        """测试无分析结果时显示提示。"""
        with patch("src.ui.review_data.load_review_records", return_value={}):
            mock_st.session_state = {}

            ui = FaultAnalysisUI()
            ui._render_review()

            # 应显示警告（无数据）
            mock_st.warning.assert_called_once()

    @patch("src.ui.streamlit_app.st")
    def test_render_review_with_data(self, mock_st):
        """测试有分析结果时正常渲染。"""
        mock_recs = {
            11974219: {
                "urId": 11974219,
                "title": "测试故障",
                "root_causes": [
                    {"cause_type": "编码错误", "description": "逻辑错误", "confidence": 0.9}
                ],
                "violations": [{"rule_id": "security-001", "rule_name": "安全规范", "severity": "high"}],
                "improvements": [
                    {"priority": "high", "measure": "加强代码审查", "acceptance_criteria": "审查通过"}
                ],
                "has_code_change": True,
                "processing_time": 20.5,
            }
        }
        with patch("src.ui.review_data.load_review_records", return_value=mock_recs):
            mock_st.session_state = {}
            # 模拟 columns 返回 4 个上下文管理器
            mock_st.columns.return_value = [MagicMock(), MagicMock(), MagicMock(), MagicMock()]

            ui = FaultAnalysisUI()
            ui._render_review()

            # 应显示标题和统计
            mock_st.title.assert_called_once()
            mock_st.metric.assert_called()

    @patch("src.ui.streamlit_app.st")
    def test_render_review_error(self, mock_st):
        """测试加载失败时显示错误。"""
        with patch(
            "src.ui.review_data.load_review_records", side_effect=Exception("加载失败")
        ):
            mock_st.session_state = {}

            ui = FaultAnalysisUI()
            ui._render_review()

            # 应显示错误
            mock_st.error.assert_called_once()
