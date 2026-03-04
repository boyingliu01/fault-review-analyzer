from src.analyzer.reasoning.models import (
    CAUSE_TYPES,
    RootCause,
    RootCauseAnalysisResult,
)


class TestReasoningModels:
    def test_root_cause_creation(self):
        cause = RootCause(
            cause_type="编码错误",
            description="代码逻辑错误导致",
            evidence=["证据1", "证据2"],
            confidence=0.85,
        )
        assert cause.cause_type == "编码错误"
        assert cause.description == "代码逻辑错误导致"
        assert len(cause.evidence) == 2
        assert cause.confidence == 0.85

    def test_root_cause_analysis_result(self):
        cause = RootCause(cause_type="测试", description="测试", confidence=0.5)
        result = RootCauseAnalysisResult(
            task_id=1,
            root_causes=[cause],
            analysis_summary="测试总结",
            technical_factors=["因素1"],
            process_factors=["因素2"],
            management_factors=["因素3"],
        )
        assert result.task_id == 1
        assert len(result.root_causes) == 1
        assert result.analysis_summary == "测试总结"
        assert len(result.technical_factors) == 1

    def test_cause_types(self):
        assert isinstance(CAUSE_TYPES, list)
        assert len(CAUSE_TYPES) > 0
        assert "编码错误" in CAUSE_TYPES
        assert "设计缺陷" in CAUSE_TYPES
