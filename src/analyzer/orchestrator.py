"""PipelineOrchestrator — orchestrates the analysis pipeline using handlers.

Composes FetchHandler, AnalyzeHandler, and ReportHandler to execute
the full analysis flow while keeping each concern separated.

Issue: #13 — Pipeline 拆分重构
"""

from __future__ import annotations

from typing import Any

from src.analyzer.handlers.analyze import AnalyzeHandler
from src.analyzer.handlers.fetch import FetchHandler
from src.analyzer.handlers.report import ReportHandler
from src.analyzer.pipeline import PipelineConfig, PipelineResult
from src.preprocessor.processor import DataPreprocessor


class PipelineOrchestrator:
    """Orchestrates the analysis pipeline using composable handlers.

    This class is responsible for flow control, delegating actual work
    to the three specialized handlers:
    - FetchHandler: data retrieval
    - AnalyzeHandler: LLM-based analysis
    - ReportHandler: rules checking and report generation
    """

    def __init__(
        self,
        fetch_handler: FetchHandler,
        analyze_handler: AnalyzeHandler,
        report_handler: ReportHandler,
        preprocessor: DataPreprocessor | None = None,
    ) -> None:
        self._fetch_handler = fetch_handler
        self._analyze_handler = analyze_handler
        self._report_handler = report_handler
        self._preprocessor = preprocessor or DataPreprocessor()

    async def run_single(self, task_id: int, config: PipelineConfig) -> PipelineResult:
        """Run the full analysis pipeline for a single task.

        Args:
            task_id: The task ID to analyze.
            config: Pipeline configuration flags.

        Returns:
            PipelineResult with all analysis outputs.
        """
        result = PipelineResult(task_id=task_id)

        try:
            # Step 1: Fetch
            task_data = await self._fetch_handler.fetch_task(task_id)
            if task_data is None:
                result.error = f"Task {task_id} not found"
                return result

            # Step 2: Preprocess
            result.task_data = task_data.model_dump()
            preprocessed = self._preprocessor.process(task_data)
            result.preprocessed = {
                "task_id": preprocessed.task_id,
                "combined_text": preprocessed.combined_text,
                "segments": [
                    {"type": s.type, "content": s.content, "metadata": s.metadata}
                    for s in preprocessed.segments
                ],
            }

            # Step 3: Analyze (LLM-based)
            if config.use_llm:
                task_dict = task_data.model_dump()
                if config.generate_labels:
                    result.labels = await self._analyze_handler.generate_labels(
                        task_dict, preprocessed
                    )
                if config.analyze_root_cause:
                    result.root_causes = await self._analyze_handler.analyze_root_cause(
                        task_dict, preprocessed
                    )

                if config.analyze_root_cause_deep:
                    result.deep_root_causes = await self._analyze_handler.analyze_root_cause_deep(
                        task_dict
                    )

            # Step 4: Report
            if config.check_rules:
                result.violations = self._report_handler.check_rules(task_data.model_dump())

            if config.generate_report:
                result.report = self._report_handler.generate_report(
                    task_data.model_dump(),
                    result.preprocessed,
                    result.labels,
                    result.root_causes,
                )

        except Exception as e:
            result.error = str(e)

        return result
