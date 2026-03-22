"""根因分析数据模型"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FaultAnalysisInput:
    """故障分析输入"""

    task_no: str
    title: str
    description: str
    task_src: str
    created_date: str
    finish_date: str
    product_module_id: int | None = None
    product_version_id: int | None = None


@dataclass
class ExistingFaultAnalysis:
    """现有故障复盘结论"""

    dev_catalog: str = ""
    dev_catalog_detail: str = ""
    dev_reason: str = ""
    dev_conclusion: str = ""
    dev_improve_stage: str = ""
    test_catalog: str = ""
    test_catalog_detail: str = ""
    test_reason: str = ""
    test_conclusion: str = ""
    test_improve_stage: str = ""


@dataclass
class RootCause:
    """深层根因"""

    layer: str
    root_cause: str
    why_reason: str
    evidence: str


@dataclass
class ActionableImprovement:
    """可落地改进措施"""

    type: str
    action: str
    owner: str
    priority: str


@dataclass
class RootCauseAnalysisResult:
    """根因分析结果"""

    problem_category: str
    initial_cause: str
    deep_root_causes: list[RootCause] = field(default_factory=list)
    actionable_improvements: list[ActionableImprovement] = field(default_factory=list)
    checklist_recommendations: list[str] = field(default_factory=list)
