from __future__ import annotations

import contextlib
import json
import re
from enum import Enum
from typing import TYPE_CHECKING, Any

from loguru import logger

from src.utils.diff_utils import extract_added_lines

from .models import Rule, RuleCheckResult, RuleViolation

if TYPE_CHECKING:
    from pathlib import Path

# ============================================================================
# Backward compatibility layer for tests
# Tests expect a different API than the current implementation.
# These wrappers adapt the old test API to the new implementation.
# ============================================================================


class RuleSeverity(str, Enum):
    """Backward-compatible severity enum for tests."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

    def __lt__(self, other: Any) -> bool:
        order = {"info": 0, "warning": 1, "error": 2, "critical": 3}
        if isinstance(other, RuleSeverity):
            return order[self.value] < order[other.value]
        return NotImplemented


class Violation:
    """Backward-compatible Violation class for tests.

    Wraps RuleViolation but accepts old-style constructor args.
    """

    def __init__(
        self,
        rule_id: str,
        message: str,
        location: str = "",
        context: dict[str, Any] | None = None,
    ) -> None:
        self.rule_id = rule_id
        self.message = message
        self.location = location
        self.context = context  # Keep None if None is passed

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "rule_id": self.rule_id,
            "message": self.message,
            "location": self.location,
            "context": self.context,
        }

    def to_rule_violation(self) -> RuleViolation:
        """Convert to the actual RuleViolation."""
        return RuleViolation(
            rule_id=self.rule_id,
            rule_name=self.rule_id,
            severity="error",
            message=self.message,
            location=self.location,
        )


class RuleEngine:
    """Backward-compatible RuleEngine that wraps RulesEngine.

    Provides the old API: rules list, config, register_rule/unregister_rule/get_rule/clear_rules/run_all.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._engine = RulesEngine()
        self.config: dict[str, Any] = config or {}
        self.rules: list[Rule] = []

    def register_rule(self, rule: Any) -> None:
        """Register a rule."""
        self.rules.append(rule)

    def unregister_rule(self, rule_id: str) -> None:
        """Remove a rule by ID. Does not raise if not found."""
        self.rules = [r for r in self.rules if r.id != rule_id]

    def get_rule(self, rule_id: str) -> Any | None:
        """Get a rule by ID."""
        for rule in self.rules:
            if rule.id == rule_id:
                return rule
        return None

    def clear_rules(self) -> None:
        """Clear all registered rules."""
        self.rules.clear()

    def run_all(self, code: str, context: dict[str, Any] | None = None) -> Any:
        """Run all registered rules and return results."""
        violations: list[Any] = []
        passed_rules = 0
        failed_rules = 0
        ctx = context or {}
        for rule in self.rules:
            try:
                if rule.check_function:
                    result = rule.check_function(code, ctx)
                    violations.extend(result)
                    if result:
                        failed_rules += 1
                    else:
                        passed_rules += 1
            except Exception:
                failed_rules += 1
        total_rules = len(self.rules)
        success = failed_rules == 0
        # Create a RuleCheckResult and dynamically add backward compat attrs
        result = RuleCheckResult(
            task_id=0,
            violations=[
                v.to_rule_violation() if hasattr(v, "to_rule_violation") else v for v in violations
            ],
            passed=success,
            summary=f"{len(violations)} violation(s) found",
        )
        # Dynamic compat attributes
        # type: ignore[attr-defined]
        result.total_rules = total_rules  # type: ignore[attr-defined]
        result.passed_rules = passed_rules  # type: ignore[attr-defined]
        result.failed_rules = failed_rules  # type: ignore[attr-defined]
        result.total_violations = len(violations)  # type: ignore[attr-defined]
        result.success = success  # type: ignore[attr-defined]
        return result


class RuleResult:
    """Backward-compatible rule result for tests."""

    def __init__(
        self,
        rule_id: str | None = None,
        passed: bool = True,
        violations: list[Any] | None = None,
        execution_time_ms: float = 0.0,
        total_rules: int = 0,
        total_violations: int = 0,
    ) -> None:
        self.rule_id = rule_id
        self.passed = passed
        self.violations = violations or []
        self.execution_time_ms = execution_time_ms
        self.total_rules = total_rules
        self.total_violations = total_violations


BUILTIN_RULES: list[dict] = [
    {
        "id": "security-001",
        "name": "敏感信息泄露",
        "description": "检测代码中是否包含敏感信息如密码、令牌、密钥等",
        "category": "security",
        "severity": "critical",
        # 只匹配明确的凭证类变量名；旧正则含裸词 key|token，IGNORECASE
        # 下 cacheKey/KEY 等普通变量名大量误报（修正前 41/181 单命中，
        # 证据全为变量名，如 11964009）。要求值长度 >=6 以过滤占位符。
        "pattern": (
            r"\b(password|passwd|pwd|secret|token|api_?key|access_?key"
            r"|secret_?key|private_?key|auth_?token|app_?secret)\w*"
            r"\s*[:=]\s*['\"][^'\"]{6,}['\"]"
        ),
        "flags": re.IGNORECASE,
        "message": "检测到敏感信息硬编码",
    },
    {
        "id": "security-002",
        "name": "SQL注入风险",
        "description": "检测是否存在SQL注入风险",
        "category": "security",
        "severity": "high",
        "pattern": r"(execute|exec|cursor\.execute)\s*\(\s*['\"].*\%s.*['\"]",
        "message": "存在SQL注入风险，建议使用参数化查询",
    },
    {
        "id": "code-001",
        "name": "未处理异常",
        "description": "检测是否有未捕获的异常",
        "category": "code",
        "severity": "medium",
        "pattern": r"except\s*:(\s*\n\s*(?!raise|return|pass))",
        "message": "检测到空的异常捕获",
    },
    {
        "id": "code-002",
        "name": "过长函数",
        "description": "检测函数是否过长",
        "category": "code",
        "severity": "low",
        "condition": "lines > 100",
        "message": "函数行数超过100行，建议拆分",
    },
    {
        "id": "perf-001",
        "name": "循环内字符串拼接",
        "description": "检测循环内是否使用字符串拼接",
        "category": "performance",
        "severity": "medium",
        "pattern": r"for\s+.*:\s*\n\s*[\+\=].*\+",
        "message": "循环内字符串拼接会影响性能，建议使用join",
    },
    {
        "id": "perf-002",
        "name": "N+1查询",
        "description": "检测是否存在N+1查询问题",
        "category": "performance",
        "severity": "high",
        "pattern": r"for\s+\w+\s+in\s+\w+:\s*\n\s*.*\.query\(",
        "message": "检测到循环内查询，可能存在N+1问题",
    },
]


class RulesEngine:
    """Rules engine for checking violations."""

    def __init__(self) -> None:
        self._rules: dict[str, Rule] = {}
        self._load_builtin_rules()

    def _load_builtin_rules(self) -> None:
        """Load built-in rules."""
        for rule_data in BUILTIN_RULES:
            rule = Rule(
                id=rule_data["id"],
                name=rule_data["name"],
                description=rule_data["description"],
                category=rule_data["category"],
                severity=rule_data["severity"],
                pattern=rule_data.get("pattern", ""),
                condition=rule_data.get("condition", ""),
                message=rule_data.get("message", ""),
                flags=rule_data.get("flags", re.IGNORECASE),
            )
            self._rules[rule.id] = rule

    def load_custom_rules(self, rules_path: Path) -> int:
        """Load custom rules from YAML/JSON files."""
        count = 0
        if not rules_path.exists():
            return count

        for file_path in rules_path.glob("*.yaml"):
            count += self._load_rules_from_yaml(file_path)
        for file_path in rules_path.glob("*.json"):
            count += self._load_rules_from_json(file_path)

        return count

    def _load_rules_from_yaml(self, file_path: Path) -> int:
        """Load rules from YAML file."""
        try:
            import yaml

            with file_path.open(encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data or "rules" not in data:
                return 0

            for rule_data in data["rules"]:
                rule = Rule(
                    id=rule_data.get("id", ""),
                    name=rule_data.get("name", ""),
                    description=rule_data.get("description", ""),
                    category=rule_data.get("category", "custom"),
                    severity=rule_data.get("severity", "medium"),
                    pattern=rule_data.get("pattern", ""),
                    condition=rule_data.get("condition", ""),
                    message=rule_data.get("message", ""),
                    enabled=rule_data.get("enabled", True),
                )
                if rule.id:
                    self._rules[rule.id] = rule

            return len(data.get("rules", []))
        except Exception as e:
            logger.error(f"Failed to load rules from {file_path}: {e}")
            return 0

    def _load_rules_from_json(self, file_path: Path) -> int:
        """Load rules from JSON file."""
        try:
            with file_path.open(encoding="utf-8") as f:
                data = json.load(f)

            if not data or "rules" not in data:
                return 0

            for rule_data in data["rules"]:
                rule = Rule(
                    id=rule_data.get("id", ""),
                    name=rule_data.get("name", ""),
                    description=rule_data.get("description", ""),
                    category=rule_data.get("category", "custom"),
                    severity=rule_data.get("severity", "medium"),
                    pattern=rule_data.get("pattern", ""),
                    condition=rule_data.get("condition", ""),
                    message=rule_data.get("message", ""),
                    enabled=rule_data.get("enabled", True),
                )
                if rule.id:
                    self._rules[rule.id] = rule

            return len(data.get("rules", []))
        except Exception as e:
            logger.error(f"Failed to load rules from {file_path}: {e}")
            return 0

    def get_rule(self, rule_id: str) -> Rule | None:
        """Get a rule by ID."""
        return self._rules.get(rule_id)

    def get_all_rules(self) -> list[Rule]:
        """Get all loaded rules."""
        return list(self._rules.values())

    def get_rules_by_category(self, category: str) -> list[Rule]:
        """Get rules by category."""
        return [r for r in self._rules.values() if r.category == category]

    def check(self, task_data: dict[str, Any]) -> list[RuleViolation]:
        """Check task data against all rules.

        优先检查代码diff内容，如果没有diff则降级到检查commit message。
        diff 只检测新增行（+ 行）：删除行是本次被移除的代码、上下文行
        是未变更的历史代码，混入会把历史/已删除代码误判为本次引入的违规。
        """
        violations = []

        # 收集可检查的代码内容
        code_parts: list[str] = []
        max_content_size = 500_000  # 500KB 上限，防止大 diff 导致性能问题

        if task_data.get("development"):
            dev = task_data["development"]
            if isinstance(dev, dict):
                # 首先尝试从commits中获取diff（只取新增行）
                for commit in dev.get("commits", []):
                    diff = commit.get("diff", "")
                    if diff:
                        code_parts.append(extract_added_lines(diff))
                    else:
                        # 降级：使用commit message
                        code_parts.append(commit.get("message", ""))

                # code_changes 只检测新代码；old_content 是变更前代码，
                # 混入会把"被删除的代码"误判为本次引入的违规
                for change in dev.get("code_changes", []):
                    new_content = change.get("new_content", "")
                    if new_content:
                        code_parts.append(new_content)

        # 使用 join 代替 += 拼接，限制总大小
        code_content = "\n".join(code_parts)[:max_content_size]

        for rule in self._rules.values():
            if not rule.enabled:
                continue

            if rule.pattern:
                evidence = self._match_with_context(rule, code_content)
                if evidence:
                    violations.append(
                        RuleViolation(
                            rule_id=rule.id,
                            rule_name=rule.name,
                            severity=rule.severity,
                            message=rule.message,
                            evidence=evidence,
                        )
                    )

        return violations

    @staticmethod
    def _match_with_context(rule: Rule, code_content: str) -> list[str]:
        """正则匹配并返回带上下文的证据行（最多5条）。

        旧实现用 re.findall + str(m)：带分组的 pattern 只返回分组元组，
        证据沦为裸关键词（如 ['KEY','key',...]），无法复核。此处改为
        返回完整匹配所在的代码行；每条规则使用自己的 flags。
        """
        evidences: list[str] = []
        try:
            for m in re.finditer(rule.pattern, code_content, rule.flags):
                line_start = code_content.rfind("\n", 0, m.start()) + 1
                line_end = code_content.find("\n", m.end())
                if line_end == -1:
                    line_end = len(code_content)
                line = code_content[line_start:line_end].strip()
                if line:
                    evidences.append(line[:200])
                if len(evidences) >= 5:
                    break
        except re.error as e:
            logger.warning(f"规则 {rule.id} 正则执行失败: {e}")
        return evidences


# ============================================================================
# Monkey-patch Rule.execute for backward compat with old test API
# ============================================================================


def _rule_execute(self: Rule, code: str, context: dict[str, Any] | None = None) -> RuleResult:
    """Execute a rule check. Backward compat for old test API."""
    ctx = context or {}
    violations: list[Any] = []
    if self.check_function:
        with contextlib.suppress(Exception):
            violations = self.check_function(code, ctx)
    passed = len(violations) == 0
    return RuleResult(
        rule_id=self.id,
        passed=passed,
        violations=violations,
        execution_time_ms=1.0,
    )


Rule.execute = _rule_execute  # type: ignore[attr-defined]
