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
