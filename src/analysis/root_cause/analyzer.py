"""根因分析服务"""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from typing import Any

from loguru import logger

from src.analysis.root_cause.models import (
    ActionableImprovement,
    ExistingFaultAnalysis,
    FaultAnalysisInput,
    RootCause,
    RootCauseAnalysisResult,
)
from src.analysis.root_cause.prompts import ROOT_CAUSE_ANALYSIS_PROMPT


def _camel_to_snake(name: str) -> str:
    """Convert camelCase to snake_case."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _convert_keys(data: Any) -> Any:
    """Recursively convert camelCase keys to snake_case."""
    if not isinstance(data, dict):
        return data
    result: dict[str, Any] = {}
    for key, value in data.items():
        snake_key = _camel_to_snake(key)
        if isinstance(value, dict):
            result[snake_key] = _convert_keys(value)
        elif isinstance(value, list):
            result[snake_key] = [
                _convert_keys(item) if isinstance(item, dict) else item for item in value
            ]
        else:
            result[snake_key] = value
    return result


class RootCauseAnalyzer:
    """根因分析器"""

    def __init__(self, llm_client: Any) -> None:
        """
        初始化根因分析器

        Args:
            llm_client: LLM客户端，需提供 generate(prompt) -> str 方法
        """
        self.llm_client = llm_client

    def _render_prior_root_causes(self, prior: list[dict[str, Any]]) -> str:
        """把普通根因链路结论渲染为 prompt 文本（深度分析的事实锚点）。"""
        if not prior:
            return (
                "（无。本单未经普通根因分析或无代码变更——"
                "此时更要严守证据边界，证据不足的层面如实降级）"
            )
        lines: list[str] = []
        for idx, rc in enumerate(prior, 1):
            evidence = rc.get("evidence") or []
            if isinstance(evidence, list):
                evidence_text = "；".join(str(e) for e in evidence)
            else:
                evidence_text = str(evidence)
            lines.append(
                f"{idx}. [{rc.get('cause_type', '')}] {rc.get('description', '')}"
                f"\n   证据: {evidence_text}"
            )
        return "\n".join(lines)

    def _render_introduce_task_diff(self, diff: str) -> str:
        """渲染引入单代码变更区块内容（无引入单号时输出占位说明）。"""
        diff = (diff or "").strip()
        if not diff:
            return (
                "（无。故障单未填写引入单号，或引入单无代码变更——"
                "此时以故障单自身 diff 的旧代码与描述证据为准）"
            )
        return diff

    @staticmethod
    def _render_requirement_context(ctx: Any) -> str:
        """渲染需求-测试传导链证据区块（无证据时输出 gap 声明）。"""
        lines: list[str] = []
        if ctx.requirement_no:
            label = {"parent_task": "父需求/任务单", "introduce_task": "引入任务单"}.get(
                ctx.source, "关联单据"
            )
            lines.append(f"- {label}: {ctx.requirement_no} {ctx.requirement_title}")
            if ctx.requirement_desc:
                lines.append(f"- 需求描述原文:\n{ctx.requirement_desc}")
            else:
                lines.append("- 需求描述: （空——该单据未填写需求内容）")
        if ctx.test_case_ids:
            ids_text = ", ".join(str(i) for i in ctx.test_case_ids[:20])
            more = (
                f"（共 {len(ctx.test_case_ids)} 个，仅列前 20）"
                if len(ctx.test_case_ids) > 20
                else ""
            )
            lines.append(f"- 故障单关联测试用例 ID: {ids_text} {more}".rstrip())
        else:
            lines.append("- 故障单关联测试用例: （无关联记录）")
        if ctx.data_gaps:
            lines.append("- 证据缺失声明（分析时必须如实引用，不得脑补缺失部分）:")
            for gap in ctx.data_gaps:
                lines.append(f"  * {gap}")
        return "\n".join(lines)

    def _build_prompt(
        self, fault_input: FaultAnalysisInput, existing_analysis: ExistingFaultAnalysis
    ) -> str:
        """构建Prompt"""
        return ROOT_CAUSE_ANALYSIS_PROMPT.format(
            task_no=fault_input.task_no,
            title=fault_input.title,
            description=fault_input.description,
            task_src=fault_input.task_src,
            created_date=fault_input.created_date,
            finish_date=fault_input.finish_date,
            prior_root_causes=self._render_prior_root_causes(
                fault_input.prior_root_causes
            ),
            introduce_task_diff=self._render_introduce_task_diff(
                fault_input.introduce_task_diff
            ),
            requirement_context=self._render_requirement_context(
                fault_input.requirement_context
            ),
            dev_catalog=existing_analysis.dev_catalog,
            dev_catalog_detail=existing_analysis.dev_catalog_detail,
            dev_reason=existing_analysis.dev_reason,
            dev_conclusion=existing_analysis.dev_conclusion,
            dev_improve_stage=existing_analysis.dev_improve_stage,
            test_catalog=existing_analysis.test_catalog,
            test_catalog_detail=existing_analysis.test_catalog_detail,
            test_reason=existing_analysis.test_reason,
            test_conclusion=existing_analysis.test_conclusion,
            test_improve_stage=existing_analysis.test_improve_stage,
        )

    @staticmethod
    def _parse_json_loose(response: str) -> dict[str, Any] | None:
        """宽松解析 LLM 的 JSON 响应（容忍 markdown 围栏/前后杂文）。

        代理模型偶发把 JSON 包在 ```json 围栏里或附加说明文字，
        直接 json.loads 会失败导致整单深度分析丢失。
        """
        t = (response or "").strip()
        if not t:
            return None
        # 剥离 markdown 围栏
        if "```" in t:
            start = t.find("{")
            end = t.rfind("}")
            if start >= 0 and end > start:
                t = t[start : end + 1]
        try:
            data = json.loads(t)
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None

    async def analyze(
        self, fault_input: FaultAnalysisInput, existing_analysis: ExistingFaultAnalysis
    ) -> RootCauseAnalysisResult:
        """
        执行根因分析

        Args:
            fault_input: 故障分析输入
            existing_analysis: 现有故障复盘结论

        Returns:
            RootCauseAnalysisResult: 根因分析结果
        """
        prompt = self._build_prompt(fault_input, existing_analysis)
        logger.debug("开始调用LLM进行根因分析，task_no={}", fault_input.task_no)

        parsed: dict[str, Any] | None = None
        response = ""
        for attempt in range(2):
            response = await self.llm_client.generate(prompt)
            logger.debug("LLM响应长度: {}", len(response))
            parsed = self._parse_json_loose(response)
            if parsed is not None:
                break
            logger.warning(
                "根因分析响应无法解析为JSON(task_no={}，第{}次)，重试",
                fault_input.task_no,
                attempt + 1,
            )
        if parsed is None:
            raise ValueError(f"根因分析响应无法解析为JSON: {response[:200]}")

        result_data = _convert_keys(parsed)

        # 转换camelCase键为snake_case
        result_data = _convert_keys(result_data)

        # 转换为数据类
        deep_root_causes = [RootCause(**r) for r in result_data.get("deep_root_causes", [])]
        actionable_improvements = [
            ActionableImprovement(**r) for r in result_data.get("actionable_improvements", [])
        ]

        return RootCauseAnalysisResult(
            problem_category=result_data.get("problem_category", ""),
            initial_cause=result_data.get("initial_cause", ""),
            deep_root_causes=deep_root_causes,
            actionable_improvements=actionable_improvements,
            checklist_recommendations=result_data.get("checklist_recommendations", []),
            requirement_check=result_data.get("requirement_check")
            if isinstance(result_data.get("requirement_check"), dict)
            else {},
        )

    def analyze_to_dict(
        self, fault_input: FaultAnalysisInput, existing_analysis: ExistingFaultAnalysis
    ) -> dict:
        """
        同步版本：将分析结果转为字典

        Returns:
            dict: 根因分析结果的字典形式
        """
        import asyncio

        result = asyncio.run(self.analyze(fault_input, existing_analysis))
        return asdict(result)
