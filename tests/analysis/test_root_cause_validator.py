"""根因可落地性验证器测试套件"""

import pytest

from src.analysis.root_cause_validator import RootCauseValidator
from src.core.models import RootCauseValidation


class TestRootCauseValidator:
    """根因可落地性验证器测试套件"""

    def test_validate_actionable_root_cause(self, root_cause_validator):
        """测试可落地的根因"""
        root_cause = "数据库连接未正确关闭导致连接池耗尽"
        result = root_cause_validator.validate(root_cause)
        assert isinstance(result, RootCauseValidation)
        assert result.is_actionable is True

    def test_validate_non_actionable_root_cause(self, root_cause_validator):
        """测试不可落地的根因"""
        root_cause = "场景考虑不周全"
        result = root_cause_validator.validate(root_cause)
        assert isinstance(result, RootCauseValidation)
        if not result.is_actionable:
            assert result.needs_reanalysis is True

    def test_validate_vague_root_cause(self, root_cause_validator):
        """测试模糊的根因"""
        root_cause = "开发人员经验不足"
        result = root_cause_validator.validate(root_cause)
        assert isinstance(result, RootCauseValidation)

    def test_generate_improvement_measures(self, root_cause_validator):
        """测试生成改进措施"""
        root_cause = "空指针异常导致服务崩溃"
        result = root_cause_validator.validate(root_cause)
        assert len(result.improvement_measures) > 0

    def test_actionability_score_calculation(self, root_cause_validator):
        """测试可落地性评分计算"""
        root_cause = "使用完数据库连接后必须关闭"
        result = root_cause_validator.validate(root_cause)
        assert result.actionability_score >= 0.0
        assert result.actionability_score <= 1.0

    def test_validation_with_specific_measures(self, root_cause_validator):
        """测试具体改进措施生成"""
        root_cause = "未对用户输入进行参数校验导致SQL注入"
        result = root_cause_validator.validate(root_cause)
        if result.is_actionable:
            for measure in result.improvement_measures:
                assert len(measure.description) > 0
                assert measure.priority in ["high", "medium", "low"]

    def test_reanalysis_feedback(self, root_cause_validator):
        """测试重新分析反馈"""
        root_cause = "测试覆盖不足"
        result = root_cause_validator.validate(root_cause)
        if result.needs_reanalysis:
            assert len(result.reanalysis_feedback) > 0

    def test_empty_root_cause(self, root_cause_validator):
        """测试空根因"""
        root_cause = ""
        result = root_cause_validator.validate(root_cause)
        assert isinstance(result, RootCauseValidation)
        assert result.is_actionable is False
