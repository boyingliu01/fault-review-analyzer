"""引入单代码变更拉取与注入防回归测试（故障单 11757372 教训）。

背景：11757372 复盘把故障单自身的修复性变更（按客户要求改用新校验逻辑、
跳过父类校验）误判为"绕过父类校验的设计缺陷"，并对 diff 中未出现的父类
实现臆测"可能存在的业务逻辑"。修复后：
- 引入单（introduceTaskNo，引入此缺陷的任务单）的代码变更作为缺陷引入的
  直接候选证据，注入普通/深度两条根因链路
- 拉取失败/无单号/非数字单号时降级为空串，不阻断主流程
- 普通链路 prompt 增加变更意图识别与禁止臆测未读代码纪律条款

本测试锁定：
- fetch_introduce_task_diff 的降级矩阵（不阻断主流程）
- 普通链路 prompt 的纪律条款（正向断言）
- 引入单 diff 在普通链路的 segment 注入与 prompt 渲染
"""

from datetime import datetime
from unittest.mock import AsyncMock

from src.analyzer.handlers.analyze import AnalyzeHandler
from src.analyzer.introduce_diff import MAX_INTRODUCE_DIFF_CHARS, fetch_introduce_task_diff
from src.analyzer.reasoning.generator import (
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
    build_segment_details,
)
from src.api.models import CommitInfo


def _make_commit(diff: str) -> CommitInfo:
    return CommitInfo(
        commit_id="abc123",
        message="fix",
        time=datetime(2026, 8, 27, 10, 0, 0),
        diff=diff,
    )


class TestFetchIntroduceTaskDiff:
    """fetch_introduce_task_diff 降级矩阵"""

    async def test_no_introduce_task_no_returns_empty(self):
        """单据未填写引入单号（None/缺失）→ 空串，不调用 API"""
        api = AsyncMock()
        result = await fetch_introduce_task_diff(api, {"task_id": 11757372})
        assert result == ""
        api.get_commits.assert_not_awaited()

    async def test_empty_string_no_returns_empty(self):
        """引入单号为空串 → 空串"""
        api = AsyncMock()
        result = await fetch_introduce_task_diff(api, {"introduce_task_no": ""})
        assert result == ""

    async def test_api_client_none_returns_empty(self):
        """API 客户端不可用 → 空串（不抛异常）"""
        result = await fetch_introduce_task_diff(None, {"introduce_task_no": "11758001"})
        assert result == ""

    async def test_non_digit_no_returns_empty(self):
        """引入单号非数字单号 → 空串，不调用 API"""
        api = AsyncMock()
        result = await fetch_introduce_task_diff(api, {"introduce_task_no": "REQ-abc"})
        assert result == ""
        api.get_commits.assert_not_awaited()

    async def test_api_error_returns_empty(self):
        """API 拉取失败（单号不存在等）→ 空串，不抛异常"""
        api = AsyncMock()
        api.get_commits = AsyncMock(side_effect=RuntimeError("404 not found"))
        result = await fetch_introduce_task_diff(api, {"introduce_task_no": "11758001"})
        assert result == ""

    async def test_success_returns_diff(self):
        """正常拉取 → 返回引入单 diff 内容"""
        api = AsyncMock()
        api.get_commits = AsyncMock(return_value=[_make_commit("- old; + new check")])
        result = await fetch_introduce_task_diff(api, {"introduce_task_no": "11758001"})
        assert "new check" in result
        api.get_commits.assert_awaited_once_with(11758001)

    async def test_diff_truncated_to_limit(self):
        """超长 diff 截断到 MAX_INTRODUCE_DIFF_CHARS"""
        api = AsyncMock()
        api.get_commits = AsyncMock(return_value=[_make_commit("x" * (MAX_INTRODUCE_DIFF_CHARS + 100))])
        result = await fetch_introduce_task_diff(api, {"introduce_task_no": "11758001"})
        assert len(result) == MAX_INTRODUCE_DIFF_CHARS

    async def test_camel_case_key_supported(self):
        """API 原始数据（camelCase introduceTaskNo）也能取到单号"""
        api = AsyncMock()
        api.get_commits = AsyncMock(return_value=[_make_commit("diff-body")])
        result = await fetch_introduce_task_diff(api, {"introduceTaskNo": "11758001"})
        assert "diff-body" in result


class TestNormalChainPromptDiscipline:
    """普通链路 SYSTEM_PROMPT 纪律条款（11757372 教训）"""

    def test_change_intent_identification_clause(self):
        """变更意图识别条款：修复动作不得被定性为缺陷"""
        assert "变更意图识别" in SYSTEM_PROMPT
        assert "不得将修复动作本身定性为缺陷" in SYSTEM_PROMPT
        assert "旧代码" in SYSTEM_PROMPT  # old 侧才是缺陷引入候选

    def test_attribution_direction_clause(self):
        """故障归因方向条款：故障现象归因于修复前行为，而非修复后代码形态（11757372 第二次教训）"""
        assert "故障归因方向" in SYSTEM_PROMPT
        assert "追溯到修复前的旧行为" in SYSTEM_PROMPT
        assert "作为缺陷结论" in SYSTEM_PROMPT
        assert "新增了某处理，说明修复前缺少该处理" in SYSTEM_PROMPT

    def test_user_prompt_attribution_direction(self):
        """user prompt 注意事项包含修复后代码形态不得定性与反推缺失说明"""
        assert "修复后代码的设计形态定性为缺陷" in USER_PROMPT_TEMPLATE
        assert "说明修复前缺少" in USER_PROMPT_TEMPLATE

    def test_no_speculation_about_unread_code_clause(self):
        """禁止臆测未读代码条款：父类实现等不在 diff 中的代码不得猜测"""
        assert "禁止臆测未读代码" in SYSTEM_PROMPT
        assert "父类实现" in SYSTEM_PROMPT
        assert "证据不足" in SYSTEM_PROMPT

    def test_concept_grounding_clause(self):
        """概念溯源条款：技术概念必须能在原文找到"""
        assert "概念溯源" in SYSTEM_PROMPT
        assert "不得引入原文中不存在的概念" in SYSTEM_PROMPT

    def test_user_prompt_change_intent_note(self):
        """user prompt 注意事项包含变更意图判断与引入单优先级说明"""
        assert "变更" in USER_PROMPT_TEMPLATE
        assert "修复动作本身或修复后代码的设计形态定性为缺陷" in USER_PROMPT_TEMPLATE
        assert "引入缺陷任务单的代码变更" in USER_PROMPT_TEMPLATE

    def test_segment_label_for_introduce_diff(self):
        """introduce_task_diff segment 渲染为中文标签"""
        details = build_segment_details(
            [{"type": "introduce_task_diff", "content": "diff content here"}]
        )
        assert "引入缺陷任务单的代码变更" in details
        assert "diff content here" in details


class TestNormalChainDiffInjection:
    """普通链路引入单 diff 注入测试"""

    def _make_prompt_capturing_handler(self) -> tuple[AnalyzeHandler, list[str]]:
        """构造捕获 user prompt 的 handler，用于验证渲染内容"""
        captured: list[str] = []

        class CapturingProvider:
            async def generate(self, system: str, user: str) -> str:  # noqa: ARG002
                captured.append(user)
                return (
                    '{"root_causes": [{"cause_type": "测试", "description": "d",'
                    ' "evidence": ["e"], "confidence": 0.5}], "analysis_summary": "s",'
                    ' "technical_factors": [], "process_factors": [],'
                    ' "management_factors": []}'
                )

        handler = AnalyzeHandler(llm_provider=CapturingProvider())
        return handler, captured

    def _make_task_data(self) -> dict:
        return {
            "task_id": 11757372,
            "title": "号码接口报错",
            "description": "gomo号码查询报错",
            "status": "open",
            "priority": "high",
        }

    async def test_introduce_diff_in_user_prompt(self):
        """注入引入单 diff 后，user prompt 必须包含引入单区块标签与内容"""
        handler, captured = self._make_prompt_capturing_handler()
        from src.preprocessor.models import ProcessedTask, TextSegment

        preprocessed = ProcessedTask(
            task_id=11757372,
            segments=[TextSegment(task_id=11757372, type="development", content="开发记录")],
        )
        await handler.analyze_root_cause(
            self._make_task_data(),
            preprocessed,
            introduce_task_diff="cocManager.qryNbrOperator(accNbr) 新校验逻辑",
        )
        assert captured, "LLM 未被调用"
        prompt = captured[0]
        assert "引入缺陷任务单的代码变更" in prompt
        assert "qryNbrOperator" in prompt

    async def test_no_introduce_diff_keeps_segments_unchanged(self):
        """无引入单 diff 时，不追加空 segment"""
        handler, captured = self._make_prompt_capturing_handler()
        from src.preprocessor.models import ProcessedTask, TextSegment

        preprocessed = ProcessedTask(
            task_id=11757372,
            segments=[TextSegment(task_id=11757372, type="development", content="开发记录")],
        )
        await handler.analyze_root_cause(self._make_task_data(), preprocessed)
        prompt = captured[0]
        # 仅 user prompt 注意事项提及该标签 1 次，无实际引入单区块渲染
        assert prompt.count("引入缺陷任务单的代码变更") == 1
