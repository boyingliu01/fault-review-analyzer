"""ReportHandler — responsible for rules checking and report generation.

Issue: #13 — Pipeline 拆分重构
"""

from __future__ import annotations

from typing import Any

from src.report.generator import ReportGenerator
from src.rules.engine import RulesEngine


class ReportHandler:
    """Handles rules checking and report generation.

    Encapsulates the rules engine and report generator logic
    previously embedded in AnalysisPipeline.
    """

    def __init__(
        self,
        rules_engine: RulesEngine | None = None,
        report_generator: ReportGenerator | None = None,
    ) -> None:
        self._rules_engine = rules_engine or RulesEngine()
        self._report_generator = report_generator

    def check_rules(self, task_data: dict[str, Any]) -> list[dict]:
        """Check rules for a task.

        Args:
            task_data: Task data as dict.

        Returns:
            List of violation dicts with rule_id, rule_name, severity, message, evidence.
        """
        violations = self._rules_engine.check(task_data)

        return [
            {
                "rule_id": v.rule_id,
                "rule_name": v.rule_name,
                "severity": v.severity,
                "message": v.message,
                "evidence": v.evidence,
            }
            for v in violations
        ]

    def generate_report(
        self,
        task_data: dict[str, Any],
        preprocessed: dict[str, Any],
        labels: list[dict] | None = None,
        root_causes: list[dict] | None = None,
    ) -> str:
        """Generate a report for a task.

        Args:
            task_data: Task data as dict.
            preprocessed: Preprocessed task data dict.
            labels: Generated labels (optional).
            root_causes: Identified root causes (optional).

        Returns:
            Generated report as string.
        """
        if self._report_generator is None:
            self._report_generator = ReportGenerator()

        suggestions = []
        if root_causes:
            suggestions = [
                f"针对{rc.get('cause_type', '未知')}类型问题，建议加强相关环节的质量把控"
                for rc in root_causes[:3]
            ]

        return self._report_generator.generate_single(
            task_data=task_data,
            segments=preprocessed.get("segments", []),
            labels=labels or [],
            root_causes=root_causes or [],
            suggestions=suggestions,
        )
