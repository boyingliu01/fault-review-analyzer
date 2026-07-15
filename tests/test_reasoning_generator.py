import pytest

from src.analyzer.reasoning.generator import RootCauseAnalyzer


class MockReasoningProvider:
    def __init__(self, response: str):
        self.response = response

    async def generate(self, system: str, user: str) -> str:  # noqa: ARG002
        return self.response


class MockReasoningProviderError:
    """A provider that raises an exception during generate()."""

    async def generate(self, system: str, user: str) -> str:  # noqa: ARG002
        raise RuntimeError("LLM provider connection failed")


class TestRootCauseAnalyzer:
    async def test_analyze_root_cause(self):
        mock_response = """
        {
            "root_causes": [
                {
                    "cause_type": "编码错误",
                    "description": "代码逻辑错误",
                    "evidence": ["证据1"],
                    "confidence": 0.9
                }
            ],
            "analysis_summary": "分析总结",
            "technical_factors": ["代码问题"],
            "process_factors": ["测试不足"],
            "management_factors": ["资源不足"]
        }
        """
        provider = MockReasoningProvider(mock_response)
        analyzer = RootCauseAnalyzer(llm_provider=provider)

        task_data = {
            "task_id": 123,
            "title": "测试任务",
            "description": "测试描述",
            "status": "resolved",
            "priority": "high",
        }

        result = await analyzer.analyze(task_data)

        assert result.task_id == 123
        assert len(result.root_causes) == 1
        assert result.root_causes[0].cause_type == "编码错误"
        assert result.analysis_summary == "分析总结"

    async def test_analyze_batch(self):
        mock_response = """
        {
            "root_causes": [{"cause_type": "测试", "description": "测试", "evidence": [], "confidence": 0.5}],
            "analysis_summary": "测试",
            "technical_factors": [],
            "process_factors": [],
            "management_factors": []
        }
        """
        provider = MockReasoningProvider(mock_response)
        analyzer = RootCauseAnalyzer(llm_provider=provider)

        tasks = [
            {"task_id": 1, "title": "任务1", "description": "描述1"},
            {"task_id": 2, "title": "任务2", "description": "描述2"},
        ]

        results = await analyzer.analyze_batch(tasks)

        assert len(results) == 2
        assert results[0].task_id == 1
        assert results[1].task_id == 2

    def test_get_provider_raises_when_none(self):
        analyzer = RootCauseAnalyzer(llm_provider=None)
        with pytest.raises(RuntimeError, match="LLM provider not configured"):
            analyzer._get_provider()

    async def test_parse_response_invalid_json(self):
        analyzer = RootCauseAnalyzer(llm_provider=None)
        result = analyzer._parse_response(1, "invalid json")

        assert result.task_id == 1
        assert len(result.root_causes) == 0

    async def test_analyze_provider_raises_exception(self):
        """Provider raises RuntimeError — exception should propagate (not caught)."""
        provider = MockReasoningProviderError()
        analyzer = RootCauseAnalyzer(llm_provider=provider)

        task_data = {"task_id": 123, "title": "测试", "description": "描述"}

        with pytest.raises(RuntimeError, match="LLM provider connection failed"):
            await analyzer.analyze(task_data)

    async def test_analyze_provider_returns_garbled_text(self):
        """Provider returns non-JSON text — _parse_response handles gracefully."""
        provider = MockReasoningProvider("This is not JSON at all, just some random text")
        analyzer = RootCauseAnalyzer(llm_provider=provider)

        task_data = {"task_id": 456, "title": "测试", "description": "描述"}
        result = await analyzer.analyze(task_data)

        assert result.task_id == 456
        assert len(result.root_causes) == 0
        assert result.analysis_summary == ""
        assert result.technical_factors == []
        assert result.process_factors == []
        assert result.management_factors == []

    async def test_analyze_provider_returns_json_missing_root_causes_key(self):
        """Provider returns valid JSON but without 'root_causes' key."""
        provider = MockReasoningProvider('{"analysis_summary": "ok", "technical_factors": ["t1"]}')
        analyzer = RootCauseAnalyzer(llm_provider=provider)

        task_data = {"task_id": 789, "title": "测试", "description": "描述"}
        result = await analyzer.analyze(task_data)

        assert result.task_id == 789
        assert len(result.root_causes) == 0
        assert result.analysis_summary == "ok"
        assert result.technical_factors == ["t1"]

    async def test_analyze_provider_returns_empty_string(self):
        """Provider returns empty string — _parse_response handles JSONDecodeError."""
        provider = MockReasoningProvider("")
        analyzer = RootCauseAnalyzer(llm_provider=provider)

        task_data = {"task_id": 999, "title": "测试", "description": "描述"}
        result = await analyzer.analyze(task_data)

        assert result.task_id == 999
        assert len(result.root_causes) == 0
        assert result.analysis_summary == ""

    async def test_analyze_with_labels_context(self):
        """analyze() with labels list — label_context should be appended to user prompt."""
        mock_response = """
        {
            "root_causes": [
                {
                    "cause_type": "配置错误",
                    "description": "配置文件错误",
                    "evidence": ["日志显示配置缺失"],
                    "confidence": 0.95
                }
            ],
            "analysis_summary": "配置相关问题",
            "technical_factors": ["配置管理"],
            "process_factors": ["变更流程"],
            "management_factors": ["审批不足"]
        }
        """
        provider = MockReasoningProvider(mock_response)
        analyzer = RootCauseAnalyzer(llm_provider=provider)

        task_data = {"task_id": 100, "title": "服务异常", "description": "描述"}
        labels = [{"name": "配置错误", "confidence": 0.9, "category": "config"}]

        result = await analyzer.analyze(task_data, labels=labels)

        assert result.task_id == 100
        assert len(result.root_causes) == 1
        assert result.root_causes[0].cause_type == "配置错误"
        assert result.analysis_summary == "配置相关问题"
