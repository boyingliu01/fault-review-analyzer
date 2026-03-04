from dataclasses import dataclass, field
from typing import Any


@dataclass
class ReportSection:
    """Represents a section in a report."""

    title: str
    content: str
    level: int = 1


@dataclass
class AnalysisReport:
    """Complete analysis report data structure."""

    task_id: int
    title: str
    summary: str
    segments: list[dict] = field(default_factory=list)
    labels: list[dict] = field(default_factory=list)
    root_causes: list[dict] = field(default_factory=list)
    clusters: list[dict] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    sections: list[ReportSection] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ClusterReport:
    """Cluster analysis report."""

    cluster_id: int
    task_count: int
    labels: list[dict]
    common_root_causes: list[dict]
    summary: str
    suggestions: list[str]
    tasks: list[dict] = field(default_factory=list)


@dataclass
class BatchReport:
    """Batch analysis report."""

    total_tasks: int
    cluster_count: int
    cluster_reports: list[ClusterReport]
    overall_summary: str
    recommendations: list[str]
