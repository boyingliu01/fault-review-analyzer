"""高级规则引擎模型"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Union

from .models import Rule, RuleViolation


class OperatorType(Enum):
    """条件操作符类型"""

    AND = "AND"
    OR = "OR"
    NOT = "NOT"


@dataclass
class Condition:
    """规则条件"""

    left: Union["Condition", str]
    right: Union["Condition", str]
    operator: OperatorType
    value: str | int | float | bool | None = None


@dataclass
class RuleCondition:
    """规则条件配置"""

    conditions: list[Condition | str]
    operator: OperatorType = OperatorType.AND
    min_score: float = 0.0
    max_score: float = 1.0


@dataclass
class RuleMetadata:
    """规则元数据"""

    version: str = "1.0"
    author: str = ""
    created_at: str = ""
    updated_at: str = ""
    tags: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)


@dataclass
class AdvancedRule(Rule):
    """增强版规则"""

    priority: int = 10
    weight: float = 1.0
    conditions: RuleCondition | None = None
    metadata: RuleMetadata = field(default_factory=RuleMetadata)
    enabled: bool = True
    effective_from: str | None = None
    effective_to: str | None = None
    description_en: str = ""
    message_en: str = ""


@dataclass
class EnhancedRuleViolation(RuleViolation):
    """增强版违规记录"""

    rule_weight: float = 1.0
    rule_priority: int = 10
    score: float = 0.0
    matched_patterns: list[str] = field(default_factory=list)
    condition_results: dict[str, bool] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    source_text: str = ""


@dataclass
class RuleCheckResult:
    """规则检查结果"""

    task_id: int
    violations: list[EnhancedRuleViolation] = field(default_factory=list)
    passed: bool = True
    score: float = 100.0
    summary: str = ""
    processed_rules: int = 0
    matched_rules: int = 0


@dataclass
class RulesEvaluation:
    """规则引擎评估结果"""

    overall_score: float = 100.0
    violations: list[EnhancedRuleViolation] = field(default_factory=list)
    rules_evaluated: int = 0
    rules_triggered: int = 0
    rule_evaluations: dict[str, float] = field(default_factory=dict)
    category_scores: dict[str, float] = field(default_factory=dict)
    severity_distribution: dict[str, int] = field(default_factory=dict)
