import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.core.models import StandardCategory, StandardRule


class TestStandardKnowledgeBase:
    """规范知识库管理器测试套件"""

    def test_load_java_coding_standards(self, standards_manager, sample_java_standards):
        """测试加载Java编码规范"""
        standards = standards_manager.load_category("java_coding")
        assert standards is not None
        assert standards.id == "java_coding"
        assert standards.name == "Java编码规范"
        assert len(standards.rules) >= 1

    def test_load_database_standards(self, standards_manager, sample_database_standards):
        """测试加载数据库规范"""
        standards = standards_manager.load_category("database_design")
        assert standards is not None
        assert standards.id == "database_design"
        assert standards.name == "数据库设计规范"

    def test_get_all_categories(self, standards_manager):
        """测试获取所有规范类别"""
        categories = standards_manager.get_all_categories()
        assert isinstance(categories, list)
        assert len(categories) >= 2

    def test_get_rule_by_id(self, standards_manager):
        """测试根据ID获取规则"""
        rule = standards_manager.get_rule("JAVA-001")
        assert rule is not None
        assert rule.id == "JAVA-001"
        assert "异常处理" in rule.subcategory

    def test_search_rules_by_keyword(self, standards_manager):
        """测试按关键字搜索规则"""
        rules = standards_manager.search_rules("异常")
        assert len(rules) > 0

    def test_search_rules_no_results(self, standards_manager):
        """测试搜索无结果"""
        rules = standards_manager.search_rules("不存在的规则关键字xyz123")
        assert len(rules) == 0

    def test_get_rules_by_level(self, standards_manager):
        """测试按级别获取规则"""
        mandatory_rules = standards_manager.get_rules_by_level("强制")
        assert len(mandatory_rules) > 0
        for rule in mandatory_rules:
            assert rule.level == "强制"

    def test_get_rules_by_category_and_subcategory(self, standards_manager):
        """测试按类别和子类别获取规则"""
        rules = standards_manager.get_rules_by_subcategory("java_coding", "异常处理")
        assert len(rules) > 0
        for rule in rules:
            assert rule.category == "java_coding"
            assert rule.subcategory == "异常处理"

    def test_validate_violation_rule_exists(self, standards_manager):
        """测试验证违规规则是否存在"""
        rule = standards_manager.get_rule("JAVA-001")
        assert rule is not None
        assert rule.title == "禁止捕获异常后不做任何处理"

    def test_get_rules_count(self, standards_manager):
        """测试获取规则总数"""
        count = standards_manager.get_total_rules_count()
        assert count >= 3

    def test_load_nonexistent_category(self, standards_manager):
        """测试加载不存在的类别"""
        standards = standards_manager.load_category("nonexistent_category")
        assert standards is None

    def test_rule_model_fields(self, standards_manager):
        """测试规则模型字段完整性"""
        rule = standards_manager.get_rule("JAVA-001")
        assert rule.id
        assert rule.category
        assert rule.subcategory
        assert rule.title
        assert rule.content
        assert rule.level
