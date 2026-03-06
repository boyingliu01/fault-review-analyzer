from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from loguru import logger

from .models import BatchReport, ClusterReport

DEFAULT_TEMPLATE = """# 故障复盘分析报告

## 基本信息

- **任务ID**: {{ task_id }}
- **标题**: {{ title }}
- **概要**: {{ summary }}

{% if segments %}
## 故障详情

{% for segment in segments %}
### {{ segment.type }}

{{ segment.content[:500] }}

{% endfor %}
{% endif %}

{% if labels %}
## 分类标签

{% for label in labels %}
- **{{ label.name }}** ({{ label.category }}) - 置信度: {{ "%.0f%%"|format(label.confidence * 100) }}
  {% if label.description %}{{ label.description }}{% endif %}

{% endfor %}
{% endif %}

{% if root_causes %}
## 根因分析

{% for cause in root_causes %}
### {{ cause.cause_type }}

{{ cause.description }}

**证据**:
{% for evidence in cause.evidence %}
- {{ evidence }}
{% endfor %}

置信度: {{ "%.0f%%"|format(cause.confidence * 100) }}

{% endfor %}
{% endif %}

{% if suggestions %}
## 改进建议

{% for suggestion in suggestions %}
{{ loop.index }}. {{ suggestion }}
{% endfor %}
{% endif %}

---
*报告生成时间: {{ metadata.generated_at }}*
"""


CLUSTER_TEMPLATE = """# 故障聚类分析报告

## 聚类概览

- **聚类ID**: {{ cluster_id }}
- **任务数量**: {{ task_count }}

## 聚类标签

{% for label in labels %}
- {{ label.name }} ({{ label.category }})
{% endfor %}

## 共同特征

{{ summary }}

{% if common_root_causes %}
## 共同根因

{% for cause in common_root_causes %}
- {{ cause.cause_type }}: {{ cause.description }}
{% endfor %}
{% endif %}

{% if suggestions %}
## 改进建议

{% for suggestion in suggestions %}
{{ loop.index }}. {{ suggestion }}
{% endfor %}
{% endif %}

---
*聚类分析报告*
"""


BATCH_TEMPLATE = """# 批量故障分析报告

## 总体概览

- **总任务数**: {{ total_tasks }}
- **聚类数量**: {{ cluster_count }}

## 聚类汇总

{% for cluster in cluster_reports %}
### 聚类 {{ cluster.cluster_id }} ({{ cluster.task_count }} 个任务)

{{ cluster.summary[:300] }}

{% if cluster.labels %}
标签: {{ cluster.labels|map(attribute='name')|join(', ') }}
{% endif %}

{% endfor %}

{% if recommendations %}
## 整体建议

{% for rec in recommendations %}
{{ loop.index }}. {{ rec }}
{% endfor %}
{% endif %}

---
*批量分析报告 - 生成时间: {{ generated_at }}*
"""


class ReportGenerator:
    """Generate reports from analysis results."""

    def __init__(self, template_dir: Path | None = None):
        self._template_dir = template_dir
        self._env = None
        if template_dir and template_dir.exists():
            self._env = Environment(
                loader=FileSystemLoader(str(template_dir)),
                autoescape=select_autoescape(),
            )

    def generate_single(
        self,
        task_data: dict[str, Any],
        segments: list[dict] | None = None,
        labels: list[dict] | None = None,
        root_causes: list[dict] | None = None,
        suggestions: list[str] | None = None,
    ) -> str:
        """Generate a single task analysis report."""
        if self._env:
            try:
                template = self._env.get_template("single.md.j2")
                return template.render(
                    task_id=task_data.get("task_id", 0),
                    title=task_data.get("title", ""),
                    summary=task_data.get("summary", ""),
                    segments=segments or [],
                    labels=labels or [],
                    root_causes=root_causes or [],
                    suggestions=suggestions or [],
                    metadata={
                        "generated_at": self._get_timestamp(),
                    },
                )
            except Exception as e:
                logger.warning(f"Custom template failed, using default: {e}")
                pass

        return self._render_single_markdown(task_data, segments, labels, root_causes, suggestions)

    def generate_cluster(
        self,
        cluster_report: ClusterReport,
    ) -> str:
        """Generate a cluster analysis report."""
        if self._env:
            try:
                template = self._env.get_template("cluster.md.j2")
                return template.render(
                    cluster_id=cluster_report.cluster_id,
                    task_count=cluster_report.task_count,
                    labels=cluster_report.labels,
                    common_root_causes=cluster_report.common_root_causes,
                    summary=cluster_report.summary,
                    suggestions=cluster_report.suggestions,
                )
            except Exception as e:
                logger.warning(f"Custom template failed, using default: {e}")
                pass

        return self._render_cluster_markdown(cluster_report)

    def generate_batch(
        self,
        batch_report: BatchReport,
    ) -> str:
        """Generate a batch analysis report."""
        if self._env:
            try:
                template = self._env.get_template("batch.md.j2")
                return template.render(
                    total_tasks=batch_report.total_tasks,
                    cluster_count=batch_report.cluster_count,
                    cluster_reports=batch_report.cluster_reports,
                    recommendations=batch_report.recommendations,
                    generated_at=self._get_timestamp(),
                )
            except Exception as e:
                logger.warning(f"Custom template failed, using default: {e}")
                pass

        return self._render_batch_markdown(batch_report)

    def save_report(
        self,
        content: str,
        output_path: Path,
    ) -> None:
        """Save report to file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")

    def _render_single_markdown(
        self,
        task_data: dict[str, Any],
        segments: list[dict] | None,
        labels: list[dict] | None,
        root_causes: list[dict] | None,
        suggestions: list[str] | None,
    ) -> str:
        """Render single task report with default template."""
        from jinja2 import Template

        template = Template(DEFAULT_TEMPLATE)
        return template.render(
            task_id=task_data.get("task_id", 0),
            title=task_data.get("title", ""),
            summary=task_data.get("summary", ""),
            segments=segments or [],
            labels=labels or [],
            root_causes=root_causes or [],
            suggestions=suggestions or [],
            metadata={
                "generated_at": self._get_timestamp(),
            },
        )

    def _render_cluster_markdown(self, cluster_report: ClusterReport) -> str:
        """Render cluster report with default template."""
        from jinja2 import Template

        template = Template(CLUSTER_TEMPLATE)
        return template.render(
            cluster_id=cluster_report.cluster_id,
            task_count=cluster_report.task_count,
            labels=cluster_report.labels,
            common_root_causes=cluster_report.common_root_causes,
            summary=cluster_report.summary,
            suggestions=cluster_report.suggestions,
        )

    def _render_batch_markdown(self, batch_report: BatchReport) -> str:
        """Render batch report with default template."""
        from jinja2 import Template

        template = Template(BATCH_TEMPLATE)
        return template.render(
            total_tasks=batch_report.total_tasks,
            cluster_count=batch_report.cluster_count,
            cluster_reports=batch_report.cluster_reports,
            recommendations=batch_report.recommendations,
            generated_at=self._get_timestamp(),
        )

    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime

        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
