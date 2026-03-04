from src.analyzer.labeling.models import (
    Label,
    LabelGenerationResult,
)
from src.rules.categories import FAULT_CATEGORIES


class TestLabelingModels:
    def test_label_creation(self):
        label = Label(
            name="测试标签",
            confidence=0.9,
            category="编码错误",
            description="这是一个测试标签",
        )
        assert label.name == "测试标签"
        assert label.confidence == 0.9
        assert label.category == "编码错误"
        assert label.description == "这是一个测试标签"

    def test_label_generation_result(self):
        label = Label(name="测试", confidence=0.8, category="测试")
        result = LabelGenerationResult(
            cluster_id=1,
            labels=[label],
            summary="测试总结",
            reasoning="测试推理",
        )
        assert result.cluster_id == 1
        assert len(result.labels) == 1
        assert result.summary == "测试总结"
        assert result.reasoning == "测试推理"

    def test_fault_categories(self):
        assert isinstance(FAULT_CATEGORIES, list)
        assert len(FAULT_CATEGORIES) > 0
        assert "需求环节" in FAULT_CATEGORIES
        assert "设计环节" in FAULT_CATEGORIES
