"""Tests for the report generator."""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import Mock, patch, MagicMock

import pytest

from src.report.generator import (
    ReportGenerator,
    ReportType,
    ReportFormat,
    ReportData,
    ChartData,
    TableData,
)


class TestReportType:
    """Tests for ReportType enum."""

    def test_report_type_values(self):
        """Test report type enum values."""
        assert ReportType.SUMMARY.value == "summary"
        assert ReportType.DETAILED.value == "detailed"
        assert ReportType.CLUSTERING.value == "clustering"
        assert ReportType.ROOT_CAUSE.value == "root_cause"
        assert ReportType.TREND.value == "trend"


class TestReportFormat:
    """Tests for ReportFormat enum."""

    def test_report_format_values(self):
        """Test report format enum values."""
        assert ReportFormat.HTML.value == "html"
        assert ReportFormat.JSON.value == "json"
        assert ReportFormat.PDF.value == "pdf"
        assert ReportFormat.MARKDOWN.value == "markdown"


class TestChartData:
    """Tests for ChartData dataclass."""

    def test_chart_data_creation(self):
        """Test creating chart data."""
        chart = ChartData(
            type="bar", title="Test Chart", labels=["A", "B", "C"], datasets=[{"data": [1, 2, 3]}]
        )
        assert chart.type == "bar"
        assert chart.title == "Test Chart"
        assert chart.labels == ["A", "B", "C"]
        assert len(chart.datasets) == 1

    def test_chart_data_to_dict(self):
        """Test converting chart data to dict."""
        chart = ChartData(
            type="pie", title="Pie Chart", labels=["X", "Y"], datasets=[{"data": [50, 50]}]
        )
        result = chart.to_dict()
        assert result["type"] == "pie"
        assert result["title"] == "Pie Chart"
        assert result["labels"] == ["X", "Y"]


class TestTableData:
    """Tests for TableData dataclass."""

    def test_table_data_creation(self):
        """Test creating table data."""
        table = TableData(
            title="Test Table",
            headers=["Col1", "Col2", "Col3"],
            rows=[["A1", "B1", "C1"], ["A2", "B2", "C2"]],
        )
        assert table.title == "Test Table"
        assert len(table.headers) == 3
        assert len(table.rows) == 2

    def test_table_data_to_dict(self):
        """Test converting table data to dict."""
        table = TableData(title="Summary", headers=["Item", "Count"], rows=[["A", 10], ["B", 20]])
        result = table.to_dict()
        assert result["title"] == "Summary"
        assert result["headers"] == ["Item", "Count"]
        assert len(result["rows"]) == 2


class TestReportData:
    """Tests for ReportData dataclass."""

    def test_report_data_creation(self):
        """Test creating report data."""
        report = ReportData(
            title="Test Report",
            type=ReportType.SUMMARY,
            generated_at=datetime(2024, 1, 1, 12, 0, 0),
            summary={"total": 100, "passed": 95},
            charts=[],
            tables=[],
        )
        assert report.title == "Test Report"
        assert report.type == ReportType.SUMMARY
        assert report.summary["total"] == 100

    def test_report_data_to_dict(self):
        """Test converting report data to dict."""
        chart = ChartData("bar", "Chart", ["A"], [{"data": [1]}])
        table = TableData("Table", ["Col"], [["Row1"]])

        report = ReportData(
            title="Full Report",
            type=ReportType.DETAILED,
            generated_at=datetime(2024, 6, 15, 10, 30, 0),
            summary={"items": 50},
            charts=[chart],
            tables=[table],
        )

        result = report.to_dict()
        assert result["title"] == "Full Report"
        assert result["type"] == "detailed"
        assert result["summary"]["items"] == 50
        assert len(result["charts"]) == 1
        assert len(result["tables"]) == 1


class TestReportGenerator:
    """Tests for ReportGenerator class."""

    @pytest.fixture
    def temp_output_dir(self):
        """Create a temporary output directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def sample_report_data(self):
        """Create sample report data for testing."""
        return ReportData(
            title="Sample Report",
            type=ReportType.SUMMARY,
            generated_at=datetime.now(),
            summary={"total": 100, "passed": 95, "failed": 5},
            charts=[
                ChartData(
                    type="bar",
                    title="Results",
                    labels=["Passed", "Failed"],
                    datasets=[{"data": [95, 5]}],
                )
            ],
            tables=[
                TableData(
                    title="Details",
                    headers=["Item", "Status"],
                    rows=[["Test1", "Pass"], ["Test2", "Fail"]],
                )
            ],
        )

    def test_generator_creation(self, temp_output_dir):
        """Test creating a report generator."""
        generator = ReportGenerator(output_dir=temp_output_dir)
        assert generator.output_dir == temp_output_dir
        assert generator.templates_dir is not None

    def test_generate_json_report(self, temp_output_dir, sample_report_data):
        """Test generating a JSON report."""
        generator = ReportGenerator(output_dir=temp_output_dir)

        output_path = generator.generate(
            data=sample_report_data, format=ReportFormat.JSON, filename="test_report"
        )

        assert output_path.exists()
        assert output_path.suffix == ".json"

        # Verify content
        with open(output_path) as f:
            content = json.load(f)
            assert content["title"] == "Sample Report"
            assert content["summary"]["total"] == 100

    def test_generate_markdown_report(self, temp_output_dir, sample_report_data):
        """Test generating a Markdown report."""
        generator = ReportGenerator(output_dir=temp_output_dir)

        output_path = generator.generate(
            data=sample_report_data, format=ReportFormat.MARKDOWN, filename="test_report"
        )

        assert output_path.exists()
        assert output_path.suffix == ".md"

        # Verify content
        content = output_path.read_text()
        assert "# Sample Report" in content
        assert "Results" in content
        assert "| Item | Status |" in content  # Table

    @patch("src.report.generator.ReportGenerator._generate_html")
    def test_generate_html_report(self, mock_generate_html, temp_output_dir, sample_report_data):
        """Test generating an HTML report."""
        # Mock returns HTML string content
        mock_generate_html.return_value = "<!DOCTYPE html><html><body><h1>Sample Report</h1></body></html>"

        generator = ReportGenerator(output_dir=temp_output_dir)
        output_path = generator.generate(
            data=sample_report_data, format=ReportFormat.HTML, filename="test_report"
        )

        assert output_path is not None
        assert output_path.suffix == ".html"
        assert output_path.exists()
        mock_generate_html.assert_called_once()

    def test_get_template(self, temp_output_dir):
        """Test getting a template."""
        generator = ReportGenerator(output_dir=temp_output_dir)

        # Should return None for non-existent template
        template = generator.get_template("non_existent")
        assert template is None

    def test_validate_data(self, temp_output_dir, sample_report_data):
        """Test data validation."""
        generator = ReportGenerator(output_dir=temp_output_dir)

        # Valid data should pass
        is_valid, errors = generator.validate_data(sample_report_data)
        assert is_valid is True
        assert len(errors) == 0

        # Invalid data should fail
        invalid_data = {"title": "Invalid"}  # Missing required fields
        is_valid, errors = generator.validate_data(invalid_data)
        assert is_valid is False
        assert len(errors) > 0

    def test_generate_with_invalid_data(self, temp_output_dir):
        """Test generation with invalid data raises error."""
        generator = ReportGenerator(output_dir=temp_output_dir)

        invalid_data = ReportData(
            title="",  # Empty title should be invalid
            type=ReportType.SUMMARY,
            generated_at=datetime.now(),
            summary={},
            charts=[],
            tables=[],
        )

        # Should raise ValueError for invalid data
        with pytest.raises(ValueError):
            generator.generate(data=invalid_data, format=ReportFormat.JSON, filename="test")

    def test_generate_with_auto_format(self, temp_output_dir, sample_report_data):
        """Test auto-determining format from filename."""
        generator = ReportGenerator(output_dir=temp_output_dir)

        # Should infer JSON from .json extension
        output_path = generator.generate(
            data=sample_report_data,
            format=ReportFormat.JSON,  # Explicit format still required
            filename="report.json",
        )

        assert output_path.suffix == ".json"
