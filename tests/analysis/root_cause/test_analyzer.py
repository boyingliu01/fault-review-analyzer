"""Tests for root cause analyzer"""

import pytest

from src.analysis.root_cause.analyzer import RootCauseAnalyzer
from src.analysis.root_cause.models import (
    ActionableImprovement,
    ExistingFaultAnalysis,
    FaultAnalysisInput,
    RequirementContext,
    RootCause,
)


class MockLLMClient:
    """Mock LLM client for testing."""

    def __init__(self, response: str) -> None:
        self.response = response

    async def generate(self, prompt: str) -> str:  # noqa: ARG002
        return self.response


class TestRootCauseAnalyzer:
    """Test suite for RootCauseAnalyzer."""

    @pytest.fixture
    def mock_llm_client(self):
        """Create a mock LLM client with valid response."""
        client = MockLLMClient(
            response="{"
            '"problemCategory": "开发引入",'
            '"initialCause": "正常场景遗漏",'
            '"deepRootCauses": ['
            "{"
            '"layer": "测试层面",'
            '"rootCause": "缺少状态转换路径测试",'
            '"whyReason": "测试用例只覆盖正向流程",'
            '"evidence": "现有测试用例缺少逆向操作场景"'
            "}"
            "],"
            '"actionableImprovements": ['
            "{"
            '"type": "直接改进",'
            '"action": "补充测试用例覆盖逆向操作",'
            '"owner": "测试",'
            '"priority": "高"'
            "}"
            "],"
            '"checklistRecommendations": ['
            '"测试用例设计增加逆向路径覆盖"'
            "]"
            "}"
        )
        return client

    @pytest.fixture
    def fault_input(self):
        """Create sample fault analysis input."""
        return FaultAnalysisInput(
            task_no="11745664",
            title="复装业务卡类型切换问题",
            description="复装选择virtual eSIM卡后切换卡类型报错",
            task_src="BUG_ON_SITE",
            created_date="2025-12-24",
            finish_date="2025-12-30",
            product_module_id=35035,
            product_version_id=20603,
        )

    @pytest.fixture
    def existing_analysis(self):
        """Create sample existing fault analysis."""
        return ExistingFaultAnalysis(
            dev_catalog="研发环节",
            dev_catalog_detail="正常场景遗漏",
            dev_reason="没有将内存中的ResOrder数据置失效",
            dev_conclusion="代码逻辑不完善",
            dev_improve_stage="补充逆向场景测试",
            test_catalog="测试环节",
            test_catalog_detail="关联场景考虑不全",
            test_reason="测试用例覆盖不足",
            test_conclusion="需补充边界测试",
            test_improve_stage="增加测试用例覆盖",
        )

    @pytest.mark.asyncio
    async def test_analyze_returns_correct_problem_category(
        self, mock_llm_client, fault_input, existing_analysis
    ):
        """Test that analyze returns correct problem category."""
        analyzer = RootCauseAnalyzer(mock_llm_client)
        result = await analyzer.analyze(fault_input, existing_analysis)

        assert result.problem_category == "开发引入"

    @pytest.mark.asyncio
    async def test_analyze_returns_initial_cause(
        self, mock_llm_client, fault_input, existing_analysis
    ):
        """Test that analyze returns initial cause."""
        analyzer = RootCauseAnalyzer(mock_llm_client)
        result = await analyzer.analyze(fault_input, existing_analysis)

        assert result.initial_cause == "正常场景遗漏"

    @pytest.mark.asyncio
    async def test_analyze_returns_deep_root_causes(
        self, mock_llm_client, fault_input, existing_analysis
    ):
        """Test that analyze returns deep root causes."""
        analyzer = RootCauseAnalyzer(mock_llm_client)
        result = await analyzer.analyze(fault_input, existing_analysis)

        assert len(result.deep_root_causes) == 1
        assert result.deep_root_causes[0].layer == "测试层面"
        assert result.deep_root_causes[0].root_cause == "缺少状态转换路径测试"

    @pytest.mark.asyncio
    async def test_analyze_returns_actionable_improvements(
        self, mock_llm_client, fault_input, existing_analysis
    ):
        """Test that analyze returns actionable improvements."""
        analyzer = RootCauseAnalyzer(mock_llm_client)
        result = await analyzer.analyze(fault_input, existing_analysis)

        assert len(result.actionable_improvements) == 1
        assert result.actionable_improvements[0].type == "直接改进"
        assert result.actionable_improvements[0].priority == "高"

    @pytest.mark.asyncio
    async def test_analyze_returns_checklist_recommendations(
        self, mock_llm_client, fault_input, existing_analysis
    ):
        """Test that analyze returns checklist recommendations."""
        analyzer = RootCauseAnalyzer(mock_llm_client)
        result = await analyzer.analyze(fault_input, existing_analysis)

        assert len(result.checklist_recommendations) == 1
        assert "逆向路径" in result.checklist_recommendations[0]

    @pytest.mark.asyncio
    async def test_analyze_with_empty_existing_analysis(self, mock_llm_client, fault_input):
        """Test analyze with empty existing analysis."""
        empty_analysis = ExistingFaultAnalysis()
        analyzer = RootCauseAnalyzer(mock_llm_client)
        result = await analyzer.analyze(fault_input, empty_analysis)

        assert result.problem_category == "开发引入"
        assert len(result.deep_root_causes) > 0

    @pytest.mark.asyncio
    async def test_analyze_multiple_root_causes(self, fault_input, existing_analysis):
        """Test analyze with multiple root causes in response."""
        multi_response_client = MockLLMClient(
            response="{"
            '"problemCategory": "开发引入",'
            '"initialCause": "设计缺陷",'
            '"deepRootCauses": ['
            '{"layer": "设计层面", "rootCause": "接口契约不清晰", "whyReason": "设计文档未明确", "evidence": "接口文档"},'
            '{"layer": "编码层面", "rootCause": "异常处理缺失", "whyReason": "未做防御性编程", "evidence": "代码缺少try-catch"}'
            "],"
            '"actionableImprovements": ['
            '{"type": "流程改进", "action": "增加接口评审", "owner": "开发", "priority": "中"}'
            "],"
            '"checklistRecommendations": ["接口设计评审checklist"]'
            "}"
        )
        analyzer = RootCauseAnalyzer(multi_response_client)
        result = await analyzer.analyze(fault_input, existing_analysis)

        assert len(result.deep_root_causes) == 2
        assert result.deep_root_causes[0].layer == "设计层面"
        assert result.deep_root_causes[1].layer == "编码层面"

    def test_build_prompt_includes_fault_info(
        self, mock_llm_client, fault_input, existing_analysis
    ):
        """Test that _build_prompt includes fault information."""
        analyzer = RootCauseAnalyzer(mock_llm_client)
        prompt = analyzer._build_prompt(fault_input, existing_analysis)

        assert fault_input.task_no in prompt
        assert fault_input.title in prompt
        assert fault_input.description in prompt
        assert existing_analysis.dev_reason in prompt
        assert existing_analysis.test_reason in prompt

    def test_build_prompt_includes_analysis_requirements(
        self, mock_llm_client, fault_input, existing_analysis
    ):
        """Test that _build_prompt includes analysis requirements."""
        analyzer = RootCauseAnalyzer(mock_llm_client)
        prompt = analyzer._build_prompt(fault_input, existing_analysis)

        assert "问题分类" in prompt
        assert "深层根因挖掘" in prompt
        assert "输出格式" in prompt
        assert "开发引入" in prompt
        assert "测试泄露" in prompt

    def test_build_prompt_includes_requirement_check_section(
        self, mock_llm_client, fault_input, existing_analysis
    ):
        """Test that _build_prompt includes requirement-test chain check section."""
        analyzer = RootCauseAnalyzer(mock_llm_client)
        prompt = analyzer._build_prompt(fault_input, existing_analysis)

        assert "需求-测试传导链例行检查" in prompt
        assert "requirementCheck" in prompt

    def test_build_prompt_renders_requirement_context(self, mock_llm_client, existing_analysis):
        """Test that requirement_context (evidence + gaps) is rendered into prompt."""
        fault_input = FaultAnalysisInput(
            task_no="11757372",
            title="GOMO-BXportin 号码为gomo的号码接口报错",
            description="接口报错",
            task_src="BUG_IN_RD",
            created_date="2026-01-04",
            finish_date="2026-01-08",
            requirement_context=RequirementContext(
                requirement_no="21537689",
                requirement_title="DPC-产品优化提升-Q3",
                requirement_desc="本单作为Q3各类产品优化的总单",
                test_case_ids=[6827877, 6828237],
                source="parent_task",
                data_gaps=["研发云未录入引入单/父需求关联"],
            ),
        )
        analyzer = RootCauseAnalyzer(mock_llm_client)
        prompt = analyzer._build_prompt(fault_input, existing_analysis)

        assert "21537689" in prompt
        assert "DPC-产品优化提升-Q3" in prompt
        assert "本单作为Q3各类产品优化的总单" in prompt
        assert "6827877" in prompt
        assert "研发云未录入引入单/父需求关联" in prompt

    @pytest.mark.asyncio
    async def test_analyze_parses_requirement_check(self, fault_input, existing_analysis):
        """Test that requirementCheck in LLM response maps to requirement_check."""
        client = MockLLMClient(
            response="{"
            '"problemCategory": "需求问题",'
            '"initialCause": "验收标准不明确",'
            '"deepRootCauses": [],'
            '"actionableImprovements": [],'
            '"checklistRecommendations": [],'
            '"requirementCheck": {'
            '"ruleDefinedInRequirement": "未定义",'
            '"testCovered": "证据不足",'
            '"conclusion": "命中传导链"'
            "}"
            "}"
        )
        analyzer = RootCauseAnalyzer(client)
        result = await analyzer.analyze(fault_input, existing_analysis)

        assert result.requirement_check["rule_defined_in_requirement"] == "未定义"
        assert result.requirement_check["test_covered"] == "证据不足"
        assert result.requirement_check["conclusion"] == "命中传导链"

    @pytest.mark.asyncio
    async def test_analyze_requirement_check_defaults_empty(
        self, mock_llm_client, fault_input, existing_analysis
    ):
        """Test that missing requirementCheck (old models) degrades to empty dict."""
        analyzer = RootCauseAnalyzer(mock_llm_client)
        result = await analyzer.analyze(fault_input, existing_analysis)

        assert result.requirement_check == {}


class TestFaultAnalysisInput:
    """Test suite for FaultAnalysisInput model."""

    def test_create_fault_analysis_input(self):
        """Test creating FaultAnalysisInput with all fields."""
        input_data = FaultAnalysisInput(
            task_no="11745664",
            title="测试故障",
            description="故障描述",
            task_src="BUG_ON_SITE",
            created_date="2025-01-01",
            finish_date="2025-01-10",
            product_module_id=100,
            product_version_id=200,
        )

        assert input_data.task_no == "11745664"
        assert input_data.title == "测试故障"
        assert input_data.product_module_id == 100
        assert input_data.product_version_id == 200

    def test_fault_analysis_input_optional_fields(self):
        """Test FaultAnalysisInput with optional fields None."""
        input_data = FaultAnalysisInput(
            task_no="11745664",
            title="测试故障",
            description="故障描述",
            task_src="BUG_ON_SITE",
            created_date="2025-01-01",
            finish_date="2025-01-10",
        )

        assert input_data.product_module_id is None
        assert input_data.product_version_id is None


class TestExistingFaultAnalysis:
    """Test suite for ExistingFaultAnalysis model."""

    def test_create_existing_fault_analysis(self):
        """Test creating ExistingFaultAnalysis with all fields."""
        analysis = ExistingFaultAnalysis(
            dev_catalog="研发环节",
            dev_catalog_detail="正常场景遗漏",
            dev_reason="代码逻辑问题",
            dev_conclusion="需修复代码",
            dev_improve_stage="开发自测",
            test_catalog="测试环节",
            test_catalog_detail="覆盖不足",
            test_reason="用例设计问题",
            test_conclusion="补充用例",
            test_improve_stage="测试补充",
        )

        assert analysis.dev_catalog == "研发环节"
        assert analysis.test_catalog == "测试环节"

    def test_existing_fault_analysis_defaults(self):
        """Test ExistingFaultAnalysis with default values."""
        analysis = ExistingFaultAnalysis()

        assert analysis.dev_catalog == ""
        assert analysis.dev_catalog_detail == ""
        assert analysis.dev_reason == ""


class TestActionableImprovement:
    """Test suite for ActionableImprovement model."""

    def test_create_actionable_improvement(self):
        """Test creating ActionableImprovement."""
        improvement = ActionableImprovement(
            type="直接改进",
            action="增加参数校验",
            owner="开发",
            priority="高",
        )

        assert improvement.type == "直接改进"
        assert improvement.action == "增加参数校验"
        assert improvement.priority == "高"


class TestRootCause:
    """Test suite for RootCause model."""

    def test_create_root_cause(self):
        """Test creating RootCause."""
        root_cause = RootCause(
            layer="编码层面",
            root_cause="异常处理缺失",
            why_reason="未做防御性编程",
            evidence="代码缺少try-catch",
        )

        assert root_cause.layer == "编码层面"
        assert root_cause.root_cause == "异常处理缺失"
        assert root_cause.evidence == "代码缺少try-catch"
