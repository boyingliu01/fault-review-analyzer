"""AnalyzeHandler — responsible for LLM-based analysis.

Handles label generation, root cause analysis, and deep root cause analysis.

Issue: #13 — Pipeline 拆分重构
"""

from __future__ import annotations

from typing import Any

from src.analyzer.labeling import LabelGenerator
from src.analyzer.llm_provider import create_llm_provider
from src.analyzer.reasoning import RootCauseAnalyzer
from src.preprocessor.models import ProcessedTask


class AnalyzeHandler:
    """Handles LLM-based analysis tasks.

    Encapsulates label generation and root cause analysis logic
    previously embedded in AnalysisPipeline.
    """

    def __init__(
        self,
        llm_provider: Any | None = None,
        label_generator: LabelGenerator | None = None,
        root_cause_analyzer: RootCauseAnalyzer | None = None,
    ) -> None:
        self._llm_provider = llm_provider
        self._label_generator = label_generator
        self._root_cause_analyzer = root_cause_analyzer

    async def generate_labels(
        self,
        task_data: dict[str, Any],
        preprocessed: ProcessedTask,
    ) -> list[dict]:
        """Generate labels for a task using LLM.

        Args:
            task_data: Task data as dict.
            preprocessed: Preprocessed task data.

        Returns:
            List of label dicts with name, confidence, category, description.
        """
        if self._label_generator is None:
            self._label_generator = LabelGenerator(llm_provider=self._llm_provider)

        if not self._label_generator.is_available:
            return []

        result = await self._label_generator.generate(
            task_data,
            [{"type": s.type, "content": s.content} for s in preprocessed.segments],
        )

        return [
            {
                "name": label.name,
                "confidence": label.confidence,
                "category": label.category,
                "description": label.description,
            }
            for label in result.labels
        ]

    async def analyze_root_cause(
        self,
        task_data: dict[str, Any],
        preprocessed: ProcessedTask,
    ) -> list[dict]:
        """Analyze root cause for a task using LLM.

        Args:
            task_data: Task data as dict.
            preprocessed: Preprocessed task data.

        Returns:
            List of root cause dicts with cause_type, description, evidence, confidence.
        """
        if self._root_cause_analyzer is None:
            self._root_cause_analyzer = RootCauseAnalyzer(llm_provider=self._llm_provider)

        if not self._root_cause_analyzer.is_available:
            return []

        result = await self._root_cause_analyzer.analyze(
            task_data,
            [{"type": s.type, "content": s.content} for s in preprocessed.segments],
        )

        return [
            {
                "cause_type": rc.cause_type,
                "description": rc.description,
                "evidence": rc.evidence,
                "confidence": rc.confidence,
            }
            for rc in result.root_causes
        ]

    def set_llm_provider(self, provider: Any) -> None:
        """Set or replace the LLM provider."""
        self._llm_provider = provider
        # Reset generators so they pick up the new provider
        self._label_generator = None
        self._root_cause_analyzer = None

    async def analyze_root_cause_deep(
        self,
        task_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Perform enhanced 5-layer deep root cause analysis.

        Args:
            task_data: Task data as dict.

        Returns:
            Deep root cause analysis result dict, or empty dict if unavailable.
        """
        # Deep root cause analysis requires additional API calls and
        # the DeepRootCauseAnalyzer. This is a placeholder that returns
        # empty until the full integration is wired up.
        return {}
