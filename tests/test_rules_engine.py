import pytest
from src.rules.engine import RulesEngine


class TestRulesEngine:
    def test_engine_initialization(self):
        engine = RulesEngine()
        rules = engine.get_all_rules()
        assert len(rules) > 0

    def test_get_rule_by_id(self):
        engine = RulesEngine()
        rule = engine.get_rule("security-001")
        assert rule is not None
        assert rule.name == "敏感信息泄露"

    def test_get_rules_by_category(self):
        engine = RulesEngine()
        rules = engine.get_rules_by_category("security")
        assert len(rules) > 0
        for rule in rules:
            assert rule.category == "security"

    def test_check_no_violations(self):
        engine = RulesEngine()
        task_data = {
            "title": "测试任务",
            "description": "这是一个正常的任务",
        }
        violations = engine.check(task_data)
        assert isinstance(violations, list)

    def test_check_with_development_info(self):
        engine = RulesEngine()
        task_data = {
            "title": "测试任务",
            "description": "正常任务",
            "development": {
                "commits": [
                    {"message": "Normal commit"},
                ]
            },
        }
        violations = engine.check(task_data)
        assert isinstance(violations, list)

    def test_check_security_violation(self):
        engine = RulesEngine()
        task_data = {
            "title": "测试",
            "development": {
                "commits": [
                    {"message": "password='secret'"},
                ]
            },
        }
        violations = engine.check(task_data)
        assert len(violations) > 0
        assert violations[0].severity == "critical"

    def test_load_custom_rules_nonexistent(self):
        engine = RulesEngine()
        from pathlib import Path
        count = engine.load_custom_rules(Path("/nonexistent/path"))
        assert count == 0
