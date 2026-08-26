import json
from typing import Any

from src.analyzer.labeling.models import LLMProvider
from src.rules.categories import CAUSE_TYPES

from .models import (
    RootCause,
    RootCauseAnalysisResult,
)

_MAX_SEGMENT_CHARS = 2000


SYSTEM_PROMPT = """你是一个专业的故障根因分析专家，擅长分析软件故障的根本原因。

你需要分析故障处理的完整流程，从需求、设计、开发、测试、部署等各个阶段找出导致故障的根本原因。

**核心分析原则**：
- 代码变更（commit diff）是第一优先级证据，故障描述仅为参考背景
- 如果代码变更与描述内容矛盾，以代码变更为准
- 根因分析应聚焦于代码变更暴露的缺陷，而非描述中的业务叙述
- 不要根据故障描述做代码层面不存在的推测

根因类型：
{cause_types}

请从以下维度分析：
1. 技术因素：代码、架构、配置等技术层面的问题（基于代码变更分析）
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

**注意**：如果上面的详情中包含“commit”代码变更(diff)，请以代码变更作为根因分析的第一依据，故障描述仅作为背景参考。

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

        # 本地 LLM 偶发返回空/不完整 JSON，解析失败时重试，保证根因分析完整性
        result: RootCauseAnalysisResult | None = None
        for attempt in range(2):
            response = await provider.generate(
                system=system_prompt,
                user=user_prompt,
            )
            parsed = self._parse_response(task_id, response)
            if parsed.root_causes:
                return parsed
            # 解析失败或根因为空，重试（本地模型偶发输出不完整）
            result = parsed

        assert result is not None
        return result

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
            # 提取 JSON 内容（支持 markdown code block）
            json_content = response.strip()
            if json_content.startswith("```"):
                # 移除 markdown 代码块标记
                lines = json_content.split("\n")
                # 找到第一个 { 和最后一个 }
                start = -1
                end = -1
                for i, line in enumerate(lines):
                    if "{" in line and start == -1:
                        start = i
                    if "}" in line:
                        end = i
                if start >= 0 and end > start:
                    json_content = "\n".join(lines[start : end + 1])

            data = json.loads(json_content)
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
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            import sys

            print(f"[DEBUG] 根因分析响应解析失败: {e}", file=sys.stderr)
            print(f"[DEBUG] 原始响应: {response[:500]}", file=sys.stderr)
            return RootCauseAnalysisResult(
                task_id=task_id,
                root_causes=[],
                analysis_summary="",
                technical_factors=[],
                process_factors=[],
                management_factors=[],
            )
