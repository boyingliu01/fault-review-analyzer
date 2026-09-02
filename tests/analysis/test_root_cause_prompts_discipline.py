"""根因分析 prompt 事实纪律防回归测试。

背景（故障单 11955497）两轮偏差教训：
1. 第一轮：深度根因分析把截图中短信模板变量 ${UTM_LINK$$$ClaimVoucher}
   （正常配置占位符）误判为"变量映射缺陷"，进而脑补出"缓存写入未实现幂等性"的
   机制性根因并派生出流程层结论与改进建议。→ 修复：事实纪律条款。
2. 第二轮：修复 prompt 时在禁止条款中列举了"幂等性、并发、重复写入、内存泄漏"
   等示例词，反而为 LLM 提供了词汇锚点——模型从"缓存写入重复"联想并套用
   "幂等性"概念框架（本单实为宏列表去重的性能问题，与幂等无关）。→ 修复：
   删除机制词表 + 概念溯源/最简解释条款 + 注入普通链路结论作为事实锚点。

背景（故障单 11757372）第三轮偏差教训：
3. 普通链路把故障单的修复性代码变更（按客户要求改用新校验逻辑、跳过父类
   校验）误判为"绕过父类校验的设计缺陷"，并对 diff 中未出现的父类实现
   臆测"可能存在的业务逻辑"。→ 修复：变更意图识别条款 + 禁止臆测未读
   代码条款 + 引入单号代码变更接入（引入单 diff 才是缺陷引入候选证据）。

本测试锁定：
- prompt 中必须存在的事实约束条款（正向）
- prompt 中不得再出现机制概念词表（反向锚定防护）
- 深度分析 prompt 必须注入普通链路结论（事实锚点）
- 深度分析 prompt 必须区分修复变更与引入变更（11757372 教训）
"""

from typing import Any

from src.analysis.root_cause.analyzer import RootCauseAnalyzer
from src.analysis.root_cause.models import ExistingFaultAnalysis, FaultAnalysisInput
from src.analysis.root_cause.prompts import (
    ROOT_CAUSE_ANALYSIS_PROMPT,
    ROOT_CAUSE_SYSTEM_PROMPT,
)

# 曾在禁止条款中出现、反而被 LLM 拿来套用的机制词表——prompt 中不得再出现
FORBIDDEN_MECHANISM_WORDS = ["幂等", "并发", "重复写入", "内存泄漏"]


class TestRootCauseSystemPromptDiscipline:
    """system prompt 必须包含事实纪律条款"""

    def test_evidence_reasoning_separation(self):
        """证据与结论分离条款"""
        assert "证据与结论分离" in ROOT_CAUSE_SYSTEM_PROMPT
        assert "推理链条" in ROOT_CAUSE_SYSTEM_PROMPT

    def test_forbid_mechanism_hallucination(self):
        """禁止机制脑补条款（概念必须溯源到证据原文）"""
        assert "禁止机制脑补" in ROOT_CAUSE_SYSTEM_PROMPT
        assert "证据原文" in ROOT_CAUSE_SYSTEM_PROMPT
        assert "不得引入证据原文中不存在的概念" in ROOT_CAUSE_SYSTEM_PROMPT

    def test_business_knowledge_boundary(self):
        """业务知识边界条款"""
        assert "待业务确认" in ROOT_CAUSE_SYSTEM_PROMPT

    def test_insufficient_evidence_degrades(self):
        """证据不足如实降级条款"""
        assert "证据不足" in ROOT_CAUSE_SYSTEM_PROMPT
        assert "准确性优先于完整性" in ROOT_CAUSE_SYSTEM_PROMPT

    def test_simplest_explanation_rule(self):
        """最简解释优先条款（11955497 第二轮教训：性能问题不得升格）"""
        assert "最简解释优先" in ROOT_CAUSE_SYSTEM_PROMPT
        assert "不得在分析中被改变" in ROOT_CAUSE_SYSTEM_PROMPT

    def test_improvements_not_based_on_unverified_assumption(self):
        """改进措施不得建立在未证实假设上"""
        assert "未经证实的机制假设" in ROOT_CAUSE_SYSTEM_PROMPT

    def test_distinguish_fix_vs_introduce_change(self):
        """区分修复变更与引入变更条款（11757372 教训）"""
        assert "区分修复变更与引入变更" in ROOT_CAUSE_SYSTEM_PROMPT
        assert "不得将修复动作本身定性为缺陷" in ROOT_CAUSE_SYSTEM_PROMPT
        assert "不得臆测其逻辑" in ROOT_CAUSE_SYSTEM_PROMPT

    def test_attribution_direction_for_fixed_code(self):
        """故障现象归因于修复前行为，修复后代码形态不得作为缺陷结论（11757372 二次教训）"""
        assert "故障现象应归因于修复前的旧行为" in ROOT_CAUSE_SYSTEM_PROMPT
        assert "不得作为缺陷结论" in ROOT_CAUSE_SYSTEM_PROMPT

    def test_no_mechanism_word_list(self):
        """prompt 不得包含机制概念词表（词汇锚定防护）

        在禁止条款中列举具体机制词汇会反向引导 LLM 套用这些概念
        （11955497 第二轮偏差的直接成因）。
        """
        for prompt in (ROOT_CAUSE_SYSTEM_PROMPT, ROOT_CAUSE_ANALYSIS_PROMPT):
            for word in FORBIDDEN_MECHANISM_WORDS:
                assert word not in prompt, f"prompt 中出现机制词表词汇: {word}"


class TestRootCauseAnalysisPromptDiscipline:
    """user prompt 模板必须包含事实纪律注意事项"""

    def test_discipline_section_exists(self):
        """事实纪律章节存在"""
        assert "事实纪律与注意事项" in ROOT_CAUSE_ANALYSIS_PROMPT
        assert "禁止脑补与幻觉" in ROOT_CAUSE_ANALYSIS_PROMPT

    def test_evidence_layering_rule(self):
        """证据分层规则：禁止多级推测"""
        assert "证据分层" in ROOT_CAUSE_ANALYSIS_PROMPT
        assert "暗示" in ROOT_CAUSE_ANALYSIS_PROMPT  # 明确点名禁止"X 暗示 Y"句式

    def test_surface_pattern_not_defect_rule(self):
        """表面现象≠代码缺陷规则（模板变量占位符案例教训）"""
        assert "表面现象" in ROOT_CAUSE_ANALYSIS_PROMPT
        # 模板用 str.format 渲染，字面大括号需写成 ${{VAR}}，渲染后为 ${VAR}
        assert "${{VAR}}" in ROOT_CAUSE_ANALYSIS_PROMPT
        assert "占位符" in ROOT_CAUSE_ANALYSIS_PROMPT

    def test_concept_grounding_rule(self):
        """概念溯源规则（第二轮教训：从'重复'不得推出证据中没有的概念）"""
        assert "概念溯源" in ROOT_CAUSE_ANALYSIS_PROMPT
        assert "证据原文中没有的概念" in ROOT_CAUSE_ANALYSIS_PROMPT

    def test_simplest_explanation_rule(self):
        """最简解释优先规则：故障定性不得被改变"""
        assert "最简解释优先" in ROOT_CAUSE_ANALYSIS_PROMPT
        assert "不得在分析中被改变或重新包装" in ROOT_CAUSE_ANALYSIS_PROMPT

    def test_layer_count_not_forced(self):
        """不得强制凑齐 5 层结论（防止为凑层数编造结论）"""
        assert "不得为了凑齐层数而编造结论" in ROOT_CAUSE_ANALYSIS_PROMPT
        assert "每层追问都必须给出明确结论" not in ROOT_CAUSE_ANALYSIS_PROMPT

    def test_business_terms_pending_confirmation_rule(self):
        """业务术语待确认规则"""
        assert "短信模板变量" in ROOT_CAUSE_ANALYSIS_PROMPT
        assert "待业务确认" in ROOT_CAUSE_ANALYSIS_PROMPT

    def test_prior_root_causes_section_exists(self):
        """已确认根因结论区块存在（事实锚点注入位）"""
        assert "本单已确认的根因结论" in ROOT_CAUSE_ANALYSIS_PROMPT
        assert "{prior_root_causes}" in ROOT_CAUSE_ANALYSIS_PROMPT

    def test_prior_root_causes_misjudge_warning(self):
        """锚点区块必须标注自动结论可能误判（11757372 教训）"""
        assert "可能存在误判" in ROOT_CAUSE_ANALYSIS_PROMPT
        assert "以直接证据为准" in ROOT_CAUSE_ANALYSIS_PROMPT

    def test_introduce_task_diff_section_exists(self):
        """引入单代码变更区块存在，且与故障单修复变更区分开"""
        assert "引入缺陷任务单的代码变更" in ROOT_CAUSE_ANALYSIS_PROMPT
        assert "{introduce_task_diff}" in ROOT_CAUSE_ANALYSIS_PROMPT
        assert "通常是修复动作" in ROOT_CAUSE_ANALYSIS_PROMPT

    def test_evidence_insufficient_rule(self):
        """证据不足降级规则"""
        assert "证据不足，无法确认该层根因" in ROOT_CAUSE_ANALYSIS_PROMPT

    def test_output_format_still_parseable(self):
        """约束增强不得破坏 JSON 输出格式定义（下游解析依赖）"""
        for key in (
            "problemCategory",
            "initialCause",
            "deepRootCauses",
            "actionableImprovements",
            "checklistRecommendations",
        ):
            assert f'"{key}"' in ROOT_CAUSE_ANALYSIS_PROMPT


class TestPriorRootCausesInjection:
    """普通链路结论注入深度分析 prompt 的事实锚点测试"""

    def _make_analyzer(self) -> RootCauseAnalyzer:
        return RootCauseAnalyzer(llm_client=object())

    def _make_fault_input(
        self, prior: list[dict[str, Any]] | None = None
    ) -> FaultAnalysisInput:
        return FaultAnalysisInput(
            task_no="11955497",
            title="SMS发送utm短链",
            description="活动运行缓慢",
            task_src="",
            created_date="",
            finish_date="",
            prior_root_causes=prior or [],
        )

    def test_build_prompt_contains_prior_conclusions(self):
        """有普通结论时，prompt 必须包含结论原文与证据"""
        analyzer = self._make_analyzer()
        prior = [
            {
                "cause_type": "性能问题",
                "description": "未对宏列表去重，导致重复解析和缓存写入",
                "evidence": ["代码变更新增 copyDistinctMacroList 方法对宏列表去重"],
            }
        ]
        prompt = analyzer._build_prompt(
            self._make_fault_input(prior), ExistingFaultAnalysis()
        )
        assert "本单已确认的根因结论" in prompt
        assert "未对宏列表去重" in prompt
        assert "copyDistinctMacroList" in prompt
        assert "[性能问题]" in prompt

    def test_build_prompt_without_prior_marks_absence(self):
        """无普通结论时，prompt 必须显式标注缺失并提示严守证据边界"""
        analyzer = self._make_analyzer()
        prompt = analyzer._build_prompt(
            self._make_fault_input(None), ExistingFaultAnalysis()
        )
        assert "本单已确认的根因结论" in prompt
        assert "证据不足的层面如实降级" in prompt

    def test_render_prior_handles_string_evidence(self):
        """evidence 为字符串（非列表）时也能渲染"""
        analyzer = self._make_analyzer()
        text = analyzer._render_prior_root_causes(
            [{"cause_type": "性能问题", "description": "d", "evidence": "单一证据"}]
        )
        assert "单一证据" in text


class TestIntroduceTaskDiffInjection:
    """引入单代码变更注入深度分析 prompt 的测试（11757372 教训）"""

    def _make_analyzer(self) -> RootCauseAnalyzer:
        return RootCauseAnalyzer(llm_client=object())

    def _make_fault_input(
        self, introduce_task_diff: str = ""
    ) -> FaultAnalysisInput:
        return FaultAnalysisInput(
            task_no="11757372",
            title="GOMO-BXportin 号码为gomo的号码接口报错",
            description="号码接口报错",
            task_src="",
            created_date="",
            finish_date="",
            introduce_task_diff=introduce_task_diff,
        )

    def test_build_prompt_contains_introduce_diff(self):
        """有引入单 diff 时，prompt 必须包含其内容"""
        analyzer = self._make_analyzer()
        diff = "- if (operator.equals(\"SINGTEL\")) { return cocManager.qryNbrOperator(accNbr); }"
        prompt = analyzer._build_prompt(
            self._make_fault_input(diff), ExistingFaultAnalysis()
        )
        assert "引入缺陷任务单的代码变更" in prompt
        assert "qryNbrOperator" in prompt

    def test_build_prompt_without_introduce_diff_marks_absence(self):
        """无引入单 diff 时，prompt 必须显式标注缺失并给出替代证据指引"""
        analyzer = self._make_analyzer()
        prompt = analyzer._build_prompt(
            self._make_fault_input(""), ExistingFaultAnalysis()
        )
        assert "未填写引入单号" in prompt
        assert "旧代码与描述证据为准" in prompt

    def test_render_introduce_diff_strips_whitespace(self):
        """渲染时去除首尾空白"""
        analyzer = self._make_analyzer()
        assert analyzer._render_introduce_task_diff("  diff-body  ") == "diff-body"
