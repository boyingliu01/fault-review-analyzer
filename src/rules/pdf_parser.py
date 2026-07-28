"""PDF rule parser — extract rule definitions from PDF documents.

Parses PDF files containing standard rules/specifications and converts
them into Rule objects for the RulesEngine.

Issue: #7 — PDF 规范解析
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path  # noqa: TC003 — used in public API docstring example

from src.core.exceptions import DataProcessingError
from src.rules.models import Rule


class PDFRuleParser:
    """Parser for extracting rules from PDF specification documents.

    Supports Chinese-formatted rule definitions:
        规则名称: <name>
        描述: <description>
        严重级别: <severity>
        分类: <category>

    Usage:
        parser = PDFRuleParser()
        rules = parser.parse(Path("specs.pdf"))
    """

    # Field patterns for rule extraction
    FIELD_PATTERNS = {
        "name": r"规则名称[：:]\s*(.+)",
        "description": r"描述[：:]\s*(.+)",
        "severity": r"严重级别[：:]\s*(.+)",
        "category": r"分类[：:]\s*(.+)",
        "pattern": r"模式[：:]\s*(.+)",
        "message": r"提示信息[：:]\s*(.+)",
    }

    VALID_SEVERITIES = {"critical", "high", "medium", "low", "info"}

    def parse(self, pdf_path: Path) -> list[Rule]:
        """Parse a PDF file and extract rule definitions.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            List of Rule objects extracted from the PDF.

        Raises:
            DataProcessingError: If file not found or PDF library unavailable.
        """
        if not pdf_path.exists():
            raise DataProcessingError(
                f"PDF file does not exist: {pdf_path}",
                error_code="PDF_001",
                context={"path": str(pdf_path)},
            )

        try:
            text = self._extract_text(pdf_path)
        except ImportError as e:
            raise DataProcessingError(
                f"PDF library not available. Install PyMuPDF: pip install pymupdf. "
                f"Error: {e}",
                error_code="PDF_002",
                context={"path": str(pdf_path)},
            ) from e
        except Exception as e:
            raise DataProcessingError(
                f"Failed to extract text from PDF: {e}",
                error_code="PDF_003",
                context={"path": str(pdf_path), "error": str(e)},
            ) from e

        if not text or not text.strip():
            return []

        return self._parse_rules_from_text(text)

    def _extract_text(self, pdf_path: Path) -> str:
        """Extract text content from a PDF file.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            Extracted text content.

        Raises:
            ImportError: If PyMuPDF is not installed.
        """
        import fitz  # type: ignore[import-untyped]  # PyMuPDF

        doc = fitz.open(str(pdf_path))
        try:
            text_parts: list[str] = []
            for page in doc:
                text_parts.append(page.get_text())
            return "\n".join(text_parts)
        finally:
            doc.close()

    def _parse_rules_from_text(self, text: str) -> list[Rule]:
        """Parse rule definitions from extracted text.

        Splits text into rule blocks and extracts fields from each block.

        Args:
            text: Raw text content from PDF.

        Returns:
            List of parsed Rule objects.
        """
        rules: list[Rule] = []
        current_fields: dict[str, str] = {}

        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue

            # Check if this line starts a new rule (has 规则名称)
            name_match = re.match(self.FIELD_PATTERNS["name"], line)
            if name_match and current_fields.get("name"):
                # Save previous rule before starting new one
                rule = self._build_rule(current_fields)
                if rule:
                    rules.append(rule)
                current_fields = {}

            # Extract fields from this line
            for field_name, pattern in self.FIELD_PATTERNS.items():
                match = re.match(pattern, line)
                if match:
                    current_fields[field_name] = match.group(1).strip()

        # Don't forget the last rule
        if current_fields.get("name"):
            rule = self._build_rule(current_fields)
            if rule:
                rules.append(rule)

        return rules

    def _build_rule(self, fields: dict[str, str]) -> Rule | None:
        """Build a Rule object from extracted fields.

        Args:
            fields: Dict of extracted field values.

        Returns:
            Rule object, or None if required fields missing.
        """
        name = fields.get("name", "").strip()
        if not name:
            return None

        description = fields.get("description", "").strip()
        severity = fields.get("severity", "medium").strip().lower()
        if severity not in self.VALID_SEVERITIES:
            severity = "medium"

        category = fields.get("category", "").strip()
        pattern = fields.get("pattern", "").strip()
        message = fields.get("message", "").strip()

        return Rule(
            id=f"pdf-{uuid.uuid4().hex[:8]}",
            name=name,
            description=description,
            severity=severity,
            category=category,
            pattern=pattern,
            message=message,
        )
