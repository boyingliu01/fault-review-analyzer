import json
import re
from pathlib import Path
from typing import Any

from loguru import logger

from .models import Rule, RuleViolation

BUILTIN_RULES: list[dict] = [
    {
        "id": "security-001",
        "name": "敏感信息泄露",
        "description": "检测代码中是否包含敏感信息如密码、密钥等",
        "category": "security",
        "severity": "critical",
        "pattern": r"(password|secret|key|token|api_key|apikey)\s*=\s*['\"][^'\"]+['\"]",
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
        """Check task data against all rules."""
        violations = []

        code_content = ""
        if task_data.get("development"):
            dev = task_data["development"]
            if isinstance(dev, dict):
                for commit in dev.get("commits", []):
                    code_content += commit.get("message", "") + "\n"

        for rule in self._rules.values():
            if not rule.enabled:
                continue

            if rule.pattern:
                matches = re.findall(rule.pattern, code_content, re.IGNORECASE)
                if matches:
                    violations.append(
                        RuleViolation(
                            rule_id=rule.id,
                            rule_name=rule.name,
                            severity=rule.severity,
                            message=rule.message,
                            evidence=[str(m) for m in matches[:5]],
                        )
                    )

        return violations
