"""可视化图表测试套件"""

import pytest
from pathlib import Path

from src.visualization.charts import (
    RootCauseChart,
    ViolationChart,
    ImprovementTrackingChart,
    DashboardGenerator,
)
from src.analysis.improvement_recommender import ImprovementMeasure


class TestRootCauseChart:
    """根因分布图测试"""

    def test_create_bar_chart(self, tmp_path):
        """测试创建根因分布柱状图"""
        chart = RootCauseChart()
        
        root_causes = {
            "需求遗漏": 15,
            "代码bug": 20,
            "设计缺陷": 10,
            "配置错误": 5,
        }
        
        output_path = tmp_path / "root_cause.html"
        result = chart.create_bar_chart(
            root_causes,
            output_path=output_path,
        )
        
        assert result is True
        assert output_path.exists()

    def test_create_bar_chart_empty(self):
        """测试空数据"""
        chart = RootCauseChart()
        result = chart.create_bar_chart({})
        assert result is False


class TestViolationChart:
    """违规类型分布图测试"""

    def test_create_pie_chart(self, tmp_path):
        """测试创建违规类型饼图"""
        chart = ViolationChart()
        
        violations = {
            "Java异常处理规范": 8,
            "数据库连接规范": 5,
            "日志规范": 3,
        }
        
        output_path = tmp_path / "violation.html"
        result = chart.create_pie_chart(
            violations,
            output_path=output_path,
        )
        
        assert result is True
        assert output_path.exists()

    def test_create_pie_chart_empty(self):
        """测试空数据"""
        chart = ViolationChart()
        result = chart.create_pie_chart({})
        assert result is False


class TestImprovementTrackingChart:
    """改进措施追踪图测试"""

    def test_create_priority_chart(self, tmp_path):
        """测试创建优先级分布图"""
        chart = ImprovementTrackingChart()
        
        measures = [
            ImprovementMeasure(
                root_cause="需求遗漏",
                measure="建立评审机制",
                acceptance_criteria="覆盖率100%",
                expected_impact="减少30%",
                priority="high",
            ),
            ImprovementMeasure(
                root_cause="代码bug",
                measure="加强CR",
                acceptance_criteria="CR率100%",
                expected_impact="减少20%",
                priority="medium",
            ),
        ]
        
        output_path = tmp_path / "improvement_priority.html"
        result = chart.create_priority_chart(
            measures,
            output_path=output_path,
        )
        
        assert result is True
        assert output_path.exists()

    def test_create_detail_chart(self, tmp_path):
        """测试创建详情图"""
        chart = ImprovementTrackingChart()
        
        measures = [
            ImprovementMeasure(
                root_cause="需求遗漏",
                measure="建立评审机制",
                acceptance_criteria="覆盖率100%",
                expected_impact="减少30%",
                priority="high",
            ),
        ]
        
        output_path = tmp_path / "improvement_detail.html"
        result = chart.create_detail_chart(
            measures,
            output_path=output_path,
        )
        
        assert result is True
        assert output_path.exists()

    def test_create_chart_empty(self):
        """测试空数据"""
        chart = ImprovementTrackingChart()
        result = chart.create_priority_chart([])
        assert result is False


class TestDashboardGenerator:
    """仪表板生成器测试"""

    def test_generate_full_dashboard(self, tmp_path):
        """测试生成完整仪表板"""
        dashboard = DashboardGenerator()
        
        root_causes = {"需求遗漏": 15, "代码bug": 20}
        violations = {"Java规范": 8, "数据库规范": 5}
        measures = [
            ImprovementMeasure(
                root_cause="需求遗漏",
                measure="建立评审机制",
                acceptance_criteria="覆盖率100%",
                expected_impact="减少30%",
                priority="high",
            ),
        ]
        
        results = dashboard.generate_full_dashboard(
            root_causes,
            violations,
            measures,
            output_dir=tmp_path,
        )
        
        assert len(results) >= 3
        for path in results.values():
            assert Path(path).exists()
