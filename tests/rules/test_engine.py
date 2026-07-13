"""Tests for the rules engine."""

from typing import Any

import pytest

from src.rules.engine import Rule, RuleEngine, RuleResult, RuleSeverity, Violation


class TestViolation:
    """Tests for the Violation class."""

    def test_violation_creation(self):
        """Test creating a basic violation."""
        violation = Violation(
            rule_id="RULE001", message="Test violation message", location="file.py:42"
        )
        assert violation.rule_id == "RULE001"
        assert violation.message == "Test violation message"
        assert violation.location == "file.py:42"
        assert violation.context is None

    def test_violation_with_context(self):
        """Test creating a violation with context."""
        context = {"code": "x = y + z", "line_number": 42}
        violation = Violation(
            rule_id="RULE002",
            message="Variable not defined",
            location="file.py:42",
            context=context,
        )
        assert violation.context == context

    def test_violation_to_dict(self):
        """Test converting violation to dictionary."""
        violation = Violation(
            rule_id="RULE003",
            message="Test message",
            location="test.py:10",
            context={"key": "value"},
        )
        result = violation.to_dict()
        assert result["rule_id"] == "RULE003"
        assert result["message"] == "Test message"
        assert result["location"] == "test.py:10"
        assert result["context"] == {"key": "value"}


class TestRule:
    """Tests for the Rule class."""

    def test_rule_creation(self):
        """Test creating a basic rule."""

        def check_func(code: str, context: dict[str, Any]) -> list[Violation]:
            return []

        rule = Rule(
            id="TEST001",
            name="Test Rule",
            description="A test rule",
            severity=RuleSeverity.ERROR,
            check_function=check_func,
        )
        assert rule.id == "TEST001"
        assert rule.name == "Test Rule"
        assert rule.description == "A test rule"
        assert rule.severity == RuleSeverity.ERROR
        assert rule.enabled is True

    def test_rule_with_options(self):
        """Test creating a rule with custom options."""

        def check_func(code: str, context: dict[str, Any]) -> list[Violation]:
            return []

        rule = Rule(
            id="TEST002",
            name="Configurable Rule",
            description="A configurable test rule",
            severity=RuleSeverity.WARNING,
            check_function=check_func,
            enabled=False,
            options={"max_lines": 100, "ignore_patterns": ["*.test.py"]},
        )
        assert rule.enabled is False
        assert rule.options["max_lines"] == 100

    def test_rule_execute_with_violations(self):
        """Test executing a rule that finds violations."""

        def check_func(code: str, context: dict[str, Any]) -> list[Violation]:
            if "bad_keyword" in code:
                return [
                    Violation(rule_id="RULE001", message="Found bad keyword", location="test.py:1")
                ]
            return []

        rule = Rule(
            id="RULE001",
            name="Bad Keyword Rule",
            description="Detects bad keywords",
            severity=RuleSeverity.ERROR,
            check_function=check_func,
        )

        result = rule.execute("code with bad_keyword here", {})
        assert result.rule_id == "RULE001"
        assert result.passed is False
        assert len(result.violations) == 1
        assert result.violations[0].message == "Found bad keyword"

    def test_rule_execute_without_violations(self):
        """Test executing a rule that finds no violations."""

        def check_func(code: str, context: dict[str, Any]) -> list[Violation]:
            return []

        rule = Rule(
            id="RULE002",
            name="Clean Code Rule",
            description="Validates clean code",
            severity=RuleSeverity.INFO,
            check_function=check_func,
        )

        result = rule.execute("some clean code", {})
        assert result.passed is True
        assert len(result.violations) == 0
        assert result.execution_time_ms > 0


class TestRuleEngine:
    """Tests for the RuleEngine class."""

    @pytest.fixture
    def sample_rules(self):
        """Create sample rules for testing."""

        def check_bad_keyword(code: str, context: dict[str, Any]) -> list[Violation]:
            if "bad" in code.lower():
                return [Violation(rule_id="R001", message="Found 'bad'", location="line:1")]
            return []

        def check_todo(code: str, context: dict[str, Any]) -> list[Violation]:
            if "TODO" in code:
                return [Violation(rule_id="R002", message="Found TODO", location="line:1")]
            return []

        rule1 = Rule(
            id="R001",
            name="No Bad Words",
            description="Checks for bad words",
            severity=RuleSeverity.ERROR,
            check_function=check_bad_keyword,
        )

        rule2 = Rule(
            id="R002",
            name="TODO Finder",
            description="Finds TODO comments",
            severity=RuleSeverity.WARNING,
            check_function=check_todo,
        )

        return [rule1, rule2]

    def test_engine_creation(self):
        """Test creating a rule engine."""
        engine = RuleEngine()
        assert len(engine.rules) == 0
        assert engine.config == {}

    def test_engine_with_config(self):
        """Test creating a rule engine with config."""
        config = {"max_violations": 10, "stop_on_error": True}
        engine = RuleEngine(config=config)
        assert engine.config["max_violations"] == 10

    def test_register_rule(self, sample_rules):
        """Test registering a rule."""
        engine = RuleEngine()
        engine.register_rule(sample_rules[0])
        assert len(engine.rules) == 1
        assert engine.rules[0].id == "R001"

    def test_register_multiple_rules(self, sample_rules):
        """Test registering multiple rules."""
        engine = RuleEngine()
        for rule in sample_rules:
            engine.register_rule(rule)
        assert len(engine.rules) == 2

    def test_unregister_rule(self, sample_rules):
        """Test unregistering a rule."""
        engine = RuleEngine()
        engine.register_rule(sample_rules[0])
        engine.register_rule(sample_rules[1])

        engine.unregister_rule("R001")
        assert len(engine.rules) == 1
        assert engine.rules[0].id == "R002"

    def test_unregister_nonexistent_rule(self, sample_rules):
        """Test unregistering a rule that doesn't exist."""
        engine = RuleEngine()
        engine.register_rule(sample_rules[0])

        # Should not raise error
        engine.unregister_rule("NONEXISTENT")
        assert len(engine.rules) == 1

    def test_run_all_passed(self, sample_rules):
        """Test running rules with no violations."""
        engine = RuleEngine()
        for rule in sample_rules:
            engine.register_rule(rule)

        result = engine.run_all("clean code without issues")
        assert result.total_rules == 2
        assert result.passed_rules == 2
        assert result.failed_rules == 0
        assert result.total_violations == 0
        assert result.success is True

    def test_run_all_with_violations(self, sample_rules):
        """Test running rules with violations."""
        engine = RuleEngine()
        for rule in sample_rules:
            engine.register_rule(rule)

        result = engine.run_all("bad code with TODO")
        assert result.total_rules == 2
        assert result.passed_rules == 0
        assert result.failed_rules == 2
        assert result.total_violations == 2
        assert result.success is False

    def test_run_all_partial_failure(self, sample_rules):
        """Test running rules with partial failures."""
        engine = RuleEngine()
        for rule in sample_rules:
            engine.register_rule(rule)

        # Only triggers R002 (TODO), not R001 (bad)
        result = engine.run_all("clean code with TODO")
        assert result.total_rules == 2
        assert result.passed_rules == 1
        assert result.failed_rules == 1
        assert result.total_violations == 1

    def test_get_rule(self, sample_rules):
        """Test getting a rule by ID."""
        engine = RuleEngine()
        engine.register_rule(sample_rules[0])

        rule = engine.get_rule("R001")
        assert rule is not None
        assert rule.id == "R001"

        nonexistent = engine.get_rule("NONEXISTENT")
        assert nonexistent is None

    def test_clear_rules(self, sample_rules):
        """Test clearing all rules."""
        engine = RuleEngine()
        for rule in sample_rules:
            engine.register_rule(rule)

        assert len(engine.rules) == 2
        engine.clear_rules()
        assert len(engine.rules) == 0

    def test_run_all_empty_engine(self):
        """Test running with no rules registered."""
        engine = RuleEngine()
        result = engine.run_all("some code")

        assert result.total_rules == 0
        assert result.passed_rules == 0
        assert result.failed_rules == 0
        assert result.total_violations == 0
        assert result.success is True  # No rules to fail

    def test_run_all_exception_in_rule(self):
        """Test handling exceptions during rule execution."""

        def failing_check(code: str, context: dict[str, Any]) -> list[Violation]:
            raise ValueError("Simulated rule failure")

        failing_rule = Rule(
            id="FAIL001",
            name="Failing Rule",
            description="A rule that fails",
            severity=RuleSeverity.ERROR,
            check_function=failing_check,
        )

        engine = RuleEngine()
        engine.register_rule(failing_rule)

        # Should not raise, but mark as failed
        result = engine.run_all("some code")
        assert result.total_rules == 1
        assert result.failed_rules == 1
        assert result.success is False


class TestRuleSeverity:
    """Tests for RuleSeverity enum."""

    def test_severity_values(self):
        """Test severity enum values."""
        assert RuleSeverity.INFO.value == "info"
        assert RuleSeverity.WARNING.value == "warning"
        assert RuleSeverity.ERROR.value == "error"
        assert RuleSeverity.CRITICAL.value == "critical"

    def test_severity_comparison(self):
        """Test severity level comparison."""
        # Lower value = lower severity
        assert RuleSeverity.INFO < RuleSeverity.WARNING
        assert RuleSeverity.WARNING < RuleSeverity.ERROR
        assert RuleSeverity.ERROR < RuleSeverity.CRITICAL


class TestRuleResult:
    """Tests for RuleResult class."""

    def test_result_creation(self):
        """Test creating a rule result."""
        violations = [
            Violation("R001", "Error 1", "line:1"),
            Violation("R001", "Error 2", "line:2"),
        ]
        result = RuleResult(
            rule_id="R001", passed=False, violations=violations, execution_time_ms=10.5
        )

        assert result.rule_id == "R001"
        assert result.passed is False
        assert len(result.violations) == 2
        assert result.execution_time_ms == 10.5

    def test_result_success(self):
        """Test a successful result."""
        result = RuleResult(rule_id="R002", passed=True, violations=[], execution_time_ms=5.0)

        assert result.passed is True
        assert len(result.violations) == 0


class TestEngineConfig:
    """Tests for engine configuration."""

    def test_default_config(self):
        """Test default engine configuration."""
        engine = RuleEngine()
        assert engine.config == {}

    def test_custom_config(self):
        """Test engine with custom config."""
        config = {"max_violations": 100, "stop_on_error": True, "parallel_execution": False}
        engine = RuleEngine(config=config)
        assert engine.config["max_violations"] == 100
        assert engine.config["stop_on_error"] is True
