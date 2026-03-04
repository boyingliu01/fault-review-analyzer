import pytest
from src.report.models import (
    ReportSection,
    AnalysisReport,
    ClusterReport,
    BatchReport,
)


class TestReportModels:
    def test_report_section(self):
        section = ReportSection(
            title="测试章节",
            content="这是测试内容",
            level=1,
        )
        assert section.title == "测试章节"
        assert section.content == "这是测试内容"
        assert section.level == 1

    def test_analysis_report(self):
        report = AnalysisReport(
            task_id=1,
            title="测试报告",
            summary="测试总结",
        )
        assert report.task_id == 1
        assert report.title == "测试报告"
        assert report.summary == "测试总结"
        assert report.labels == []
        assert report.root_causes == []

    def test_cluster_report(self):
        report = ClusterReport(
            cluster_id=1,
            task_count=10,
            labels=[],
            common_root_causes=[],
            summary="聚类总结",
            suggestions=["建议1"],
        )
        assert report.cluster_id == 1
        assert report.task_count == 10
        assert len(report.suggestions) == 1

    def test_batch_report(self):
        cluster_report = ClusterReport(
            cluster_id=1,
            task_count=5,
            labels=[],
            common_root_causes=[],
            summary="总结",
            suggestions=[],
        )
        batch = BatchReport(
            total_tasks=100,
            cluster_count=10,
            cluster_reports=[cluster_report],
            overall_summary="整体总结",
            recommendations=["建议1", "建议2"],
        )
        assert batch.total_tasks == 100
        assert batch.cluster_count == 10
        assert len(batch.cluster_reports) == 1
        assert len(batch.recommendations) == 2
