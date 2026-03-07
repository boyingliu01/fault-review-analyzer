"""根因可落地性验证器 - 验证根因是否可落地并生成改进措施"""

from __future__ import annotations

import re
from typing import Any

from loguru import logger

from src.core.models import (
    ImprovementMeasure,
    RootCauseValidation,
)

NON_ACTIONABLE_PATTERNS = [
    r"场景.*不(?:周全|足)|考虑.*不足",
    r"经验.*不足|能力.*不足",
    r"疏忽.*|(?:粗心|大意).*导致",
    r".*问题.*原因.*不.*清楚",
    r"未.*找到.*根本.*原因",
]

ACTIONABLE_KEYWORDS = {
    "high": [
        "关闭",
        "释放",
        "校验",
        "验证",
        "检查",
        "配置",
        "设置",
        "权限",
        "认证",
        "加密",
    ],
    "medium": [
        "优化",
        "改进",
        "完善",
        "添加",
        "增强",
        "重构",
        "拆分",
        "简化",
        "规范",
    ],
    "low": [
        "培训",
        "学习",
        "加强",
        "提高",
    ],
}

MEASURE_TEMPLATES = {
    "database_connection": [
        ImprovementMeasure(
            id="MEASURE-001",
            description="使用try-with-resources确保资源自动关闭",
            acceptance_criteria="所有数据库操作使用try-with-resources语法",
            expected_impact="消除连接泄漏风险",
            priority="high",
        ),
        ImprovementMeasure(
            id="MEASURE-002",
            description="在finally块中显式关闭资源",
            acceptance_criteria="所有资源在finally中关闭",
            expected_impact="确保资源一定被释放",
            priority="high",
        ),
    ],
    "null_pointer": [
        ImprovementMeasure(
            id="MEASURE-003",
            description="方法入口添加空值校验",
            acceptance_criteria="public方法参数必须进行null检查",
            expected_impact="提前发现空指针异常",
            priority="high",
        ),
        ImprovementMeasure(
            id="MEASURE-004",
            description="使用Optional处理可能为null的场景",
            acceptance_criteria="返回值使用Optional包装",
            expected_impact="强制调用方处理null情况",
            priority="medium",
        ),
    ],
    "sql_injection": [
        ImprovementMeasure(
            id="MEASURE-005",
            description="使用参数化查询",
            acceptance_criteria="禁止字符串拼接SQL",
            expected_impact="消除SQL注入风险",
            priority="high",
        ),
        ImprovementMeasure(
            id="MEASURE-006",
            description="使用ORM框架的查询构建器",
            acceptance_criteria="使用MyBatis/Hibernate等ORM",
            expected_impact="自动处理SQL转义",
            priority="medium",
        ),
    ],
    "concurrency": [
        ImprovementMeasure(
            id="MEASURE-007",
            description="使用线程安全集合",
            acceptance_criteria="多线程场景使用ConcurrentHashMap等",
            expected_impact="消除并发安全问题",
            priority="high",
        ),
        ImprovementMeasure(
            id="MEASURE-008",
            description="添加同步机制",
            acceptance_criteria="关键代码块使用synchronized或Lock",
            expected_impact="保证线程安全",
            priority="high",
        ),
    ],
    "resource_leak": [
        ImprovementMeasure(
            id="MEASURE-009",
            description="资源使用try-with-resources",
            acceptance_criteria="所有资源使用自动管理",
            expected_impact="防止资源泄漏",
            priority="high",
        ),
        ImprovementMeasure(
            id="MEASURE-010",
            description="添加资源监控告警",
            acceptance_criteria="监控连接池、线程池使用率",
            expected_impact="及时发现资源异常",
            priority="medium",
        ),
    ],
}


class RootCauseValidator:
    """根因可落地性验证器 - 验证根因是否可落地并生成具体改进措施"""

    def __init__(self) -> None:
        self._non_actionable_patterns = [
            re.compile(p, re.IGNORECASE) for p in NON_ACTIONABLE_PATTERNS
        ]

    def validate(self, root_cause: str) -> RootCauseValidation:
        """验证根因是否可落地

        Args:
            root_cause: 根因描述

        Returns:
            RootCauseValidation: 验证结果
        """
        if not root_cause or not root_cause.strip():
            return RootCauseValidation(
                root_cause=root_cause,
                is_actionable=False,
                actionability_score=0.0,
                improvement_measures=[],
                validation_reason="根因为空，无法验证",
                needs_reanalysis=True,
                reanalysis_feedback="请提供具体的根因描述",
            )

        is_actionable, reason = self._check_actionability(root_cause)

        actionability_score = self._calculate_score(root_cause, is_actionable)

        improvement_measures = self._generate_measures(root_cause)

        needs_reanalysis = not is_actionable

        reanalysis_feedback = ""
        if needs_reanalysis:
            reanalysis_feedback = self._generate_reanalysis_feedback(root_cause)

        return RootCauseValidation(
            root_cause=root_cause,
            is_actionable=is_actionable,
            actionability_score=actionability_score,
            improvement_measures=improvement_measures,
            validation_reason=reason,
            needs_reanalysis=needs_reanalysis,
            reanalysis_feedback=reanalysis_feedback,
        )

    def _check_actionability(self, root_cause: str) -> tuple[bool, str]:
        """检查根因是否可落地"""
        root_cause_lower = root_cause.lower()

        for pattern in self._non_actionable_patterns:
            if pattern.search(root_cause):
                return False, f"根因过于笼统，属于不可落地类型: {root_cause}"

        if len(root_cause) < 10:
            return False, "根因描述过于简短，无法生成具体措施"

        actionable_count = sum(
            1
            for keywords in ACTIONABLE_KEYWORDS.values()
            if any(kw in root_cause_lower for kw in keywords)
        )

        if actionable_count == 0:
            return False, "根因中未包含可执行的动作关键词"

        return True, "根因包含具体可执行的动作"

    def _calculate_score(self, root_cause: str, is_actionable: bool) -> float:
        """计算可落地性评分"""
        if not is_actionable:
            return 0.3

        score = 0.5

        root_cause_lower = root_cause.lower()

        if any(kw in root_cause_lower for kw in ACTIONABLE_KEYWORDS["high"]):
            score += 0.3

        if any(kw in root_cause_lower for kw in ACTIONABLE_KEYWORDS["medium"]):
            score += 0.15

        if len(root_cause) > 20:
            score += 0.1

        specific_terms = ["数据库", "连接", "资源", "空指针", "并发", "线程", "SQL", "注入"]
        if any(term in root_cause_lower for term in specific_terms):
            score += 0.1

        return min(score, 1.0)

    def _generate_measures(self, root_cause: str) -> list[ImprovementMeasure]:
        """生成改进措施"""
        root_cause_lower = root_cause.lower()
        measures = []

        if "数据库" in root_cause_lower or "连接" in root_cause_lower:
            measures.extend(MEASURE_TEMPLATES.get("database_connection", []))
            measures.extend(MEASURE_TEMPLATES.get("resource_leak", []))

        if "空指针" in root_cause_lower or "null" in root_cause_lower:
            measures.extend(MEASURE_TEMPLATES.get("null_pointer", []))

        if "sql" in root_cause_lower or "注入" in root_cause_lower:
            measures.extend(MEASURE_TEMPLATES.get("sql_injection", []))

        if (
            "并发" in root_cause_lower
            or "线程" in root_cause_lower
            or "线程安全" in root_cause_lower
        ):
            measures.extend(MEASURE_TEMPLATES.get("concurrency", []))

        if "资源" in root_cause_lower or "泄漏" in root_cause_lower:
            measures.extend(MEASURE_TEMPLATES.get("resource_leak", []))

        if not measures:
            measures = self._generate_generic_measures(root_cause)

        return measures[:5]

    def _generate_generic_measures(self, root_cause: str) -> list[ImprovementMeasure]:
        """生成通用改进措施"""
        measure_id = len(MEASURE_TEMPLATES) + 1

        return [
            ImprovementMeasure(
                id=f"MEASURE-{measure_id:03d}",
                description=f"针对根因'{root_cause}'制定专项改进计划",
                acceptance_criteria="制定可执行的改进计划并落地",
                expected_impact="消除或降低该类问题发生概率",
                priority="medium",
            ),
        ]

    def _generate_reanalysis_feedback(self, root_cause: str) -> str:
        """生成重新分析反馈"""
        return f"""根因'{root_cause}'过于笼统或抽象，无法制定具体的改进措施。
建议从以下角度重新分析:
1. 明确指出具体的技术问题（如：数据库连接未关闭、空指针未校验）
2. 指出具体的代码位置或模块
3. 指出具体的违规规范条款
4. 区分是流程问题还是技术问题
请提供更具体、可操作的根因描述。"""

    def validate_with_llm(self, root_cause: str, llm_provider: Any) -> RootCauseValidation:
        """使用LLM进行更深入的验证

        Args:
            root_cause: 根因描述
            llm_provider: LLM提供商

        Returns:
            RootCauseValidation: 验证结果
        """
        prompt = self._build_llm_prompt(root_cause)

        try:
            response = llm_provider.generate(prompt)
            return self._parse_llm_response(response, root_cause)
        except Exception as e:
            logger.error(f"LLM根因验证失败: {e}")
            return self.validate(root_cause)

    def _build_llm_prompt(self, root_cause: str) -> str:
        """构建LLM验证提示词"""
        return f"""你是一个根因分析专家。请验证以下根因是否可落地并生成改进措施。

## 根因
{root_cause}

请分析并返回JSON格式的验证结果:
{{
    "is_actionable": true/false,
    "actionability_score": 0.0-1.0,
    "validation_reason": "验证理由",
    "improvement_measures": [
        {{
            "id": "MEASURE-001",
            "description": "改进措施描述",
            "acceptance_criteria": "验收标准",
            "expected_impact": "预期影响",
            "priority": "high/medium/low"
        }}
    ],
    "needs_reanalysis": true/false,
    "reanalysis_feedback": "如果需要重新分析，给出反馈"
}}
"""

    def _parse_llm_response(self, response: str, root_cause: str) -> RootCauseValidation:
        """解析LLM响应"""
        import json

        try:
            json_match = re.search(r"\{[^{}]*\}", response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())

                measures = []
                for m in data.get("improvement_measures", []):
                    measures.append(
                        ImprovementMeasure(
                            id=m.get("id", ""),
                            description=m.get("description", ""),
                            acceptance_criteria=m.get("acceptance_criteria", ""),
                            expected_impact=m.get("expected_impact", ""),
                            priority=m.get("priority", "medium"),
                        )
                    )

                return RootCauseValidation(
                    root_cause=root_cause,
                    is_actionable=data.get("is_actionable", False),
                    actionability_score=data.get("actionability_score", 0.5),
                    improvement_measures=measures,
                    validation_reason=data.get("validation_reason", ""),
                    needs_reanalysis=data.get("needs_reanalysis", False),
                    reanalysis_feedback=data.get("reanalysis_feedback", ""),
                )
        except Exception as e:
            logger.error(f"解析LLM响应失败: {e}")

        return self.validate(root_cause)
