"""Snapshot regression tests using syrupy — REQ-6, Issue #14.

Establishes baseline snapshots for:
- Report generation output
- Label generation output

These snapshots detect unintended changes in output format/content.
"""

from __future__ import annotations

import re
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.report.generator import ReportGenerator


def _normalize_timestamps(text: str) -> str:
    """Replace dynamic timestamps with a fixed placeholder for snapshot stability."""
    return re.sub(
        r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}",
        "TIMESTAMP",
        text,
    )


class TestReportSnapshot:
    """Snapshot tests for report generation output."""

    def test_single_report_snapshot(self, snapshot):
        """Report generation output matches baseline snapshot."""
        generator = ReportGenerator()

        task_data = {
            "task_id": 12345,
            "title": "空指针异常导致服务崩溃",
            "description": "生产环境出现空指针异常，导致服务不可用",
            "status": "closed",
            "priority": "high",
        }
        preprocessed = {
            "segments": [
                {"type": "开发", "content": "修复空指针检查", "metadata": {}},
                {"type": "测试", "content": "补充边界测试用例", "metadata": {}},
            ]
        }
        labels = [
            {
                "name": "空异常捕获",
                "confidence": 0.95,
                "category": "代码质量",
                "description": "未正确处理空值",
            },
            {
                "name": "缺少边界检查",
                "confidence": 0.8,
                "category": "测试覆盖",
                "description": "边界条件未覆盖",
            },
        ]
        root_causes = [
            {
                "cause_type": "代码缺陷",
                "description": "未对返回结果进行空值检查",
                "evidence": "第42行直接调用方法未判空",
                "confidence": 0.9,
            }
        ]
        suggestions = ["加强空值检查编码规范", "补充边界条件测试用例"]

        report = _normalize_timestamps(
            generator.generate_single(
                task_data=task_data,
                segments=preprocessed["segments"],
                labels=labels,
                root_causes=root_causes,
                suggestions=suggestions,
            )
        )

        assert report == snapshot

    def test_empty_report_snapshot(self, snapshot):
        """Report with minimal data matches baseline snapshot."""
        generator = ReportGenerator()

        task_data = {"task_id": 99999, "title": "", "description": ""}
        preprocessed = {"segments": []}

        report = _normalize_timestamps(
            generator.generate_single(
                task_data=task_data,
                segments=preprocessed["segments"],
                labels=[],
                root_causes=[],
                suggestions=[],
            )
        )

        assert report == snapshot


class TestLabelingSnapshot:
    """Snapshot tests for label generation output structure."""

    @pytest.mark.asyncio
    async def test_label_output_structure_snapshot(self, snapshot):
        """Label generator output structure matches baseline."""
        from src.analyzer.labeling.generator import LabelGenerator

        # Create a mock LLM provider that returns predictable output
        mock_provider = MagicMock()
        mock_provider.generate = AsyncMock(
            return_value='{"labels": [{"name": "空指针", "confidence": 0.9, "category": "代码质量", "description": "空值未检查"}]}'
        )

        generator = LabelGenerator(llm_provider=mock_provider)

        task_data = {
            "task_id": 12345,
            "title": "测试任务",
            "description": "测试描述",
        }
        segments = [{"type": "开发", "content": "开发内容"}]

        result = await generator.generate(task_data, segments)

        # Snapshot the result structure
        result_dict = {
            "labels": [
                {
                    "name": label.name,
                    "confidence": label.confidence,
                    "category": label.category,
                    "description": label.description,
                }
                for label in result.labels
            ]
        }

        assert result_dict == snapshot
