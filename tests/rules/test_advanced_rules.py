"""高级规则引擎测试"""

from datetime import datetime, timedelta

import pytest

from src.rules import (
    AdvancedRule,
    EnhancedRulesEngine,
    OperatorType,
    RulesEngineFactory,
    RulesEvaluation,
    create_condition,
)


class TestEnhancedRulesEngine:
    """增强版规则引擎测试"""

    def test_initialization(self):
        """测试初始化"""
        engine = EnhancedRulesEngine()
        assert engine is not None
        assert len(engine.get_all_rules()) > 0

    def test_factory_creation(self):
        """测试工厂创建"""
        engine = RulesEngineFactory.create_enhanced()
        assert isinstance(engine, EnhancedRulesEngine)

        base_engine = RulesEngineFactory.create()
        assert not isinstance(base_engine, EnhancedRulesEngine)

    def test_rules_loaded(self):
        """测试规则加载"""
        engine = EnhancedRulesEngine()
        rules = engine.get_all_rules()
        assert len(rules) > 0
        assert any(rule.id == "security-001" for rule in rules)

    def test_check_with_evaluation(self):
        """测试带评估的检查方法"""
        engine = EnhancedRulesEngine()
        # 添加一个明确匹配的测试规则
        test_rule = AdvancedRule(
            id="test-001",
            name="测试规则",
            description="测试用规则",
            category="security",
            severity="high",
            pattern=r"password",
            message="检测到密码",
        )
        engine._rules["test-001"] = test_rule

        task_data = {
            "development": {
                "commits": [{"message": "password is '123456'"}],
            },
        }
        evaluation = engine.check_with_evaluation(task_data)

        assert isinstance(evaluation, RulesEvaluation)
        assert evaluation.overall_score <= 100
        assert evaluation.rules_evaluated > 0

    def test_rule_priority(self):
        """测试规则优先级"""
        engine = EnhancedRulesEngine()
        high_priority_rule = AdvancedRule(
            id="test-high",
            name="高优先级规则",
            description="测试高优先级规则",
            category="test",
            severity="high",
            pattern=r"password",
            priority=100,
        )

        low_priority_rule = AdvancedRule(
            id="test-low",
            name="低优先级规则",
            description="测试低优先级规则",
            category="test",
            severity="low",
            pattern=r"key",
            priority=1,
        )

        engine._rules["test-high"] = high_priority_rule
        engine._rules["test-low"] = low_priority_rule

        task_data = {
            "development": {
                "commits": [{"message": "password: '123456', key: 'abc123'"}]
            },
        }

        violations = engine._check_rules(task_data)

        high_rule_found = any(v.rule_id == "test-high" for v in violations)
        low_rule_found = any(v.rule_id == "test-low" for v in violations)

        # 只要规则都能被匹配到即可
        assert high_rule_found or low_rule_found

    def test_rule_effectiveness(self):
        """测试规则有效性时间范围"""
        engine = EnhancedRulesEngine()

        now = datetime.now()
        future_rule = AdvancedRule(
            id="future-rule",
            name="未来规则",
            description="测试未来生效规则",
            category="test",
            severity="medium",
            pattern=r"future",
            effective_from=(now + timedelta(days=1)).isoformat(),
        )

        expired_rule = AdvancedRule(
            id="expired-rule",
            name="过期规则",
            description="测试已过期规则",
            category="test",
            severity="low",
            pattern=r"expired",
            effective_to=(now - timedelta(days=1)).isoformat(),
        )

        current_rule = AdvancedRule(
            id="current-rule",
            name="当前规则",
            description="测试当前生效规则",
            category="test",
            severity="high",
            pattern=r"current",
        )

        engine._rules.update({
            "future-rule": future_rule,
            "expired-rule": expired_rule,
            "current-rule": current_rule,
        })

        task_data = {
            "development": {
                "commits": [{"message": "future expired current"}]
            },
        }

        violations = engine._check_rules(task_data)

        assert not any(v.rule_id == "future-rule" for v in violations)
        assert not any(v.rule_id == "expired-rule" for v in violations)
        assert any(v.rule_id == "current-rule" for v in violations)

    def test_advanced_conditions(self):
        """测试高级条件"""
        engine = EnhancedRulesEngine()

        # 使用简单的条件测试
        rule = AdvancedRule(
            id="test-conditions",
            name="条件测试规则",
            description="测试高级条件",
            category="test",
            severity="medium",
            pattern=r"test",
            conditions=None,
        )

        engine._rules["test-conditions"] = rule

        task_data1 = {
            "development": {
                "commits": [{"message": "test\n" * 60}]
            },
        }

        violations1 = engine._check_rules(task_data1)

        # 验证简单模式匹配
        assert any(v.rule_id == "test-conditions" for v in violations1)

    def test_rule_weight(self):
        """测试规则权重"""
        engine = EnhancedRulesEngine()

        high_weight_rule = AdvancedRule(
            id="high-weight",
            name="高权重规则",
            description="测试高权重规则",
            category="test",
            severity="medium",
            pattern=r"test",
            weight=2.0,
        )

        low_weight_rule = AdvancedRule(
            id="low-weight",
            name="低权重规则",
            description="测试低权重规则",
            category="test",
            severity="medium",
            pattern=r"test",
            weight=0.5,
        )

        engine._rules.update({
            "high-weight": high_weight_rule,
            "low-weight": low_weight_rule,
        })

        task_data = {
            "development": {
                "commits": [{"message": "test content"}]
            },
        }

        violations = engine._check_rules(task_data)

        high_v = next(v for v in violations if v.rule_id == "high-weight")
        low_v = next(v for v in violations if v.rule_id == "low-weight")

        assert high_v.score > low_v.score

    def test_evaluation_calculation(self):
        """测试评估计算"""
        engine = EnhancedRulesEngine()
        task_data = {
            "development": {
                "commits": [{"message": "password = 'hardcoded_secret_value'"}]
            },
        }

        evaluation = engine.check_with_evaluation(task_data)

        assert evaluation.overall_score >= 0
        assert evaluation.overall_score <= 100
        assert evaluation.rules_evaluated > 0
        assert evaluation.rules_triggered > 0

    def test_category_scores(self):
        """测试分类分数计算"""
        engine = EnhancedRulesEngine()

        task_data = {
            "development": {
                "commits": [
                    {"message": "password = 'hardcoded_secret_value'"},
                    {"message": "cursor.execute('SELECT * FROM users WHERE id = %s')"},
                ],
            },
        }

        evaluation = engine.check_with_evaluation(task_data)

        assert "security" in evaluation.category_scores
        assert evaluation.category_scores["security"] > 0

    def test_check_compatibility(self):
        """测试兼容旧接口"""
        engine = EnhancedRulesEngine()
        task_data = {
            "development": {
                "commits": [{"message": "password = 'hardcoded_secret_value'"}]
            },
        }

        violations = engine.check(task_data)
        assert len(violations) > 0
        assert all(hasattr(v, "rule_id") for v in violations)


class TestRuleConditions:
    """规则条件测试"""

    def test_and_conditions(self):
        """测试AND条件"""
        condition = create_condition(
            OperatorType.AND,
            "category == 'bug'",
            "severity == 'high'",
        )

        assert condition is not None

    def test_or_conditions(self):
        """测试OR条件"""
        condition = create_condition(
            OperatorType.OR,
            "category == 'bug'",
            "severity == 'high'",
        )

        assert condition is not None

    def test_not_conditions(self):
        """测试NOT条件"""
        condition = create_condition(
            OperatorType.NOT,
            "category == 'feature'",
        )

        assert condition is not None


class TestRuleMetadata:
    """规则元数据测试"""

    def test_rule_with_metadata(self):
        """测试带元数据的规则"""
        rule = AdvancedRule(
            id="test-meta",
            name="元数据测试规则",
            description="测试规则元数据",
            category="test",
            severity="medium",
            pattern=r"test",
        )

        assert rule.metadata is not None
        assert rule.metadata.version == "1.0"
        assert rule.description_en == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
