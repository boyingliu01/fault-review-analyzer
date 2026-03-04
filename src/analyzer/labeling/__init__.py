"""标签生成模块

该模块负责对故障单进行分类标签生成，基于LLM进行智能分析。
"""

from src.rules.categories import FAULT_CATEGORIES

from .generator import LabelGenerator
from .models import Label, LabelGenerationResult

__all__ = [
    "LabelGenerator",
    "Label",
    "LabelGenerationResult",
    "FAULT_CATEGORIES",
]
