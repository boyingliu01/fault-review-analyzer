import json
from typing import Any

from loguru import logger

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
- 代码变更（commit diff）是第一优先级证据，故障描述仅为参考背景。注意 diff 有两种语义：故障单自身的 diff 记录修复动作（证明系统修复后的行为），引入单的 diff 记录缺陷引入（证明缺陷代码），两者不得混淆
- 变更意图识别：分析前必须先判断 diff 是"引入缺陷的变更"还是"修复缺陷的变更"。判断线索：commit message、故障描述与变更内容的对应关系。故障单自身的代码变更通常是修复动作——变更正是在改掉错误逻辑以消除故障，此时被修改前的旧代码（diff 的 old/- 侧）才是缺陷引入的候选证据，不得将修复动作本身定性为缺陷；只有存在直接证据表明修复不完整或引入了新问题时，才可对修复动作定性
- 修复 diff 的解读规则：diff 中新增或保留的代码代表修复后的正确形态，不是缺陷本体；缺陷定性必须指向修复前的旧行为或当时缺失的处理。若 diff 为纯新增、看不到旧行为，唯一合法的反推是"新增了某处理，说明修复前缺少该处理"，同时如实说明修复前的具体实现证据不足；不得将新增实现的设计选择（调用方式、未做某项处理、结构取舍）作为缺陷结论，除非有直接证据表明修复后故障仍复现
- 故障归因方向：故障现象（报错、数据异常等）的成因应追溯到修复前的旧行为或当时缺失的处理，而非修复后代码的形态
- 禁止臆测未读代码：不得对 diff 中未出现的代码（父类实现、被调用类的内部逻辑、框架行为）猜测其用途与内容；"可能存在/可能包含/可能未做"式推测不得写入根因描述或证据，无法验证时如实输出"证据不足，待确认"
- 不要根据故障描述做代码层面不存在的推测
- 概念溯源：根因与证据中出现的每个技术概念，必须能在 diff、描述或详情原文中找到对应内容，不得引入原文中不存在的概念

根因类型：
{cause_types}

请从以下维度分析：
1. 技术因素：代码、架构、配置等技术层面的问题（基于代码变更分析）
2. 过程因素：需求、设计、开发、测试等流程中的问题
3. 管理因素：沟通、变更、资源等管理层面的问题

请以JSON格式输出分析结果，包含以下字段：
- root_causes: 根因列表，每个包含cause_type(类型)、description(描述)、evidence(证据列表)。不要输出置信度：结论的可信度由证据本身说明
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

**注意**：
1. 详情中的代码变更(diff)属于故障处理过程中的修复性变更：它展示的是修复后的代码形态，用于确认系统当前行为，不得当作缺陷代码来审查；故障现象的成因在修复前的旧行为中，diff 未包含旧行为时应反推"修复前缺少什么"并如实标注"修复前实现证据不足"。
2. 可由修复动作反推修复前的缺失（如"新增了校验逻辑，说明修复前缺少该校验"），但不得把修复动作本身或修复后代码的设计形态定性为缺陷。
3. 【引入缺陷任务单的代码变更】区块（若存在）来自引入该缺陷的任务单，其中的变更是缺陷引入的直接候选证据，优先级高于故障单自身的修复性变更。

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
        "image_evidence": "故障单截图证据",
        "introduce_task_diff": "引入缺陷任务单的代码变更",
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
        for _attempt in range(2):
            response = await provider.generate(
                system=system_prompt,
                user=user_prompt,
            )
            parsed = self._parse_response(task_id, response)
            if parsed.root_causes:
                return parsed
            # 解析失败或根因为空，重试（本地模型偶发输出不完整）
            logger.warning(
                "task_id={} LLM 响应为空/不完整，重试（第 {} 次）",
                task_id,
                _attempt + 1,
            )
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
            # 可观测性：解析失败必须留下日志，否则 LLM 响应质量问题无法感知
            logger.warning(
                "task_id={} 根因分析响应解析失败: {} 原始响应片段: {}",
                task_id,
                e,
                response[:500],
            )
            return RootCauseAnalysisResult(
                task_id=task_id,
                root_causes=[],
                analysis_summary="",
                technical_factors=[],
                process_factors=[],
                management_factors=[],
            )
