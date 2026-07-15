import pytest

from src.analyzer.labeling.generator import LabelGenerator


class MockProvider:
    def __init__(self, response: str):
        self.response = response

    async def generate(self, system: str, user: str) -> str:  # noqa: ARG002
        return self.response


class MockProviderError:
    """A provider that raises an exception during generate()."""

    async def generate(self, system: str, user: str) -> str:  # noqa: ARG002
        raise RuntimeError("LLM provider connection failed")


class TestLabelGenerator:
    async def test_generate_labels(self):
        mock_response = """
        {
            "labels": [
                {"name": "编码错误", "confidence": 0.9, "category": "code", "description": "代码逻辑错误"}
            ],
            "summary": "这是一个测试故障",
            "reasoning": "通过分析代码发现..."
        }
        """
        provider = MockProvider(mock_response)
        generator = LabelGenerator(llm_provider=provider)

        task_data = {
            "task_id": 123,
            "title": "测试任务",
            "description": "这是一个测试任务描述",
            "status": "resolved",
            "priority": "high",
        }

        result = await generator.generate(task_data)

        assert result.cluster_id == 123
        assert len(result.labels) == 1
        assert result.labels[0].name == "编码错误"
        assert result.labels[0].confidence == 0.9

    async def test_generate_for_cluster(self):
        mock_response = """
        {
            "labels": [
                {"name": "性能问题", "confidence": 0.85, "category": "performance", "description": "性能瓶颈"}
            ],
            "summary": "聚类总结",
            "reasoning": "这些任务都有性能问题"
        }
        """
        provider = MockProvider(mock_response)
        generator = LabelGenerator(llm_provider=provider)

        tasks = [
            {"task_id": 1, "title": "任务1", "description": "描述1"},
            {"task_id": 2, "title": "任务2", "description": "描述2"},
        ]

        result = await generator.generate_for_cluster(tasks)

        assert result.summary == "聚类总结"
        assert result.reasoning == "这些任务都有性能问题"
        assert len(result.labels) >= 1

    def test_get_provider_raises_when_none(self):
        generator = LabelGenerator(llm_provider=None)
        with pytest.raises(RuntimeError, match="LLM provider not configured"):
            generator._get_provider()

    async def test_parse_response_invalid_json(self):
        generator = LabelGenerator(llm_provider=None)
        result = generator._parse_response(1, "invalid json")

        assert result.cluster_id == 1
        assert len(result.labels) == 0

    async def test_generate_without_segments(self):
        mock_response = """
        {
            "labels": [{"name": "测试", "confidence": 0.5, "category": "test", "description": ""}],
            "summary": "测试",
            "reasoning": "测试"
        }
        """
        provider = MockProvider(mock_response)
        generator = LabelGenerator(llm_provider=provider)

        task_data = {"task_id": 1, "title": "测试", "description": "描述"}
        result = await generator.generate(task_data)

        assert result.cluster_id == 1

    async def test_generate_provider_raises_exception(self):
        """Provider raises RuntimeError — exception should propagate (not caught)."""
        provider = MockProviderError()
        generator = LabelGenerator(llm_provider=provider)

        task_data = {"task_id": 123, "title": "测试", "description": "描述"}

        with pytest.raises(RuntimeError, match="LLM provider connection failed"):
            await generator.generate(task_data)

    async def test_generate_provider_returns_garbled_text(self):
        """Provider returns non-JSON text — _parse_response handles gracefully."""
        provider = MockProvider("This is not JSON at all, just some random text")
        generator = LabelGenerator(llm_provider=provider)

        task_data = {"task_id": 456, "title": "测试", "description": "描述"}
        result = await generator.generate(task_data)

        assert result.cluster_id == 456
        assert len(result.labels) == 0
        assert result.summary == ""
        assert "Failed to parse LLM response" in result.reasoning

    async def test_generate_provider_returns_json_missing_labels_key(self):
        """Provider returns valid JSON but without 'labels' key."""
        provider = MockProvider('{"summary": "ok", "reasoning": "fine"}')
        generator = LabelGenerator(llm_provider=provider)

        task_data = {"task_id": 789, "title": "测试", "description": "描述"}
        result = await generator.generate(task_data)

        assert result.cluster_id == 789
        assert len(result.labels) == 0
        assert result.summary == "ok"
        assert result.reasoning == "fine"

    async def test_generate_provider_returns_empty_string(self):
        """Provider returns empty string — _parse_response handles JSONDecodeError."""
        provider = MockProvider("")
        generator = LabelGenerator(llm_provider=provider)

        task_data = {"task_id": 999, "title": "测试", "description": "描述"}
        result = await generator.generate(task_data)

        assert result.cluster_id == 999
        assert len(result.labels) == 0
        assert result.summary == ""

    async def test_generate_for_cluster_empty_tasks_raises_value_error(self):
        """Empty task list should raise ValueError."""
        generator = LabelGenerator(llm_provider=MockProvider("{}"))

        with pytest.raises(ValueError, match="No tasks provided for cluster labeling"):
            await generator.generate_for_cluster([])
