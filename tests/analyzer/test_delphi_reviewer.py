"""Delphi 违规复审测试套件。

锁定 2026-09 固化到引擎的多专家匿名多轮共识复审行为：
- 正则初筛候选经独立专家评审，共识误报撤销、共识成立保留附依据
- 轮次用尽仍分歧 -> diverged（保留候选，标记人工裁决）
- 评审失败/输出不可解析保守按证据不足处理，不放大违规
"""

from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.analyzer.review.delphi_reviewer import (
    DelphiViolationReviewer,
    apply_review,
    build_context_window,
    normalize_evidence,
    parse_verdict_json,
)
from src.config.models import DelphiReviewConfig, LLMConfig, ReviewerConfig


def _verdict_response(verdict: str, reason: str = "认定理由") -> str:
    return f'{{"verdict": "{verdict}", "reason": "{reason}", "key_evidence": "line"}}'


def _make_reviewer(
    verdicts_a: list[str], verdicts_b: list[str], max_rounds: int = 2
) -> DelphiViolationReviewer:
    """构造带脚本化 mock provider 的复审器（每个专家按顺序返回 verdict 序列）。"""
    llm_cfg = LLMConfig(api_key="test-key", model="test-model", temperature=0.1)
    review_cfg = DelphiReviewConfig(
        enabled=True,
        max_rounds=max_rounds,
        reviewers=[ReviewerConfig(persona="expert_a"), ReviewerConfig(persona="expert_b")],
    )
    reviewer = DelphiViolationReviewer(llm_cfg, review_cfg)

    def scripted(verdicts: list[str]) -> MagicMock:
        provider = MagicMock()
        provider.generate = AsyncMock(side_effect=[_verdict_response(v) for v in verdicts])
        return provider

    reviewer._providers = {
        "expert_a": scripted(verdicts_a),
        "expert_b": scripted(verdicts_b),
    }
    return reviewer


FAULT_INFO = {
    "task_id": 1,
    "title": "并发问题",
    "description": "线程环境",
    "code_snippet": "Map<String, Object> paramMap = new HashMap<>();",
}
VIOLATION = {
    "rule_id": "J000025",
    "rule_name": "non_thread_safe_collection",
    "message": "多线程环境下使用非线程安全集合（J000025）",
    "evidence": ["Map<String, Object> paramMap = new HashMap<>();"],
}


class TestParseVerdictJson:
    def test_plain_json(self):
        data = parse_verdict_json('{"verdict": "violation", "reason": "r"}')
        assert data and data["verdict"] == "violation"

    def test_markdown_code_block(self):
        text = '评审结论如下：\n```json\n{"verdict": "false_positive"}\n```'
        assert parse_verdict_json(text) == {"verdict": "false_positive"}

    def test_embedded_json_object(self):
        data = parse_verdict_json('前缀 {"verdict": "violation"} 后缀')
        assert data is not None and data["verdict"] == "violation"

    def test_empty_or_garbage_returns_none(self):
        assert parse_verdict_json("") is None
        assert parse_verdict_json("无法解析的文本") is None


class TestEvidenceAndContext:
    def test_normalize_evidence_variants(self):
        assert normalize_evidence(["a", "b"]) == ["a", "b"]
        assert normalize_evidence("line1\nline2") == ["line1", "line2"]
        assert normalize_evidence(None) == []
        assert normalize_evidence(["", "  "]) == []

    def test_context_window_locates_hit_line(self):
        code = "a\nb\nc\npassword = 'x'\nd\ne"
        ctx = build_context_window(code, ["password = 'x'"], context_lines=1)
        assert "password = 'x'" in ctx
        assert "c" in ctx and "d" in ctx  # 前后各 1 行

    def test_context_window_fallback_on_miss(self):
        ctx = build_context_window("x\ny\nz", ["不存在的命中行"], context_lines=2)
        assert "x" in ctx and "z" in ctx  # 兜底取片段前若干行

    def test_context_window_multi_hits_separate_windows(self):
        lines = ["fill"] * 20 + ["HIT_ONE"] + ["fill"] * 5 + ["HIT_TWO"]
        code = "\n".join(lines)
        ctx = build_context_window(code, ["HIT_ONE", "HIT_TWO"], context_lines=1)
        assert "HIT_ONE" in ctx and "HIT_TWO" in ctx


class TestApplyReview:
    def test_consensus_false_positive_revoked(self):
        record = {"items": [{"final_verdict": "false_positive", "reason": "局部变量"}]}
        kept, revoked = apply_review([dict(VIOLATION)], record)
        assert not kept and len(revoked) == 1
        assert revoked[0]["delphi_verdict"] == "false_positive"

    def test_consensus_insufficient_evidence_revoked(self):
        record = {"items": [{"final_verdict": "insufficient_evidence", "reason": "证据不足"}]}
        kept, revoked = apply_review([dict(VIOLATION)], record)
        assert not kept and revoked[0]["delphi_verdict"] == "insufficient_evidence"

    def test_consensus_violation_kept_with_reason(self):
        record = {"items": [{"final_verdict": "violation", "reason": "跨线程共享"}]}
        kept, revoked = apply_review([dict(VIOLATION)], record)
        assert not revoked and kept[0]["delphi_reason"] == "跨线程共享"

    def test_diverged_kept_for_manual_review(self):
        record = {"items": [{"final_verdict": "diverged", "reason": "专家分歧"}]}
        kept, revoked = apply_review([dict(VIOLATION)], record)
        assert not revoked and kept[0]["delphi_verdict"] == "diverged"

    def test_missing_item_defaults_diverged(self):
        kept, _ = apply_review([dict(VIOLATION)], {"items": []})
        assert kept and kept[0]["delphi_verdict"] == "diverged"


class TestDelphiReviewerConsensus:
    @pytest.mark.asyncio
    async def test_round1_unanimous_revocation(self):
        """首轮全票误报 -> 共识撤销，仅 1 轮调用。"""
        reviewer = _make_reviewer(["false_positive"], ["false_positive"])
        record = await reviewer.review(FAULT_INFO, [dict(VIOLATION)])
        item = record["items"][0]
        assert item["final_verdict"] == "false_positive" and item["consensus"] is True
        assert item["rounds"] == 1
        kept, revoked = apply_review([dict(VIOLATION)], record)
        assert not kept and len(revoked) == 1

    @pytest.mark.asyncio
    async def test_round2_convergence_after_feedback(self):
        """首轮分歧 -> 二轮带匿名反方意见重审后收敛。"""
        reviewer = _make_reviewer(
            ["violation", "false_positive"], ["false_positive", "false_positive"]
        )
        record = await reviewer.review(FAULT_INFO, [dict(VIOLATION)])
        item = record["items"][0]
        assert item["final_verdict"] == "false_positive" and item["rounds"] == 2
        # 专家 A 第二轮调用应包含匿名反方意见（generate(SYSTEM, user) 位置传参）
        provider_a = cast("MagicMock", reviewer._providers["expert_a"])
        second_call = provider_a.generate.call_args_list[1]
        assert "匿名" in second_call.args[1]

    @pytest.mark.asyncio
    async def test_divergence_after_max_rounds(self):
        """两轮仍分歧 -> diverged 保留候选交人工。"""
        reviewer = _make_reviewer(["violation", "violation"], ["false_positive", "false_positive"])
        record = await reviewer.review(FAULT_INFO, [dict(VIOLATION)])
        item = record["items"][0]
        assert item["final_verdict"] == "diverged" and item["consensus"] is False
        kept, _ = apply_review([dict(VIOLATION)], record)
        assert kept and kept[0]["delphi_verdict"] == "diverged"

    @pytest.mark.asyncio
    async def test_reviewer_error_treated_as_insufficient(self):
        """专家调用异常 -> 该专家按证据不足；另一专家 violation 则分歧 diverged。"""
        llm_cfg = LLMConfig(api_key="k", model="m")
        review_cfg = DelphiReviewConfig(
            enabled=True,
            reviewers=[ReviewerConfig(persona="a"), ReviewerConfig(persona="b")],
        )
        reviewer = DelphiViolationReviewer(llm_cfg, review_cfg)
        broken = MagicMock()
        broken.generate = AsyncMock(side_effect=RuntimeError("network down"))
        good = MagicMock()
        good.generate = AsyncMock(return_value=_verdict_response("violation"))
        reviewer._providers = {"a": broken, "b": good}

        record = await reviewer.review(FAULT_INFO, [dict(VIOLATION)])
        item = record["items"][0]
        # broken=insufficient_evidence vs good=violation -> 分歧 -> diverged
        assert item["final_verdict"] == "diverged"

    @pytest.mark.asyncio
    async def test_unparseable_output_treated_as_insufficient(self):
        """输出不可解析 -> 证据不足（不放大违规）。"""
        llm_cfg = LLMConfig(api_key="k", model="m")
        review_cfg = DelphiReviewConfig(
            enabled=True,
            reviewers=[ReviewerConfig(persona="a"), ReviewerConfig(persona="b")],
        )
        reviewer = DelphiViolationReviewer(llm_cfg, review_cfg)
        garbage = MagicMock()
        garbage.generate = AsyncMock(return_value="抱歉我无法回答")
        good = MagicMock()
        good.generate = AsyncMock(return_value=_verdict_response("false_positive"))
        reviewer._providers = {"a": garbage, "b": good}

        record = await reviewer.review(FAULT_INFO, [dict(VIOLATION)])
        item = record["items"][0]
        # garbage=insufficient_evidence vs good=false_positive -> 分歧 diverged（保守保留）
        assert item["final_verdict"] == "diverged"

    @pytest.mark.asyncio
    async def test_material_contains_rule_and_context(self):
        """评审材料应包含条款、命中上下文与初筛误报形态提示。"""
        reviewer = _make_reviewer(["false_positive"], ["false_positive"])
        await reviewer.review(FAULT_INFO, [dict(VIOLATION)])
        call = cast("MagicMock", reviewer._providers["expert_a"]).generate.call_args_list[0]
        user_prompt = call.args[1]
        assert "J000025" in user_prompt
        assert "paramMap = new HashMap<>" in user_prompt
        assert "insufficient_evidence" in user_prompt  # 宁缺毋滥纪律
        assert "误报形态" in user_prompt
