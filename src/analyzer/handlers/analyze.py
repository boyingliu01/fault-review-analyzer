"""AnalyzeHandler — responsible for LLM-based analysis.

Handles label generation, root cause analysis, and deep root cause analysis.

Issue: #13 — Pipeline 拆分重构
"""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from loguru import logger

from src.analysis.root_cause import ExistingFaultAnalysis, FaultAnalysisInput
from src.analysis.root_cause import RootCauseAnalyzer as DeepRootCauseAnalyzer
from src.analyzer.labeling import LabelGenerator
from src.analyzer.reasoning import RootCauseAnalyzer

if TYPE_CHECKING:
    from src.preprocessor.models import ProcessedTask


class _LLMClientAdapter:
    """Adapter that converts generate(system, user) to generate(prompt)."""

    def __init__(self, provider: Any) -> None:
        self._provider = provider

    async def generate(self, prompt: str) -> str:
        """Generate using the provider with combined system and user prompt."""
        return str(
            await self._provider.generate(system="You are a helpful assistant.", user=prompt)
        )


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
        api_client: Any | None = None,
    ) -> None:
        self._llm_provider = llm_provider
        self._label_generator = label_generator
        self._root_cause_analyzer = root_cause_analyzer
        self._deep_root_cause_analyzer: DeepRootCauseAnalyzer | None = None
        self._api_client = api_client

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
        self._deep_root_cause_analyzer = None

    async def analyze_root_cause_deep(
        self,
        task_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Perform enhanced 5-layer deep root cause analysis.

        Fetches existing fault analysis from the API (复盘结论), builds a
        FaultAnalysisInput, and runs the DeepRootCauseAnalyzer.

        Args:
            task_data: Task data as dict.

        Returns:
            Deep root cause analysis result dict, or empty dict if unavailable.
        """
        analyzer = self._get_deep_root_cause_analyzer()
        if analyzer is None:
            return {}

        # TaskInfo.model_dump() 后的字段名是 task_id（不是 task_no/taskId）
        task_no = str(
            task_data.get("task_no")
            or task_data.get("taskId")
            or task_data.get("task_id")
            or ""
        )
        if not task_no:
            return {}

        # 获取现有故障复盘结论（API 不可用时降级为空）
        existing_analysis = ExistingFaultAnalysis()
        if self._api_client is not None:
            try:
                existing_api_data = await self._api_client.get_fault_analysis(task_no)
                existing_analysis = self._convert_api_to_existing_analysis(existing_api_data)
            except Exception as e:
                logger.warning(f"获取故障复盘结论失败，使用空结论: {e}")

        # 图片证据注入：把故障单截图提取内容并入描述，
        # 使 5 层深挖基于完整信息（描述+截图）而非残缺文本。
        description = task_data.get("description", "")
        try:
            from src.analyzer.image_evidence import ImageEvidenceExtractor

            evidence = await ImageEvidenceExtractor().get_image_evidence(task_data)
            if evidence:
                description = f"{description}\n\n## 故障单截图证据\n{evidence}"
        except Exception as e:
            logger.warning(f"图片证据注入失败(忽略，降级为纯描述): {str(e)[:80]}")

        fault_input = FaultAnalysisInput(
            task_no=task_no,
            title=task_data.get("title", ""),
            description=description,
            task_src=task_data.get("task_src", ""),
            created_date=task_data.get("created_date", task_data.get("createdDate", "")),
            finish_date=task_data.get("finish_date", task_data.get("finishDate", "")),
            product_module_id=task_data.get("product_module_id")
            or task_data.get("productModuleId"),
            product_version_id=task_data.get("product_version_id")
            or task_data.get("productVersionId"),
        )

        try:
            result = await analyzer.analyze(fault_input, existing_analysis)
            return asdict(result)
        except Exception as e:
            logger.error(f"深度根因分析失败: {e}")
            return {}

    def _get_deep_root_cause_analyzer(self) -> DeepRootCauseAnalyzer | None:
        """Get or create DeepRootCauseAnalyzer."""
        if self._deep_root_cause_analyzer is not None:
            return self._deep_root_cause_analyzer

        if self._llm_provider is None:
            return None

        adapter = _LLMClientAdapter(self._llm_provider)
        self._deep_root_cause_analyzer = DeepRootCauseAnalyzer(adapter)
        return self._deep_root_cause_analyzer

    def _convert_api_to_existing_analysis(self, api_data: dict[str, Any]) -> ExistingFaultAnalysis:
        """Convert API response to ExistingFaultAnalysis model."""
        dev_data = api_data.get("apiDevTaskAnalysis", {})
        test_data = api_data.get("apiTestTaskAnalysis", {})

        return ExistingFaultAnalysis(
            dev_catalog=dev_data.get("catalog", ""),
            dev_catalog_detail=dev_data.get("catalogDetail", ""),
            dev_reason=dev_data.get("reason", ""),
            dev_conclusion=dev_data.get("conclusion", ""),
            dev_improve_stage=dev_data.get("improveStage", ""),
            test_catalog=test_data.get("catalog", ""),
            test_catalog_detail=test_data.get("catalogDetail", ""),
            test_reason=test_data.get("reason", ""),
            test_conclusion=test_data.get("conclusion", ""),
            test_improve_stage=test_data.get("improveStage", ""),
        )
