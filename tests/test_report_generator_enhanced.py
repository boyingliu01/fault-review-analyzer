"""Enhanced tests for ReportGenerator with multiple output formats."""

import tempfile
from pathlib import Path
from datetime import datetime

import pytest

from src.report.generator import ReportGenerator, ReportFormat, ReportData, ChartData, TableData
from src.report.models import BatchReport, ClusterReport


class TestReportGeneratorEnhanced:
    """Tests for ReportGenerator with multiple output formats."""

    @pytest.fixture
    def sample_task_data(self):
        """Create sample task data for testing."""
        return {
            "task_id": 123,
            "title": "测试任务",
            "summary": "测试总结",
        }

    @pytest.fixture
    def sample_labels(self):
        """Create sample labels for testing."""
        return [
            {
                "name": "性能问题",
                "category": "performance",
                "confidence": 0.8,
                "description": "性能瓶颈",
            },
        ]

    @pytest.fixture
    def sample_root_causes(self):
        """Create sample root causes for testing."""
        return [
            {
                "cause_type": "编码错误",
                "description": "代码逻辑错误",
                "evidence": ["证据1"],
                "confidence": 0.9,
            }
        ]

    @pytest.fixture
    def sample_cluster_report(self):
        """Create sample cluster report for testing."""
        return ClusterReport(
            cluster_id=1,
            task_count=10,
            labels=[{"name": "性能问题", "category": "perf"}],
            common_root_causes=[],
            summary="这是一个聚类",
            suggestions=["建议1"],
        )

    @pytest.fixture
    def sample_batch_report(self):
        """Create sample batch report for testing."""
        return BatchReport(
            total_tasks=100,
            cluster_count=5,
            cluster_reports=[
                ClusterReport(
                    cluster_id=1,
                    task_count=20,
                    labels=[],
                    common_root_causes=[],
                    summary="聚类1",
                    suggestions=[],
                )
            ],
            overall_summary="批量分析总结",
            recommendations=["建议1"],
        )

    def test_generate_single_markdown_format(self, sample_task_data):
        """Test generate_single with MARKDOWN format."""
        generator = ReportGenerator()
        report = generator.generate_single(sample_task_data, format=ReportFormat.MARKDOWN)
        assert "故障复盘分析报告" in report
        assert "测试任务" in report

    def test_generate_single_html_format(self, sample_task_data):
        """Test generate_single with HTML format."""
        generator = ReportGenerator()
        report = generator.generate_single(sample_task_data, format=ReportFormat.HTML)
        assert "<!DOCTYPE html>" in report
        assert "故障复盘分析报告" in report

    def test_generate_single_pdf_format(self, sample_task_data):
        """Test generate_single with PDF format."""
        generator = ReportGenerator()
        report = generator.generate_single(sample_task_data, format=ReportFormat.PDF)
        assert "<!DOCTYPE html>" in report

    def test_generate_single_json_format(self, sample_task_data):
        """Test generate_single with JSON format."""
        generator = ReportGenerator()
        report = generator.generate_single(sample_task_data, format=ReportFormat.JSON)
        assert '"task_data"' in report
        assert '"测试任务"' in report

    def test_generate_single_unsupported_format(self, sample_task_data):
        """Test generate_single with unsupported format."""
        generator = ReportGenerator()
        with pytest.raises(ValueError, match="Unsupported report format"):
            generator.generate_single(sample_task_data, format="unsupported")

    def test_generate_cluster_markdown_format(self, sample_cluster_report):
        """Test generate_cluster with MARKDOWN format."""
        generator = ReportGenerator()
        report = generator.generate_cluster(sample_cluster_report, format=ReportFormat.MARKDOWN)
        assert "聚类分析报告" in report

    def test_generate_cluster_json_format(self, sample_cluster_report):
        """Test generate_cluster with JSON format."""
        generator = ReportGenerator()
        report = generator.generate_cluster(sample_cluster_report, format=ReportFormat.JSON)
        assert '"cluster_id": 1' in report
        assert '"task_count": 10' in report

    def test_generate_cluster_unsupported_format(self, sample_cluster_report):
        """Test generate_cluster with unsupported format."""
        generator = ReportGenerator()
        with pytest.raises(ValueError, match="Unsupported report format"):
            generator.generate_cluster(sample_cluster_report, format=ReportFormat.HTML)

    def test_generate_batch_markdown_format(self, sample_batch_report):
        """Test generate_batch with MARKDOWN format."""
        generator = ReportGenerator()
        report = generator.generate_batch(sample_batch_report, format=ReportFormat.MARKDOWN)
        assert "批量故障分析报告" in report

    def test_generate_batch_json_format(self, sample_batch_report):
        """Test generate_batch with JSON format."""
        generator = ReportGenerator()
        report = generator.generate_batch(sample_batch_report, format=ReportFormat.JSON)
        assert '"total_tasks": 100' in report
        assert '"cluster_count": 5' in report

    def test_generate_batch_unsupported_format(self, sample_batch_report):
        """Test generate_batch with unsupported format."""
        generator = ReportGenerator()
        with pytest.raises(ValueError, match="Unsupported report format"):
            generator.generate_batch(sample_batch_report, format=ReportFormat.HTML)

    def test_generate_report_data_html_format(self):
        """Test generate with ReportData in HTML format."""
        generator = ReportGenerator()
        report_data = ReportData(
            title="测试报告",
            type=ReportFormat.MARKDOWN,
            generated_at=datetime.now(),
            summary={"total": 10, "success": 8},
        )
        content = generator._generate_content(report_data, ReportFormat.HTML)
        assert "<!DOCTYPE html>" in content
        assert "测试报告" in content

    def test_generate_report_data_json_format(self):
        """Test generate with ReportData in JSON format."""
        generator = ReportGenerator()
        report_data = ReportData(
            title="测试报告",
            type=ReportFormat.MARKDOWN,
            generated_at=datetime.now(),
            summary={"total": 10, "success": 8},
        )
        content = generator._generate_content(report_data, ReportFormat.JSON)
        assert '"title": "测试报告"' in content

    def test_get_format_extension(self):
        """Test _get_format_extension method."""
        generator = ReportGenerator()
        assert generator._get_format_extension(ReportFormat.MARKDOWN) == "md"
        assert generator._get_format_extension(ReportFormat.HTML) == "html"
        assert generator._get_format_extension(ReportFormat.PDF) == "pdf"
        assert generator._get_format_extension(ReportFormat.JSON) == "json"

    def test_generate_single_with_all_data_html(self, sample_task_data):
        """Test generate_single with all data types in HTML format."""
        generator = ReportGenerator()
        segments = [{"type": "开发阶段", "content": "开发内容"}]
        labels = [{"name": "bug", "category": "issue", "confidence": 0.9, "description": "Bug"}]
        root_causes = [{"cause_type": "代码错误", "description": "描述", "evidence": ["证据"], "confidence": 0.8}]
        suggestions = ["建议1", "建议2"]

        report = generator.generate_single(
            sample_task_data,
            segments=segments,
            labels=labels,
            root_causes=root_causes,
            suggestions=suggestions,
            format=ReportFormat.HTML,
        )

        assert "<!DOCTYPE html>" in report
        assert "开发阶段" in report
        assert "bug" in report
        assert "代码错误" in report
        assert "建议1" in report
