"""增强LLM分析器测试套件"""

from src.core.models import (
    LLMAnalysisResult,
)


class TestEnhancedLLMAnalyzer:
    """增强LLM分析器测试套件"""

    def test_analyze_with_full_flow(
        self,
        enhanced_llm_analyzer,
        sample_fault_info,
        mock_llm_provider,
    ):
        """测试完整分析流程"""
        result = enhanced_llm_analyzer.analyze(
            sample_fault_info,
            llm_provider=mock_llm_provider,
        )
        assert isinstance(result, LLMAnalysisResult)
        assert result.task_id == "TASK-001"

    def test_analyze_without_llm(
        self,
        enhanced_llm_analyzer,
        sample_fault_info,
    ):
        """测试不使用LLM的分析"""
        result = enhanced_llm_analyzer.analyze(sample_fault_info)
        assert isinstance(result, LLMAnalysisResult)

    def test_violation_detection_integration(
        self,
        enhanced_llm_analyzer,
        sample_fault_info,
    ):
        """测试违规检测集成"""
        result = enhanced_llm_analyzer.analyze(sample_fault_info)
        assert result.violation_detection is not None

    def test_root_cause_validation_integration(
        self,
        enhanced_llm_analyzer,
        sample_fault_info,
    ):
        """测试根因验证集成"""
        result = enhanced_llm_analyzer.analyze(sample_fault_info)
        assert result.root_cause_validation is not None

    def test_code_change_integration(
        self,
        enhanced_llm_analyzer,
        sample_fault_info_with_code,
    ):
        """测试代码变更集成"""
        result = enhanced_llm_analyzer.analyze(sample_fault_info_with_code)
        assert isinstance(result.code_changes, list)

    def test_improvement_measures_generation(
        self,
        enhanced_llm_analyzer,
        sample_fault_info,
    ):
        """测试改进措施生成"""
        result = enhanced_llm_analyzer.analyze(sample_fault_info)
        if result.root_cause_validation.is_actionable:
            assert len(result.root_cause_validation.improvement_measures) > 0

    def test_analysis_with_empty_code(
        self,
        enhanced_llm_analyzer,
    ):
        """测试空代码分析"""
        fault_info = {
            "task_id": "TASK-EMPTY",
            "title": "测试",
            "description": "测试描述",
            "code_snippet": "",
            "development": {"commits": []},
        }
        result = enhanced_llm_analyzer.analyze(fault_info)
        assert result.task_id == "TASK-EMPTY"

    def test_non_actionable_root_cause_handling(
        self,
        enhanced_llm_analyzer,
    ):
        """测试不可落地根因处理"""
        fault_info = {
            "task_id": "TASK-002",
            "title": "场景考虑不足",
            "description": "业务场景考虑不周全",
            "code_snippet": "int a = 1;",
            "root_cause": "场景考虑不足",
            "development": {"commits": []},
        }
        result = enhanced_llm_analyzer.analyze(fault_info)
        assert result.root_cause_validation.needs_reanalysis is True
