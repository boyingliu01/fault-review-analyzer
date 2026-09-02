"""DelphiReviewerBase 泛化基类不变量锁定（sprint-20260902-77 SLICE-1）。

锁定两级保守兜底不变量（R1/R2 评审高危条件，见设计文档 §3.1）：
- INV-1 专家级失败（round 内解析失败/非法 verdict/调用异常）
  -> opinion_failure_verdict（由域子类决定：违规域 insufficient_evidence /
     结论域 diverged，严禁统一硬编码）
- INV-2 候选级异常（单条候选复审整体失败）
  -> candidate_failure_verdict（两域一致 diverged，保守保留交人工）
- 子类职责：verdict 词表 / _build_material / _item_identity / validate_verdict
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.analyzer.review.base import DelphiReviewerBase
from src.config.models import DelphiReviewConfig, LLMConfig, ReviewerConfig


class _FakeReviewer(DelphiReviewerBase):
    """最小域实现：验证基类机制与域钩子注入。"""

    VALID_VERDICTS = ("a", "b")
    opinion_failure_verdict = "b"
    candidate_failure_verdict = "diverged"

    def _build_material(
        self, fault_info: dict[str, Any], candidate: dict[str, Any]
    ) -> dict[str, str]:
        return {"base_prompt": "评审材料"}

    def _item_identity(self, candidate: dict[str, Any]) -> dict[str, Any]:
        return {"name": candidate.get("name", "")}


class _ExplodingReviewer(_FakeReviewer):
    """候选级异常模拟：_review_candidate 整体失败。"""

    async def _review_candidate(
        self, fault_info: dict[str, Any], candidate: dict[str, Any]
    ) -> dict[str, Any]:
        raise RuntimeError("infra down")


FAULT = {"task_id": 1}
CANDIDATE = {"name": "c1"}


def _make_reviewer(provider: MagicMock) -> _FakeReviewer:
    llm_cfg = LLMConfig(api_key="k", model="m")
    cfg = DelphiReviewConfig(
        enabled=True,
        reviewers=[ReviewerConfig(persona="p1"), ReviewerConfig(persona="p2")],
    )
    reviewer = _FakeReviewer(llm_cfg, cfg)
    reviewer._providers = {"p1": provider, "p2": provider}
    return reviewer


class TestOpinionFailureInvariant:
    """INV-1：专家级失败兜底由域钩子 opinion_failure_verdict 决定。"""

    @pytest.mark.asyncio
    async def test_expert_exception_uses_domain_hook(self):
        broken = MagicMock()
        broken.generate = AsyncMock(side_effect=RuntimeError("network down"))
        reviewer = _make_reviewer(broken)
        record = await reviewer.review(FAULT, [dict(CANDIDATE)])
        item = record["items"][0]
        # 两专家均失败 -> 兜底 "b"（域钩子值，而非基类硬编码）-> 全票共识
        assert item["final_verdict"] == "b" and item["consensus"] is True

    @pytest.mark.asyncio
    async def test_unparseable_output_uses_domain_hook(self):
        garbage = MagicMock()
        garbage.generate = AsyncMock(return_value="抱歉我无法回答")
        reviewer = _make_reviewer(garbage)
        record = await reviewer.review(FAULT, [dict(CANDIDATE)])
        item = record["items"][0]
        assert item["final_verdict"] == "b" and item["consensus"] is True

    @pytest.mark.asyncio
    async def test_invalid_verdict_uses_domain_hook(self):
        liar = MagicMock()
        liar.generate = AsyncMock(return_value='{"verdict": "nonsense", "reason": "r"}')
        reviewer = _make_reviewer(liar)
        record = await reviewer.review(FAULT, [dict(CANDIDATE)])
        item = record["items"][0]
        assert item["final_verdict"] == "b" and item["consensus"] is True


class TestCandidateFailureInvariant:
    """INV-2：候选级异常两域一致 diverged（保守保留，不得漂移为撤销）。"""

    @pytest.mark.asyncio
    async def test_candidate_exception_kept_as_diverged(self):
        llm_cfg = LLMConfig(api_key="k", model="m")
        cfg = DelphiReviewConfig(enabled=True, reviewers=[ReviewerConfig(persona="p1")])
        reviewer = _ExplodingReviewer(llm_cfg, cfg)
        record = await reviewer.review(FAULT, [dict(CANDIDATE)])
        item = record["items"][0]
        assert item["final_verdict"] == "diverged" and item["consensus"] is False
        assert item["reason"].startswith("review_error")


class TestDomainHooks:
    """子类职责契约：identity 合并 / consensus_rule 参数位。"""

    def test_item_identity_merged_into_final_item(self):
        llm_cfg = LLMConfig(api_key="k", model="m")
        cfg = DelphiReviewConfig(enabled=True, reviewers=[ReviewerConfig(persona="p1")])
        reviewer = _FakeReviewer(llm_cfg, cfg)
        item = reviewer._final_item(dict(CANDIDATE), "a", True, 1, [], "ok")
        assert item["name"] == "c1" and item["final_verdict"] == "a"

    def test_consensus_rule_reserved(self):
        llm_cfg = LLMConfig(api_key="k", model="m")
        cfg = DelphiReviewConfig(enabled=True, reviewers=[ReviewerConfig(persona="p1")])
        reviewer = _FakeReviewer(llm_cfg, cfg, consensus_rule="unanimous")
        assert reviewer._consensus_rule == "unanimous"
