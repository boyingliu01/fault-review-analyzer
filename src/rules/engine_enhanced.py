"""增强版规则引擎"""

import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from .advanced_models import (
    AdvancedRule,
    EnhancedRuleViolation,
    OperatorType,
    RulesEvaluation,
)
from .condition_evaluator import ConditionEvaluator
from .engine import RulesEngine as BaseRulesEngine
from .models import RuleViolation


class EnhancedRulesEngine(BaseRulesEngine):
    """增强版规则引擎"""

    def __init__(self):
        self._rules: dict[str, AdvancedRule] = {}
        self._evaluator = ConditionEvaluator()
        self._reload_lock = threading.RLock()
        self._last_reload = datetime.now()
        self._rules_path = Path("./data/rules/custom/")
        self._load_builtin_rules()

    def _load_builtin_rules(self) -> None:
        """加载内置规则"""
        from .engine import BUILTIN_RULES

        for rule_data in BUILTIN_RULES:
            rule = AdvancedRule(
                id=rule_data["id"],
                name=rule_data["name"],
                description=rule_data["description"],
                category=rule_data["category"],
                severity=rule_data["severity"],
                pattern=rule_data.get("pattern", ""),
                condition=rule_data.get("condition", ""),
                message=rule_data.get("message", ""),
                priority=rule_data.get("priority", 10),
                weight=rule_data.get("weight", 1.0),
            )
            self._rules[rule.id] = rule

    def load_custom_rules(self, rules_path: Path, hot_reload: bool = False) -> int:
        """
        加载自定义规则

        Args:
            rules_path: 规则文件路径
            hot_reload: 是否启用热重载

        Returns:
            加载的规则数量
        """
        self._rules_path = rules_path

        with self._reload_lock:
            initial_count = len(self.get_all_rules())
            count = super().load_custom_rules(rules_path)
            self._last_reload = datetime.now()

            if hot_reload:
                self._start_hot_reloader()

            logger.info(f"Loaded {count} custom rules")
            return count

    def _start_hot_reloader(self):
        """启动热重载监视"""
        if hasattr(self, "_hot_reloader"):
            return

        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer

        class RulesFileEventHandler(FileSystemEventHandler):
            def __init__(self, engine):
                self.engine = engine

            def on_modified(self, event):
                if event.src_path.endswith((".yaml", ".yml", ".json")):
                    logger.info(f"Rules file modified: {event.src_path}")
                    try:
                        self.engine.reload_rules()
                    except Exception as e:
                        logger.error(f"Failed to reload rules: {e}")

        self._hot_reloader = Observer()
        self._hot_reloader.schedule(
            RulesFileEventHandler(self),
            str(self._rules_path),
            recursive=True,
        )
        self._hot_reloader.start()
        logger.info("Hot reload monitoring started")

    def reload_rules(self) -> int:
        """
        重新加载所有规则

        Returns:
            加载的规则数量
        """
        with self._reload_lock:
            self._rules.clear()
            self._load_builtin_rules()
            count = self.load_custom_rules(self._rules_path)
            self._last_reload = datetime.now()
            logger.info(f"Rules reloaded. Total rules: {len(self.get_all_rules())}")
            return count

    def stop_hot_reloader(self):
        """停止热重载监视"""
        if hasattr(self, "_hot_reloader"):
            self._hot_reloader.stop()
            self._hot_reloader.join()
            delattr(self, "_hot_reloader")
            logger.info("Hot reload monitoring stopped")

    def __del__(self):
        self.stop_hot_reloader()

    def check_with_evaluation(
        self, task_data: dict[str, Any], context: dict[str, Any] | None = None
    ) -> RulesEvaluation:
        """
        检查任务数据并返回详细评估结果

        Args:
            task_data: 任务数据
            context: 上下文信息

        Returns:
            规则评估结果
        """
        violations = self._check_rules(task_data, context)
        return self._generate_evaluation(violations, task_data)

    def check(self, task_data: dict[str, Any]) -> list[RuleViolation]:
        """
        检查任务数据是否违反规则（兼容旧接口）

        Args:
            task_data: 任务数据

        Returns:
            违规列表
        """
        violations = self._check_rules(task_data)
        return [
            RuleViolation(
                rule_id=v.rule_id,
                rule_name=v.rule_name,
                severity=v.severity,
                message=v.message,
                evidence=v.evidence,
                location=v.location,
            )
            for v in violations
        ]

    def _check_rules(
        self, task_data: dict[str, Any], context: dict[str, Any] | None = None
    ) -> list[EnhancedRuleViolation]:
        """
        检查所有规则是否被违反

        Args:
            task_data: 任务数据
            context: 上下文信息

        Returns:
            违规列表
        """
        violations = []
        ctx = context or {}

        code_content = self._extract_code_content(task_data)

        for rule in sorted(
            self._rules.values(),
            key=lambda r: r.priority,
            reverse=True,
        ):
            if not rule.enabled:
                continue

            if self._is_rule_effective(rule):
                violation = self._check_single_rule(rule, code_content, task_data, ctx)
                if violation:
                    violations.append(violation)

        return violations

    def _extract_code_content(self, task_data: dict[str, Any]) -> str:
        """提取任务数据中的代码内容"""
        code_content = ""
        if task_data.get("development"):
            dev = task_data["development"]
            if isinstance(dev, dict):
                for commit in dev.get("commits", []):
                    code_content += commit.get("message", "") + "\n"
        return code_content

    def _is_rule_effective(self, rule: AdvancedRule) -> bool:
        """检查规则是否有效"""
        now = datetime.now()

        if rule.effective_from and now < datetime.fromisoformat(rule.effective_from):
            return False

        if rule.effective_to and now > datetime.fromisoformat(rule.effective_to):
            return False

        return True

    def _check_single_rule(
        self,
        rule: AdvancedRule,
        code_content: str,
        task_data: dict[str, Any],
        context: dict[str, Any],
    ) -> EnhancedRuleViolation | None:
        """
        检查单个规则是否被违反

        Args:
            rule: 规则
            code_content: 代码内容
            task_data: 任务数据
            context: 上下文信息

        Returns:
            违规记录
        """
        try:
            if rule.conditions:
                if not self._evaluate_advanced_conditions(rule, task_data, context):
                    return None

            if rule.pattern:
                matches = re.findall(rule.pattern, code_content, re.IGNORECASE)
                if matches:
                    return self._create_violation(rule, matches, code_content)

            if rule.condition:
                if self._evaluate_simple_condition(rule.condition, task_data):
                    return self._create_violation(rule, [], code_content)

        except Exception as e:
            logger.warning(f"Failed to check rule {rule.id}: {e}")

        return None

    def _evaluate_advanced_conditions(
        self, rule: AdvancedRule, task_data: dict[str, Any], context: dict[str, Any]
    ) -> bool:
        """评估高级条件"""
        if not rule.conditions:
            return True

        full_context = {**task_data, **context}

        if not rule.conditions.conditions:
            return True

        evaluator = ConditionEvaluator(full_context)
        results = []

        for cond in rule.conditions.conditions:
            if isinstance(cond, str):
                results.append(evaluator._evaluate_atomic(cond, full_context))
            else:
                results.append(evaluator.evaluate(cond, full_context))

        if rule.conditions.operator == OperatorType.AND:
            return all(results)
        elif rule.conditions.operator == OperatorType.OR:
            return any(results)
        else:
            return False

    def _evaluate_simple_condition(self, condition: str, task_data: dict[str, Any]) -> bool:
        """评估简单条件"""
        try:
            lines = len(task_data.get("code_content", "").splitlines())
            if condition == "lines > 100":
                return lines > 100
            return False
        except Exception as e:
            logger.warning(f"Failed to evaluate condition '{condition}': {e}")
            return False

    def _create_violation(
        self,
        rule: AdvancedRule,
        matches: list[str],
        code_content: str,
    ) -> EnhancedRuleViolation:
        """创建违规记录"""
        return EnhancedRuleViolation(
            rule_id=rule.id,
            rule_name=rule.name,
            severity=rule.severity,
            message=rule.message,
            evidence=[str(m) for m in matches[:5]],
            rule_weight=rule.weight,
            rule_priority=rule.priority,
            score=self._calculate_violation_score(rule),
            matched_patterns=matches,
            source_text=code_content,
        )

    def _calculate_violation_score(self, rule: AdvancedRule) -> float:
        """计算违规分数"""
        severity_scores = {
            "critical": 100.0,
            "high": 75.0,
            "medium": 50.0,
            "low": 25.0,
            "info": 10.0,
        }

        base_score = severity_scores.get(rule.severity.lower(), 50.0)
        priority_multiplier = min(rule.priority / 10.0, 2.0)
        weight_multiplier = rule.weight

        return min(base_score * priority_multiplier * weight_multiplier, 100.0)

    def _generate_evaluation(
        self, violations: list[EnhancedRuleViolation], task_data: dict[str, Any]
    ) -> RulesEvaluation:
        """
        生成评估报告

        Args:
            violations: 违规列表
            task_data: 任务数据

        Returns:
            评估结果
        """
        evaluation = RulesEvaluation()
        evaluation.violations = violations
        evaluation.rules_evaluated = len(self.get_all_rules())
        evaluation.rules_triggered = len(violations)

        severity_counts = {}
        category_scores = {}

        total_score = 100.0

        for violation in violations:
            total_score -= violation.score

            severity = violation.severity
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

            rule = self.get_rule(violation.rule_id)
            if rule:
                category = rule.category
                category_scores[category] = category_scores.get(category, 0) + violation.score

        evaluation.overall_score = max(0.0, total_score)
        evaluation.severity_distribution = severity_counts
        evaluation.category_scores = category_scores

        return evaluation


class RulesEngineFactory:
    """规则引擎工厂"""

    @staticmethod
    def create_enhanced() -> EnhancedRulesEngine:
        """创建增强版规则引擎实例"""
        return EnhancedRulesEngine()

    @staticmethod
    def create() -> BaseRulesEngine:
        """创建基础版规则引擎实例"""
        return BaseRulesEngine()
