"""报告生成模块

该模块负责生成故障分析报告，支持单个任务、聚类和批量分析报告。
支持Markdown格式输出，可自定义Jinja2模板。
"""

from .generator import (
    ReportGenerator,
    ReportFormat,
    ReportType,
    ReportData,
    ChartData,
    TableData,
)
from .models import AnalysisReport, BatchReport, ClusterReport, ReportSection

__all__ = [
    "ReportGenerator",
    "ReportFormat",
    "ReportType",
    "ReportData",
    "ChartData",
    "TableData",
    "AnalysisReport",
    "BatchReport",
    "ClusterReport",
    "ReportSection",
]
