import json
from typing import Any

from src.rules.categories import FAULT_CATEGORIES

from ..labeling.models import Label, LabelGenerationResult, LLMProvider

_MAX_SEGMENT_CHARS = 2000
_MAX_DESCRIPTION_CHARS = 200
_MAX_PARSE_DISPLAY_CHARS = 200


SYSTEM_PROMPT = """你是一个专业的故障分析专家，擅长对软件故障进行分类和根因分析。

你需要根据故障单的详细信息，为其生成合适的分类标签。

**核心分析原则**：
- 代码变更（commit diff）是第一优先级证据，故障描述仅为参考背景
- 如果代码变更与描述内容矛盾，以代码变更为准
- 区分"新增逻辑""删除逻辑""移动/重组逻辑"是不同的变更类型
- 不要根据故障描述做代码层面不存在的推测

故障分类标签：
{categories}

请从以下维度分析：
1. 故障类型：根据代码变更的性质分类（而非描述中的业务叙述）
2. 影响范围：故障影响的系统模块
3. 严重程度：故障对业务的影响程度
4. 根因类型：导致故障的根本原因类型

请以JSON格式输出分析结果，包含以下字段：
- labels: 标签列表，每个标签包含name(名称)、confidence(置信度0-1)、category(类别)、description(描述)
- summary: 故障概要描述
- reasoning: 分析推理过程
"""


USER_PROMPT_TEMPLATE = """故障单信息：
- 标题：{title}
- 描述：{description}
- 状态：{status}
- 优先级：{priority}

{segment_details}

**注意**：如果上面的“commit”部分包含代码变更(diff)，请以代码变更作为分析的第一依据，故障描述仅作为背景参考。

请分析并生成标签。"""


def build_segment_details(segments: list[dict]) -> str:
    """Build detailed text from processed task segments."""
    details = []
    for seg in segments:
        seg_type = seg.get("type", "")
        content = seg.get("content", "")
        if content:
            details.append(f"【{seg_type}】{content[:_MAX_SEGMENT_CHARS]}")
    return "\n".join(details) if details else "无详细信息"


class LabelGenerator:
    """Generate labels for fault tasks using LLM."""

    def __init__(self, llm_provider: LLMProvider | None = None):
        self._provider = llm_provider
        self._categories = FAULT_CATEGORIES

    @property
    def is_available(self) -> bool:
        return self._provider is not None

    def _get_provider(self) -> Any:
        if self._provider is None:
            raise RuntimeError("LLM provider not configured")
        return self._provider

    async def generate(
        self,
        task_data: dict[str, Any],
        segments: list[dict] | None = None,
    ) -> LabelGenerationResult:
        """Generate labels for a single task."""
        title = task_data.get("title", "")
        description = task_data.get("description", "")
        status = task_data.get("status", "")
        priority = task_data.get("priority", "")

        segment_details = ""
        if segments:
            segment_details = build_segment_details(segments)

        user_prompt = USER_PROMPT_TEMPLATE.format(
            title=title,
            description=description,
            status=status,
            priority=priority,
            segment_details=segment_details,
        )

        system_prompt = SYSTEM_PROMPT.format(
            categories="\n".join(f"- {c}" for c in self._categories)
        )

        provider = self._get_provider()
        response = await provider.generate(
            system=system_prompt,
            user=user_prompt,
        )

        return self._parse_response(task_data.get("task_id", 0), response)

    async def generate_for_cluster(
        self,
        cluster_tasks: list[dict[str, Any]],
    ) -> LabelGenerationResult:
        """Generate labels for a cluster of tasks."""
        if not cluster_tasks:
            raise ValueError("No tasks provided for cluster labeling")

        task_summaries = []
        for i, task in enumerate(cluster_tasks):
            title = task.get("title", "")
            desc = task.get("description", "")[:_MAX_DESCRIPTION_CHARS]
            task_summaries.append(f"任务{i + 1}: {title} - {desc}")

        combined_text = "\n".join(task_summaries)

        user_prompt = f"""故障聚类信息（共{len(cluster_tasks)}个任务）：

{combined_text}

请分析这个故障聚类的共同特征，生成统一的分类标签。"""

        system_prompt = SYSTEM_PROMPT.format(
            categories="\n".join(f"- {c}" for c in self._categories)
        )

        provider = self._get_provider()
        response = await provider.generate(
            system=system_prompt,
            user=user_prompt,
        )

        cluster_id = cluster_tasks[0].get("cluster_id", 0) if cluster_tasks else 0
        return self._parse_response(cluster_id, response)

    def _parse_response(self, task_id: int, response: str) -> LabelGenerationResult:
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
            labels = [
                Label(
                    name=label_data.get("name", ""),
                    confidence=float(label_data.get("confidence", 0.5)),
                    category=label_data.get("category", ""),
                    description=label_data.get("description", ""),
                )
                for label_data in data.get("labels", [])
            ]
            return LabelGenerationResult(
                cluster_id=task_id,
                labels=labels,
                summary=data.get("summary", ""),
                reasoning=data.get("reasoning", ""),
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            import sys

            print(f"[DEBUG] LLM 响应解析失败: {e}", file=sys.stderr)
            print(f"[DEBUG] 原始响应: {response[:500]}", file=sys.stderr)
            return LabelGenerationResult(
                cluster_id=task_id,
                labels=[],
                summary="",
                reasoning=f"Failed to parse LLM response: {response[:_MAX_PARSE_DISPLAY_CHARS]}",
            )
