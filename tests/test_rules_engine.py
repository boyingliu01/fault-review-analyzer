import json
import tempfile
from pathlib import Path

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
        count = engine.load_custom_rules(Path("/nonexistent/path"))
        assert count == 0

    def test_load_custom_rules_from_yaml(self):
        engine = RulesEngine()
        with tempfile.TemporaryDirectory() as tmpdir:
            yaml_path = Path(tmpdir) / "custom_rules.yaml"
            yaml_content = """
rules:
  - id: custom-001
    name: 自定义规则
    description: 测试自定义规则
    category: custom
    severity: medium
    pattern: test_pattern
    message: 发现测试模式
"""
            yaml_path.write_text(yaml_content, encoding="utf-8")
            count = engine.load_custom_rules(Path(tmpdir))
            assert count == 1
            rule = engine.get_rule("custom-001")
            assert rule is not None
            assert rule.name == "自定义规则"

    def test_load_custom_rules_from_json(self):
        engine = RulesEngine()
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "custom_rules.json"
            json_content = {
                "rules": [
                    {
                        "id": "custom-002",
                        "name": "JSON自定义规则",
                        "description": "测试JSON自定义规则",
                        "category": "custom",
                        "severity": "high",
                        "pattern": "json_pattern",
                        "message": "发现JSON模式",
                    }
                ]
            }
            json_path.write_text(json.dumps(json_content), encoding="utf-8")
            count = engine.load_custom_rules(Path(tmpdir))
            assert count == 1
            rule = engine.get_rule("custom-002")
            assert rule is not None
            assert rule.name == "JSON自定义规则"

    def test_load_custom_rules_empty_yaml(self):
        engine = RulesEngine()
        with tempfile.TemporaryDirectory() as tmpdir:
            yaml_path = Path(tmpdir) / "empty.yaml"
            yaml_path.write_text("", encoding="utf-8")
            count = engine.load_custom_rules(Path(tmpdir))
            assert count == 0

    def test_load_custom_rules_no_rules_key(self):
        engine = RulesEngine()
        with tempfile.TemporaryDirectory() as tmpdir:
            yaml_path = Path(tmpdir) / "no_rules.yaml"
            yaml_path.write_text("other_key: value", encoding="utf-8")
            count = engine.load_custom_rules(Path(tmpdir))
            assert count == 0

    def test_check_with_requirement_info(self):
        engine = RulesEngine()
        task_data = {
            "title": "测试任务",
            "requirement": {
                "description": "需求描述",
            },
        }
        violations = engine.check(task_data)
        assert isinstance(violations, list)

    def test_check_with_design_info(self):
        engine = RulesEngine()
        task_data = {
            "title": "测试任务",
            "design": {
                "design_document": "设计文档",
            },
        }
        violations = engine.check(task_data)
        assert isinstance(violations, list)

    def test_check_with_testing_info(self):
        engine = RulesEngine()
        task_data = {
            "title": "测试任务",
            "testing": {
                "test_cases": ["测试用例1"],
            },
        }
        violations = engine.check(task_data)
        assert isinstance(violations, list)

    def test_check_with_code_review_info(self):
        engine = RulesEngine()
        task_data = {
            "title": "测试任务",
            "development": {"code_reviews": [{"comments": ["评审意见"], "approved": True}]},
        }
        violations = engine.check(task_data)
        assert isinstance(violations, list)

    def test_check_with_production_info(self):
        engine = RulesEngine()
        task_data = {
            "title": "测试任务",
            "production": {
                "symptoms": "故障现象",
                "logs": ["日志内容"],
            },
        }
        violations = engine.check(task_data)
        assert isinstance(violations, list)
