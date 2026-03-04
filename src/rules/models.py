from dataclasses import dataclass, field


@dataclass
class Rule:
    """Represents a rule definition."""

    id: str
    name: str
    description: str
    category: str
    severity: str
    pattern: str = ""
    condition: str = ""
    message: str = ""
    enabled: bool = True


@dataclass
class RuleViolation:
    """Represents a rule violation."""

    rule_id: str
    rule_name: str
    severity: str
    message: str
    evidence: list[str] = field(default_factory=list)
    location: str = ""


@dataclass
class RuleCheckResult:
    """Result of rule checking."""

    task_id: int
    violations: list[RuleViolation] = field(default_factory=list)
    passed: bool = True
    summary: str = ""


@dataclass
class RulesConfig:
    """Configuration for rules engine."""

    builtin_enabled: bool = True
    custom_path: str = "./data/rules/custom/"
    cache_enabled: bool = True
