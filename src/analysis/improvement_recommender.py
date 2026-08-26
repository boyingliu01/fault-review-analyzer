"""改进措施推荐器 - 为高频根因生成专项改进措施"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast

from loguru import logger

DEFAULT_CATEGORY = "代码类"


@dataclass
class ImprovementMeasure:
    """改进措施数据模型"""

    root_cause: str
    measure: str
    acceptance_criteria: str
    expected_impact: str
    priority: str = "medium"  # high, medium, low
    category: str = ""  # 改进措施类别
    responsible_role: str = ""  # 负责角色
    deadline: str = ""  # 建议完成时间
    rule_ids: list[str] = field(default_factory=list)  # 关联的规范条款编号（如 J000001）


@dataclass
class RootCauseFrequency:
    """根因频率统计"""

    root_cause: str
    count: int
    percentage: float
    is_violation: bool = False


class ImprovementRecommender:
    """改进措施推荐器 - 基于根因频率生成改进措施"""

    # 预定义的改进措施模板
    MEASURE_TEMPLATES: dict[str, dict[str, Any]] = {
        "违规类": {
            "high": {
                "measure": "开展专项规范培训，建立规范检查自动化流程",
                "acceptance_criteria": "规范培训覆盖率100%，自动化检查拦截率>90%",
                "expected_impact": "减少80%的规范违规类故障",
            },
            "medium": {
                "measure": "定期组织规范学习和代码审查",
                "acceptance_criteria": "每月至少1次规范学习，代码审查覆盖率>80%",
                "expected_impact": "减少50%的规范违规类故障",
            },
        },
        "需求类": {
            "high": {
                "measure": "建立需求评审checklist和评审机制",
                "acceptance_criteria": "所有需求必须经过评审，评审问题闭环率100%",
                "expected_impact": "减少60%的需求遗漏类故障",
            },
            "medium": {
                "measure": "完善需求文档模板，加强需求确认",
                "acceptance_criteria": "需求文档完整度>90%，需求确认签字率100%",
                "expected_impact": "减少40%的需求遗漏类故障",
            },
        },
        "设计类": {
            "high": {
                "measure": "引入设计评审机制，建立设计模式库",
                "acceptance_criteria": "核心模块必须经过设计评审，设计模式复用率>70%",
                "expected_impact": "减少50%的设计缺陷类故障",
            },
            "medium": {
                "measure": "加强设计文档编写，推广最佳实践",
                "acceptance_criteria": "设计文档覆盖率>80%，最佳实践推广率>60%",
                "expected_impact": "减少30%的设计缺陷类故障",
            },
        },
        "代码类": {
            "high": {
                "measure": "强化代码审查，引入静态代码分析工具",
                "acceptance_criteria": "代码审查覆盖率100%，静态分析问题清零",
                "expected_impact": "减少70%的代码bug类故障",
            },
            "medium": {
                "measure": "完善单元测试，提升测试覆盖率",
                "acceptance_criteria": "单元测试覆盖率>80%，核心逻辑覆盖率>90%",
                "expected_impact": "减少50%的代码bug类故障",
            },
        },
        "测试类": {
            "high": {
                "measure": "完善测试用例设计，引入自动化测试",
                "acceptance_criteria": "测试用例评审覆盖率100%，自动化测试率>60%",
                "expected_impact": "减少60%的测试遗漏类故障",
            },
            "medium": {
                "measure": "加强测试用例评审，完善边界测试",
                "acceptance_criteria": "测试用例评审覆盖率>80%，边界场景覆盖率>70%",
                "expected_impact": "减少40%的测试遗漏类故障",
            },
        },
        "运维类": {
            "high": {
                "measure": "建立完善的监控告警体系，完善应急预案",
                "acceptance_criteria": "核心指标监控覆盖率100%，应急预案演练通过率100%",
                "expected_impact": "减少70%的运维操作类故障",
            },
            "medium": {
                "measure": "规范变更流程，加强变更评审",
                "acceptance_criteria": "变更评审覆盖率>90%，变更回滚时间<30分钟",
                "expected_impact": "减少50%的运维操作类故障",
            },
        },
    }

    def __init__(self) -> None:
        self._templates = self.MEASURE_TEMPLATES

    def calculate_frequencies(
        self,
        root_causes: list[str],
        violation_causes: list[str] | None = None,
    ) -> list[RootCauseFrequency]:
        """计算根因频率

        Args:
            root_causes: 根因列表
            violation_causes: 违规类根因列表

        Returns:
            按频率排序的根因频率列表
        """
        if not root_causes:
            return []

        violation_set = set(violation_causes or [])
        cause_counts: dict[str, int] = {}

        for cause in root_causes:
            cause_counts[cause] = cause_counts.get(cause, 0) + 1

        total = len(root_causes)
        frequencies = []

        for cause, count in cause_counts.items():
            freq = RootCauseFrequency(
                root_cause=cause,
                count=count,
                percentage=round(count / total * 100, 1),
                is_violation=cause in violation_set,
            )
            frequencies.append(freq)

        frequencies.sort(key=lambda x: x.count, reverse=True)
        return frequencies

    def recommend_measures(
        self,
        root_causes: list[str],
        violation_causes: list[str] | None = None,
        top_n: int = 10,
        rule_ids_by_cause: dict[str, list[str]] | None = None,
    ) -> list[ImprovementMeasure]:
        """推荐改进措施

        Args:
            root_causes: 根因列表
            violation_causes: 违规类根因列表
            top_n: 返回前N个改进措施
            rule_ids_by_cause: 根因到规范条款编号的映射（如 {"并发问题": ["J000066"]}）

        Returns:
            改进措施列表
        """
        if not root_causes:
            logger.warning("根因列表为空，无法生成改进措施")
            return []

        frequencies = self.calculate_frequencies(root_causes, violation_causes)
        measures = []

        for freq in frequencies[:top_n]:
            rule_ids = (rule_ids_by_cause or {}).get(freq.root_cause, [])
            measure = self._generate_measure_for_root_cause(
                freq, freq.is_violation, rule_ids=rule_ids
            )
            if measure:
                measures.append(measure)

        return self._sort_by_priority(measures)

    def _generate_measure_for_root_cause(
        self,
        freq: RootCauseFrequency,
        is_violation: bool = False,
        rule_ids: list[str] | None = None,
    ) -> ImprovementMeasure | None:
        """为单个根因生成改进措施"""
        root_cause = freq.root_cause
        percentage = freq.percentage

        # 确定优先级
        if is_violation or percentage >= 20:
            priority = "high"
        elif percentage >= 10:
            priority = "medium"
        else:
            priority = "low"

        # 确定类别
        category = self._categorize_root_cause(root_cause)

        # 获取模板
        template = self._get_template(category, priority)

        return ImprovementMeasure(
            root_cause=root_cause,
            measure=template["measure"],
            acceptance_criteria=template["acceptance_criteria"],
            expected_impact=f"预计减少{template['expected_impact'].replace('减少', '')}（当前占比{percentage}%）",
            priority=priority,
            category=category,
            rule_ids=list(rule_ids or []),
        )

    def _categorize_root_cause(self, root_cause: str) -> str:
        """对根因进行分类"""
        violation_keywords = ["规范", "违规", "违反", "不符合", "未遵循"]
        demand_keywords = ["需求", "遗漏", "缺失", "不明确"]
        design_keywords = ["设计", "架构", "方案"]
        code_keywords = ["代码", "bug", "缺陷", "实现", "逻辑"]
        test_keywords = ["测试", "用例", "覆盖", "遗漏"]
        ops_keywords = ["运维", "部署", "配置", "发布", "变更"]

        cause_lower = root_cause.lower()

        if any(k in cause_lower for k in violation_keywords):
            return "违规类"
        elif any(k in cause_lower for k in demand_keywords):
            return "需求类"
        elif any(k in cause_lower for k in design_keywords):
            return "设计类"
        elif any(k in cause_lower for k in code_keywords):
            return "代码类"
        elif any(k in cause_lower for k in test_keywords):
            return "测试类"
        elif any(k in cause_lower for k in ops_keywords):
            return "运维类"
        else:
            return DEFAULT_CATEGORY  # 默认类别

    def _get_template(self, category: str, priority: str) -> dict[str, Any]:
        """获取改进措施模板"""
        category_templates = self._templates.get(category, self._templates[DEFAULT_CATEGORY])
        return cast(
            "dict[str, Any]", category_templates.get(priority, category_templates["medium"])
        )

    def _sort_by_priority(self, measures: list[ImprovementMeasure]) -> list[ImprovementMeasure]:
        """按优先级排序"""
        priority_order = {"high": 0, "medium": 1, "low": 2}
        return sorted(measures, key=lambda x: priority_order.get(x.priority, 3))

    def filter_by_priority(
        self,
        measures: list[ImprovementMeasure],
        priority: str,
    ) -> list[ImprovementMeasure]:
        """按优先级筛选改进措施"""
        return [m for m in measures if m.priority == priority]

    def generate_report(
        self,
        measures: list[ImprovementMeasure],
        title: str = "改进措施建议报告",
    ) -> str:
        """生成改进措施报告"""
        if not measures:
            return "暂无改进措施建议"

        lines = [f"# {title}", ""]

        priority_names = {"high": "高优先级", "medium": "中优先级", "low": "低优先级"}
        current_priority = None

        for measure in measures:
            if measure.priority != current_priority:
                current_priority = measure.priority
                lines.append(f"\n## {priority_names.get(current_priority, current_priority)}")
                lines.append("")

            lines.append(f"### {measure.root_cause}")
            lines.append("")
            lines.append(f"**改进措施**: {measure.measure}")
            lines.append("")
            lines.append(f"**验收标准**: {measure.acceptance_criteria}")
            lines.append("")
            lines.append(f"**预期影响**: {measure.expected_impact}")
            lines.append("")
            if measure.category:
                lines.append(f"**类别**: {measure.category}")
                lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)
