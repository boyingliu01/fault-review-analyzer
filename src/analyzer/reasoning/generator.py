import json
from typing import Any

from src.analyzer.labeling.models import LLMProvider
from src.rules.categories import CAUSE_TYPES

from .models import (
    RootCause,
    RootCauseAnalysisResult,
)

_MAX_SEGMENT_CHARS = 800


SYSTEM_PROMPT = """你是一个专业的故障根因分析专家，擅长分析软件故障的根本原因。

你需要分析故障处理的完整流程，从需求、设计、开发、测试、部署等各个阶段找出导致故障的根本原因。

根因类型：
{cause_types}

请从以下维度分析：
1. 技术因素：代码、架构、配置等技术层面的问题
2. 过程因素：需求、设计、开发、测试等流程中的问题
3. 管理因素：沟通、变更、资源等管理层面的问题

请以JSON格式输出分析结果，包含以下字段：
- root_causes: 根因列表，每个包含cause_type(类型)、description(描述)、evidence(证据列表)、confidence(置信度0-1)
- analysis_summary: 分析总结
- technical_factors: 技术因素列表
- process_factors: 过程因素列表
- management_factors: 管理因素列表
"""


USER_PROMPT_TEMPLATE = """故障单信息：
- 标题：{title}
- 描述：{description}
- 状态：{status}
- 优先级：{priority}

故障处理详情：
{segment_details}

请进行根因分析，找出导致该故障的根本原因。"""


def build_segment_details(segments: list[dict]) -> str:
    """Build detailed text from processed task segments."""
    details = []
    segment_labels = {
        "requirement": "需求阶段",
        "design": "设计阶段",
        "development": "开发阶段",
        "testing": "测试阶段",
        "production": "生产环境",
    }
    for seg in segments:
        seg_type = seg.get("type", "")
        content = seg.get("content", "")
        label = segment_labels.get(seg_type, seg_type)
        if content:
            details.append(f"【{label}】{content[:_MAX_SEGMENT_CHARS]}")
    return "\n".join(details) if details else "无详细信息"


class RootCauseAnalyzer:
    """Analyze root causes for fault tasks using LLM."""

    def __init__(self, llm_provider: LLMProvider | None = None):
        self._provider = llm_provider
        self._cause_types = CAUSE_TYPES

    @property
    def is_available(self) -> bool:
        return self._provider is not None

    def _get_provider(self) -> Any:
        if self._provider is None:
            raise RuntimeError("LLM provider not configured")
        return self._provider

    async def analyze(
        self,
        task_data: dict[str, Any],
        segments: list[dict] | None = None,
        labels: list[dict] | None = None,
    ) -> RootCauseAnalysisResult:
        """Analyze root cause for a single task."""
        title = task_data.get("title", "")
        description = task_data.get("description", "")
        status = task_data.get("status", "")
        priority = task_data.get("priority", "")
        task_id = task_data.get("task_id", 0)

        segment_details = ""
        if segments:
            segment_details = build_segment_details(segments)

        label_context = ""
        if labels:
            label_names = [label.get("name", "") for label in labels if isinstance(label, dict)]
            if label_names:
                label_context = f"\n已有标签: {', '.join(label_names)}"

        user_prompt = (
            USER_PROMPT_TEMPLATE.format(
                title=title,
                description=description,
                status=status,
                priority=priority,
                segment_details=segment_details,
            )
            + label_context
        )

        system_prompt = SYSTEM_PROMPT.format(
            cause_types="\n".join(f"- {c}" for c in self._cause_types)
        )

        provider = self._get_provider()
        response = await provider.generate(
            system=system_prompt,
            user=user_prompt,
        )

        return self._parse_response(task_id, response)

    async def analyze_batch(
        self,
        tasks: list[dict[str, Any]],
        segments_list: list[list[dict]] | None = None,
    ) -> list[RootCauseAnalysisResult]:
        """Analyze root causes for multiple tasks."""
        results = []
        for i, task in enumerate(tasks):
            segments = segments_list[i] if segments_list and i < len(segments_list) else None
            result = await self.analyze(task, segments)
            results.append(result)
        return results

    def _parse_response(
        self,
        task_id: int,
        response: str,
    ) -> RootCauseAnalysisResult:
        """Parse LLM response into structured result."""
        try:
            data = json.loads(response)
            root_causes = [
                RootCause(
                    cause_type=rc.get("cause_type", ""),
                    description=rc.get("description", ""),
                    evidence=rc.get("evidence", []),
                    confidence=float(rc.get("confidence", 0.5)),
                )
                for rc in data.get("root_causes", [])
            ]
            return RootCauseAnalysisResult(
                task_id=task_id,
                root_causes=root_causes,
                analysis_summary=data.get("analysis_summary", ""),
                technical_factors=data.get("technical_factors", []),
                process_factors=data.get("process_factors", []),
                management_factors=data.get("management_factors", []),
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            return RootCauseAnalysisResult(
                task_id=task_id,
                root_causes=[],
                analysis_summary="",
                technical_factors=[],
                process_factors=[],
                management_factors=[],
            )
