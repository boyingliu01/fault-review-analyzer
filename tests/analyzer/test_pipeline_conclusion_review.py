"""pipeline 结论域 Delphi 复审接入不变量锁定（sprint-20260902-77 SLICE-3）。

- REQ-5 插入点：_analyze_with_llm 之后、_match_standards 之前（撤销传导至
  规范匹配与改进建议——两者读 result.root_causes）
- REQ-4 撤销策略：refuted/insufficient_evidence 移出主列表 + 撤销项保留在
  conclusion_review.revoked 审计（不静默清空）；diverged 保留附待人工标记；
  全单撤销 -> conclusion_status="pending_rebuild"
- REQ-8 可观测：全专家连续失败 -> conclusion_review.reviewer_error 标注
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.analyzer.pipeline import AnalysisPipeline
from src.analyzer.review.conclusion_reviewer import apply_conclusion_review
from src.config.models import ConclusionReviewConfig, LLMConfig

ROOT_CAUSE: dict[str, Any] = {
    "cause_type": "设计缺陷",
    "description": "查询未做分页导致全量加载超时",
    "evidence": ["return orderMapper.queryAll();"],
}


def _review_record(verdicts: list[str], reason: str = "r", error: bool = False) -> dict[str, Any]:
    """构造 review 记录（items 与候选按 index 对齐）。"""
    items = []
    for v in verdicts:
        if error:
            opinions = [
                {"reviewer": p, "round": 1, "verdict": v, "reason": f"reviewer_error: net {p}"}
                for p in ("fact_evidence_auditor", "fix_vs_intro_discriminator")
            ]
        else:
            opinions = [
                {"reviewer": p, "round": 1, "verdict": v, "reason": reason, "key_evidence": "e"}
                for p in ("fact_evidence_auditor", "fix_vs_intro_discriminator")
            ]
        items.append(
            {
                "cause_type": ROOT_CAUSE["cause_type"],
                "description": ROOT_CAUSE["description"],
                "final_verdict": v,
                "consensus": True,
                "rounds": 1,
                "reason": reason,
                "opinions": opinions,
            }
        )
    return {
        "reviewed_at": "2026-09-02T00:00:00",
        "method": "delphi_multi_expert_consensus",
        "items": items,
    }


def _pipeline(cfg: ConclusionReviewConfig | None = None) -> AnalysisPipeline:
    config = MagicMock()
    app_cfg = MagicMock()
    app_cfg.review.conclusion_review = cfg or ConclusionReviewConfig(enabled=True)
    app_cfg.llm = LLMConfig(api_key="k", model="m")
    config.get_config.return_value = app_cfg
    return AnalysisPipeline(config)


def _inject_reviewer(pipeline: AnalysisPipeline, record: dict[str, Any]) -> None:
    fake = MagicMock()
    fake.review = AsyncMock(return_value=record)
    fake.providers = []
    pipeline._conclusion_reviewer = fake


def _task_data() -> MagicMock:
    td = MagicMock()
    td.task_id = 1
    td.title = "订单导出失败"
    td.description = "导出超时"
    td.development = None
    return td


def _result(root_causes: list[dict[str, Any]] | None = None) -> Any:
    from src.analyzer.pipeline import PipelineResult

    return PipelineResult(task_id=1, root_causes=root_causes or [dict(ROOT_CAUSE)])


class TestGating:
    """灰度与凭据门禁（REQ-8/INV-4）。"""

    @pytest.mark.asyncio
    async def test_disabled_skips(self):
        pipeline = _pipeline(ConclusionReviewConfig(enabled=False))
        result = _result()
        await pipeline._review_conclusions_with_delphi(_task_data(), result)
        assert result.conclusion_review is None
        assert result.root_causes == [dict(ROOT_CAUSE)]

    @pytest.mark.asyncio
    async def test_no_api_key_skips(self):
        config = MagicMock()
        app_cfg = MagicMock()
        app_cfg.review.conclusion_review = ConclusionReviewConfig(enabled=True)
        app_cfg.llm = LLMConfig(api_key="", model="m")
        config.get_config.return_value = app_cfg
        pipeline = AnalysisPipeline(config)
        result = _result()
        await pipeline._review_conclusions_with_delphi(_task_data(), result)
        assert result.conclusion_review is None


class TestRevocationPolicy:
    """REQ-4 撤销策略。"""

    @pytest.mark.asyncio
    async def test_refuted_removed_and_audited(self):
        pipeline = _pipeline()
        _inject_reviewer(pipeline, _review_record(["refuted"]))
        result = _result()
        await pipeline._review_conclusions_with_delphi(_task_data(), result)
        assert result.root_causes == []  # 主列表移出（传导至规范匹配/改进建议）
        revoked = result.conclusion_review["revoked"]
        assert len(revoked) == 1
        assert revoked[0]["conclusion_verdict"] == "refuted"
        assert revoked[0]["description"] == ROOT_CAUSE["description"]
        assert result.conclusion_review["conclusion_status"] == "pending_rebuild"

    @pytest.mark.asyncio
    async def test_diverged_kept_with_marker(self):
        pipeline = _pipeline()
        _inject_reviewer(pipeline, _review_record(["diverged"]))
        result = _result()
        await pipeline._review_conclusions_with_delphi(_task_data(), result)
        assert len(result.root_causes) == 1  # 保留
        assert result.root_causes[0]["conclusion_verdict"] == "diverged"  # 待人工标记
        assert "conclusion_status" not in result.conclusion_review

    @pytest.mark.asyncio
    async def test_confirmed_kept(self):
        pipeline = _pipeline()
        _inject_reviewer(pipeline, _review_record(["confirmed"]))
        result = _result()
        await pipeline._review_conclusions_with_delphi(_task_data(), result)
        assert len(result.root_causes) == 1
        assert result.root_causes[0]["conclusion_verdict"] == "confirmed"


class TestObservability:
    """REQ-8 可观测标注。"""

    @pytest.mark.asyncio
    async def test_reviewer_error_flagged(self):
        pipeline = _pipeline()
        _inject_reviewer(pipeline, _review_record(["diverged"], error=True))
        result = _result()
        await pipeline._review_conclusions_with_delphi(_task_data(), result)
        # 全专家连续失败 -> diverged 保守保留 + reviewer_error 可观测
        assert result.root_causes[0]["conclusion_verdict"] == "diverged"
        assert result.conclusion_review["reviewer_error"] is True

    @pytest.mark.asyncio
    async def test_deep_impact_annotation(self):
        pipeline = _pipeline()
        _inject_reviewer(pipeline, _review_record(["refuted"]))
        result = _result()
        result.deep_root_causes = {"root_causes": ["深度结论A"]}
        await pipeline._review_conclusions_with_delphi(_task_data(), result)
        assert "深度结论可能受影响" in result.conclusion_review["deep_impact"]


class TestDownstreamPropagation:
    """REQ-5 撤销传导：规范匹配查询不含被撤销结论。"""

    @pytest.mark.asyncio
    async def test_standards_query_excludes_revoked(self):
        pipeline = _pipeline()
        _inject_reviewer(pipeline, _review_record(["refuted"]))
        result = _result()
        await pipeline._review_conclusions_with_delphi(_task_data(), result)
        query = pipeline._build_standards_query(_task_data(), result)
        assert ROOT_CAUSE["description"] not in query


class TestApplyConclusionReview:
    """结论域裁决应用（与违规域 apply_review 对称）。"""

    def test_index_alignment_and_default_diverged(self):
        conclusions = [dict(ROOT_CAUSE), {**ROOT_CAUSE, "description": "第二条"}]
        record = _review_record(["confirmed"])  # 只有 1 个 item
        kept, revoked = apply_conclusion_review(conclusions, record)
        assert len(kept) == 2 and len(revoked) == 0
        # 缺 item 兜底 diverged（保守保留）
        assert kept[1]["conclusion_verdict"] == "diverged"

    def test_revoked_keeps_audit_fields(self):
        conclusions = [dict(ROOT_CAUSE)]
        record = _review_record(["insufficient_evidence"], reason="证据不足")
        kept, revoked = apply_conclusion_review(conclusions, record)
        assert kept == [] and len(revoked) == 1
        assert revoked[0]["conclusion_verdict"] == "insufficient_evidence"
        assert revoked[0]["conclusion_reason"] == "证据不足"
