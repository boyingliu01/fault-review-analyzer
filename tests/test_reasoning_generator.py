import pytest
from src.analyzer.reasoning.generator import RootCauseAnalyzer


class MockReasoningProvider:
    def __init__(self, response: str):
        self.response = response

    async def generate(self, system: str, user: str) -> str:
        return self.response


class TestRootCauseAnalyzer:
    @pytest.mark.asyncio
    async def test_analyze_root_cause(self):
        mock_response = '''
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
        '''
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

    @pytest.mark.asyncio
    async def test_analyze_batch(self):
        mock_response = '''
        {
            "root_causes": [{"cause_type": "测试", "description": "测试", "evidence": [], "confidence": 0.5}],
            "analysis_summary": "测试",
            "technical_factors": [],
            "process_factors": [],
            "management_factors": []
        }
        '''
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

    @pytest.mark.asyncio
    async def test_parse_response_invalid_json(self):
        analyzer = RootCauseAnalyzer(llm_provider=None)
        result = analyzer._parse_response(1, "invalid json")

        assert result.task_id == 1
        assert len(result.root_causes) == 0
