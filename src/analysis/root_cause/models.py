"""根因分析数据模型"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RequirementContext:
    """需求-测试传导链例行检查的输入证据。

    背景（案例 11757372）：gomo 号码段校验规则在整条需求链上均无定义，
    研发只能按通用逻辑实现、测试无验收依据可覆盖该分支——"需求验收
    标准不明确 → 研发跑偏/遗漏 → 测试未覆盖"是典型故障传导链，
    复盘中应例行核查。
    """

    # 关联的需求/任务单（父单优先，其次引入单；均无则留空）
    requirement_no: str = ""
    requirement_title: str = ""
    requirement_desc: str = ""
    # 故障单关联的测试用例 ID 列表（内容在测试平台，此处仅作覆盖事实）
    test_case_ids: list[int] = field(default_factory=list)
    # 关联来源说明：parent_task / introduce_task / none
    source: str = ""
    # 证据缺失声明（如实列出，禁止在分析中脑补缺失部分）
    data_gaps: list[str] = field(default_factory=list)


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
    # 普通根因链路（基于代码 diff）已确认的结论，作为深度分析的事实锚点
    prior_root_causes: list[dict[str, Any]] = field(default_factory=list)
    # 引入缺陷任务单的代码变更 diff（未填写引入单号时为空串）
    introduce_task_diff: str = ""
    # 需求-测试传导链例行检查的证据上下文（采集失败时含 data_gaps 声明）
    requirement_context: RequirementContext = field(default_factory=RequirementContext)


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
    # 需求-测试传导链例行检查结论（LLM 未输出时为空 dict，向后兼容）
    requirement_check: dict[str, Any] = field(default_factory=dict)
