"""Tests for the report generator with enhanced functionality."""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from src.report.generator import (
    ChartData,
    ReportData,
    ReportFormat,
    ReportGenerator,
    ReportType,
    TableData,
)


class TestReportGeneratorEnhanced:
    """Tests for the ReportGenerator class with enhanced features."""

    @pytest.fixture
    def temp_output_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def sample_report_data(self):
        """Create a sample ReportData object for testing."""
        return ReportData(
            title="Sample Report",
            type=ReportType.SUMMARY,
            generated_at=datetime.now(),
            summary={
                "total_items": 100,
                "passed": 85,
                "failed": 15,
                "pass_rate": "85%",
            },
            charts=[
                ChartData(
                    type="bar",
                    title="Pass/Fail Distribution",
                    labels=["Pass", "Fail"],
                    datasets=[
                        {
                            "label": "Count",
                            "data": [85, 15],
                            "backgroundColor": ["#28a745", "#dc3545"],
                        }
                    ],
                ),
            ],
            tables=[
                TableData(
                    title="Test Results",
                    headers=["Item", "Status"],
                    rows=[
                        ["Item 1", "Pass"],
                        ["Item 2", "Fail"],
                        ["Item 3", "Pass"],
                    ],
                ),
            ],
        )

    def test_constructor_with_no_parameters(self):
        """Test creating a ReportGenerator instance without parameters."""
        generator = ReportGenerator()
        assert generator is not None
        assert generator.output_dir is None
        assert generator.templates_dir is not None

    def test_constructor_with_custom_output_dir(self, temp_output_dir):
        """Test creating a ReportGenerator instance with custom output directory."""
        generator = ReportGenerator(output_dir=temp_output_dir)
        assert generator.output_dir == temp_output_dir

    def test_constructor_with_custom_templates_dir(self, temp_output_dir):
        """Test creating a ReportGenerator instance with custom templates directory."""
        templates_dir = temp_output_dir / "templates"
        templates_dir.mkdir()
        generator = ReportGenerator(template_dir=templates_dir)
        assert generator.templates_dir == templates_dir

    def test_generate_html_report_with_filename(self, temp_output_dir, sample_report_data):
        """Test generating an HTML report with a specific filename."""
        generator = ReportGenerator(output_dir=temp_output_dir)
        output_path = generator.generate(sample_report_data, ReportFormat.HTML, "custom_report")

        assert output_path is not None
        assert isinstance(output_path, Path)
        assert output_path.exists()
        assert "custom_report" in str(output_path)
        assert output_path.suffix == ".html"

    def test_generate_json_report_with_filename(self, temp_output_dir, sample_report_data):
        """Test generating a JSON report with a filename."""
        generator = ReportGenerator(output_dir=temp_output_dir)
        output_path = generator.generate(sample_report_data, ReportFormat.JSON, "auto_report")

        assert output_path is not None
        assert isinstance(output_path, Path)
        assert output_path.exists()
        assert ".json" in str(output_path)

    @patch("src.report.generator.ReportGenerator._generate_content")
    def test_generate_with_format_json(self, mock_generate_content, temp_output_dir, sample_report_data):
        """Test generating a report with JSON format."""
        mock_generate_content.return_value = '{"title": "Test Report"}'

        generator = ReportGenerator(output_dir=temp_output_dir)
        output = generator.generate(sample_report_data, ReportFormat.JSON, "test_report")

        mock_generate_content.assert_called_once()
        assert output is not None

    def test_generate_with_invalid_format(self, temp_output_dir, sample_report_data):
        """Test generating a report with an invalid format."""
        generator = ReportGenerator(output_dir=temp_output_dir)
        with pytest.raises(ValueError):
            generator.generate(sample_report_data, "invalid_format")

    def test_save_report_to_file(self, temp_output_dir, sample_report_data):
        """Test saving report to file directly."""
        generator = ReportGenerator(output_dir=temp_output_dir)

        # First generate content
        content = generator.generate(sample_report_data, ReportFormat.MARKDOWN)
        assert content is not None

        # Test saving to file
        output_path = temp_output_dir / "test_report.md"
        generator.save_report(content, output_path)
        assert output_path.exists()

        # Verify content
        with open(output_path) as f:
            file_content = f.read()
            assert "Sample Report" in file_content

    def test_get_default_templates_dir(self):
        """Test getting the default templates directory."""
        generator = ReportGenerator()
        assert generator.templates_dir is not None
        assert isinstance(generator.templates_dir, Path)

    def test_validate_data_with_valid_data(self, temp_output_dir, sample_report_data):
        """Test validating report data with valid data."""
        generator = ReportGenerator(output_dir=temp_output_dir)
        is_valid, errors = generator.validate_data(sample_report_data)
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_data_with_empty_title(self, temp_output_dir, sample_report_data):
        """Test validating report data with empty title."""
        sample_report_data.title = ""
        generator = ReportGenerator(output_dir=temp_output_dir)
        is_valid, errors = generator.validate_data(sample_report_data)
        assert is_valid is False
        assert len(errors) > 0

    def test_validate_data_with_invalid_type(self, temp_output_dir):
        """Test validating report data with invalid type."""
        generator = ReportGenerator(output_dir=temp_output_dir)
        is_valid, errors = generator.validate_data("not_a_report_data")
        assert is_valid is False
        assert len(errors) > 0

    def test_generate_with_no_filename_or_output_dir(self, sample_report_data):
        """Test generating a report without filename or output directory (return content)."""
        generator = ReportGenerator()
        result = generator.generate(sample_report_data, ReportFormat.MARKDOWN)
        assert isinstance(result, str)
        assert len(result) > 0
