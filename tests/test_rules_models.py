from src.rules.models import Rule, RuleCheckResult, RulesConfig, RuleViolation


class TestRulesModels:
    def test_rule_creation(self):
        rule = Rule(
            id="test-001",
            name="测试规则",
            description="这是一个测试规则",
            category="test",
            severity="medium",
            pattern=r"test.*pattern",
            message="发现测试模式",
        )
        assert rule.id == "test-001"
        assert rule.name == "测试规则"
        assert rule.severity == "medium"
        assert rule.enabled is True

    def test_rule_violation(self):
        violation = RuleViolation(
            rule_id="test-001",
            rule_name="测试规则",
            severity="high",
            message="发现违规",
            evidence=["证据1", "证据2"],
            location="src/test.py:10",
        )
        assert violation.rule_id == "test-001"
        assert violation.severity == "high"
        assert len(violation.evidence) == 2

    def test_rule_check_result(self):
        violation = RuleViolation(
            rule_id="test-001",
            rule_name="测试规则",
            severity="medium",
            message="违规信息",
        )
        result = RuleCheckResult(
            task_id=1,
            violations=[violation],
            passed=False,
            summary="发现1个违规",
        )
        assert result.task_id == 1
        assert len(result.violations) == 1
        assert result.passed is False

    def test_rules_config(self):
        config = RulesConfig(
            builtin_enabled=True,
            custom_path="./custom/rules/",
            cache_enabled=True,
        )
        assert config.builtin_enabled is True
        assert config.custom_path == "./custom/rules/"
