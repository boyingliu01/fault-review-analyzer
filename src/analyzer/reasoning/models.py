from dataclasses import dataclass, field


@dataclass
class RootCause:
    """Represents a root cause analysis result."""

    cause_type: str
    description: str
    evidence: list[str] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class RootCauseAnalysisResult:
    """Result of root cause analysis for a task."""

    task_id: int
    root_causes: list[RootCause]
    analysis_summary: str
    technical_factors: list[str]
    process_factors: list[str]
    management_factors: list[str]


CAUSE_TYPES = [
    "需求不明确",
    "设计缺陷",
    "编码错误",
    "测试不足",
    "配置错误",
    "环境差异",
    "性能瓶颈",
    "安全漏洞",
    "数据异常",
    "接口问题",
    "第三方依赖",
    "运维失误",
    "变更管理",
    "沟通不足",
    "资源不足",
]
