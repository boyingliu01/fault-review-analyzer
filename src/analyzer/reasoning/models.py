from dataclasses import dataclass, field


@dataclass
class RootCause:
    """Represents a root cause analysis result.

    不含 confidence：LLM 自评置信度未校准，曾以高分误导复盘结论
    （如 11757372 的"设计缺陷 0.85"），已按用户决策（方案A）移除。
    """

    cause_type: str
    description: str
    evidence: list[str] = field(default_factory=list)


@dataclass
class RootCauseAnalysisResult:
    """Result of root cause analysis for a task."""

    task_id: int
    root_causes: list[RootCause]
    analysis_summary: str
    technical_factors: list[str]
    process_factors: list[str]
    management_factors: list[str]
