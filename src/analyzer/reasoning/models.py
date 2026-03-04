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
