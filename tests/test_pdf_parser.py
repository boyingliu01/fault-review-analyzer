"""Tests for PDF rule parser (REQ-5, Issue #7)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from src.core.exceptions import DataProcessingError
from src.rules.models import Rule
from src.rules.pdf_parser import PDFRuleParser


def _mock_parse(parser: PDFRuleParser, text: str) -> list[Rule]:
    """Helper: bypass file check and directly parse text."""
    return parser._parse_rules_from_text(text)


class TestPDFRuleParser:
    """Test PDF rule extraction."""

    def test_parser_creation(self) -> None:
        """PDFRuleParser can be created."""
        parser = PDFRuleParser()
        assert parser is not None

    def test_parse_nonexistent_file_raises(self) -> None:
        """Parsing a non-existent file raises DataProcessingError."""
        parser = PDFRuleParser()
        with pytest.raises(DataProcessingError, match="not found|does not exist"):
            parser.parse(Path("/nonexistent/file.pdf"))

    def test_parse_returns_list_of_rules(self) -> None:
        """parse() returns a list of Rule objects."""
        parser = PDFRuleParser()
        mock_text = """
        规则名称: 空异常捕获
        描述: 不应捕获空的异常对象
        严重级别: high
        分类: 代码质量

        规则名称: SQL注入风险
        描述: 禁止拼接SQL语句
        严重级别: critical
        分类: 安全性
        """
        rules = _mock_parse(parser, mock_text)
        assert isinstance(rules, list)
        assert all(isinstance(r, Rule) for r in rules)

    def test_parse_extracts_rule_fields(self) -> None:
        """Parsed rules have correct fields."""
        parser = PDFRuleParser()
        mock_text = """
        规则名称: 空异常捕获
        描述: 不应捕获空的异常对象
        严重级别: high
        分类: 代码质量
        """
        rules = _mock_parse(parser, mock_text)
        assert len(rules) >= 1
        rule = rules[0]
        assert rule.name == "空异常捕获"
        assert rule.description == "不应捕获空的异常对象"
        assert rule.severity == "high"
        assert rule.category == "代码质量"

    def test_parse_handles_missing_fields(self) -> None:
        """Parser handles rules with missing optional fields gracefully."""
        parser = PDFRuleParser()
        mock_text = """
        规则名称: 简单规则
        描述: 只有名称和描述
        """
        rules = _mock_parse(parser, mock_text)
        assert len(rules) >= 1
        rule = rules[0]
        assert rule.name == "简单规则"
        assert rule.severity == "medium"  # default

    def test_parse_empty_pdf_returns_empty(self) -> None:
        """Empty PDF content returns empty rule list."""
        parser = PDFRuleParser()
        rules = _mock_parse(parser, "")
        assert rules == []

    def test_parse_unavailable_library_graceful(self) -> None:
        """If PDF library unavailable, raises DataProcessingError with hint."""
        parser = PDFRuleParser()
        pdf_path = Path("/fake/test.pdf")
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch.object(parser, "_extract_text", side_effect=ImportError("no pymupdf")),
            pytest.raises(DataProcessingError, match="PDF|library|install"),
        ):
            parser.parse(pdf_path)


class TestPDFRuleParserIntegration:
    """Integration tests with actual text parsing."""

    def test_parse_multiple_rules_from_text(self) -> None:
        """Parser correctly splits multiple rules from text."""
        parser = PDFRuleParser()
        mock_text = """
        === 规范规则列表 ===

        规则名称: 规则A
        描述: 描述A
        严重级别: low
        分类: 测试

        规则名称: 规则B
        描述: 描述B
        严重级别: high
        分类: 安全

        规则名称: 规则C
        描述: 描述C
        严重级别: critical
        分类: 性能
        """
        rules = _mock_parse(parser, mock_text)
        assert len(rules) == 3
        names = [r.name for r in rules]
        assert "规则A" in names
        assert "规则B" in names
        assert "规则C" in names
