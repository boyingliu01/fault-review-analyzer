"""增强LLM分析器 - 整合违规检测、代码变更分析和根因验证"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loguru import logger

from src.analysis.code_change_analyzer import CodeChangeAnalyzer
from src.analysis.root_cause_validator import RootCauseValidator
from src.analysis.violation_detector import ViolationDetector
from src.core.models import (
    CodeChange,
    LLMAnalysisResult,
    RootCauseValidation,
    ViolationDetection,
)

if TYPE_CHECKING:
    from src.knowledge.manager import StandardsManager


class EnhancedLLMAnalyzer:
    """增强LLM分析器 - 整合违规检测、代码变更分析和根因验证"""

    def __init__(self, standards_manager: StandardsManager) -> None:
        self._standards_manager = standards_manager
        self._violation_detector = ViolationDetector(standards_manager)
        self._root_cause_validator = RootCauseValidator()
        self._code_change_analyzer = CodeChangeAnalyzer()

    def analyze(
        self,
        fault_info: dict[str, Any],
        llm_provider: Any | None = None,
    ) -> LLMAnalysisResult:
        """执行完整的增强分析流程

        步骤：
        1. 违规检测
        2. 获取代码变更
        3. 根因分析（结合代码变更）
        4. 根因可落地性验证
        5. 改进措施生成

        Args:
            fault_info: 故障信息字典
            llm_provider: LLM提供商（可选）

        Returns:
            LLMAnalysisResult: 完整的分析结果
        """
        task_id = fault_info.get("task_id", "")

        violation_detection = self._detect_violation(fault_info)

        code_changes = self._analyze_code_changes(fault_info)

        root_cause = self._extract_root_cause(fault_info)

        root_cause_validation = self._validate_root_cause(root_cause, llm_provider)

        analysis_text = self._generate_analysis_text(
            fault_info, violation_detection, root_cause, root_cause_validation
        )

        return LLMAnalysisResult(
            task_id=task_id,
            violation_detection=violation_detection,
            root_cause=root_cause,
            root_cause_validation=root_cause_validation,
            code_changes=code_changes,
            analysis_text=analysis_text,
        )

    def _detect_violation(self, fault_info: dict[str, Any]) -> ViolationDetection:
        """步骤1: 违规检测"""
        return self._violation_detector.detect(fault_info)

    def _analyze_code_changes(self, fault_info: dict[str, Any]) -> list[CodeChange]:
        """步骤2: 获取并分析代码变更"""
        development = fault_info.get("development", {})
        commits = development.get("commits", [])

        if not commits:
            return []

        return self._code_change_analyzer.parse_commits(commits)

    def _extract_root_cause(self, fault_info: dict[str, Any]) -> str:
        """步骤3: 提取根因"""
        root_cause: str = str(fault_info.get("root_cause", ""))

        if not root_cause:
            description = str(fault_info.get("description", ""))
            # 过滤 Markdown 图片链接（![...](...) 或 ![...][...]）
            if description and not description.strip().startswith("!["):
                root_cause = description
            else:
                root_cause = ""

        if not root_cause:
            title = str(fault_info.get("title", ""))
            root_cause = f"需要分析: {title}"

        return root_cause

    def _validate_root_cause(
        self,
        root_cause: str,
        llm_provider: Any | None = None,
    ) -> RootCauseValidation:
        """步骤4: 根因可落地性验证"""
        if llm_provider:
            try:
                return self._root_cause_validator.validate_with_llm(root_cause, llm_provider)
            except Exception as e:
                logger.warning(f"LLM验证失败，回退到规则验证: {e}")

        return self._root_cause_validator.validate(root_cause)

    def _generate_analysis_text(
        self,
        fault_info: dict[str, Any],
        violation_detection: ViolationDetection,
        root_cause: str,
        root_cause_validation: RootCauseValidation,
    ) -> str:
        """生成完整的分析文本"""
        lines = []

        lines.append(f"故障单ID: {fault_info.get('task_id', '')}")
        lines.append(f"标题: {fault_info.get('title', '')}")
        lines.append("")

        lines.append("## 一、违规检测结果")
        if violation_detection.is_violation:
            lines.append(f"⚠️ 检测到违规: {violation_detection.violation_type}")
            lines.append(f"违规类别: {violation_detection.violation_category}")
            lines.append(f"置信度: {violation_detection.confidence:.2f}")
            if violation_detection.evidence:
                lines.append(f"证据: {violation_detection.evidence}")
        else:
            lines.append("✓ 未检测到明显违规")
        lines.append("")

        lines.append("## 二、根因分析")
        lines.append(root_cause)
        lines.append("")

        lines.append("## 三、根因验证结果")
        if root_cause_validation.is_actionable:
            lines.append(f"✓ 根因可落地 (评分: {root_cause_validation.actionability_score:.2f})")
        else:
            lines.append(f"⚠️ 根因不可落地 (评分: {root_cause_validation.actionability_score:.2f})")
            lines.append(f"原因: {root_cause_validation.validation_reason}")
            if root_cause_validation.needs_reanalysis:
                lines.append(f"建议: {root_cause_validation.reanalysis_feedback}")
        lines.append("")

        if root_cause_validation.improvement_measures:
            lines.append("## 四、改进措施")
            for i, measure in enumerate(root_cause_validation.improvement_measures, 1):
                lines.append(f"{i}. {measure.description}")
                lines.append(f"   - 验收标准: {measure.acceptance_criteria}")
                lines.append(f"   - 预期影响: {measure.expected_impact}")
                lines.append(f"   - 优先级: {measure.priority}")
            lines.append("")

        return "\n".join(lines)

    def analyze_batch(
        self,
        fault_infos: list[dict[str, Any]],
        llm_provider: Any | None = None,
    ) -> list[LLMAnalysisResult]:
        """批量分析多个故障

        Args:
            fault_infos: 故障信息列表
            llm_provider: LLM提供商

        Returns:
            list[LLMAnalysisResult]: 分析结果列表
        """
        results = []
        for fault_info in fault_infos:
            try:
                result = self.analyze(fault_info, llm_provider)
                results.append(result)
            except Exception as e:
                logger.error(f"分析故障 {fault_info.get('task_id')} 失败: {e}")
                results.append(
                    LLMAnalysisResult(
                        task_id=fault_info.get("task_id", ""),
                        violation_detection=ViolationDetection(is_violation=False),
                        root_cause_validation=RootCauseValidation(
                            root_cause="",
                            is_actionable=False,
                            actionability_score=0.0,
                        ),
                        analysis_text=f"分析失败: {str(e)}",
                    )
                )
        return results
