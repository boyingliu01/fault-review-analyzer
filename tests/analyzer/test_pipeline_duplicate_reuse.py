"""pipeline 重复单结论复用接入不变量锁定（feat/duplicate-conclusion-reuse R8）。

- 复用命中（issue no / 内容 strong）-> root_causes 与 conclusion_review 直接
  取主单，跳过根因 LLM 与结论域 Delphi 复审；labels 仍照常生成
- 未启用 / 无关联 / 主单无结论 -> 一切照旧走 LLM
- 配置默认关闭，复用属编程传参灰度（与结论域复审 INV-4 同策略）
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.analyzer.pipeline import AnalysisPipeline, PipelineConfig, PipelineResult
from src.config.models import LLMConfig

MASTER_REC: dict[str, Any] = {
    "urId": 200,
    "root_causes": [{"cause_type": "设计缺陷", "description": "查询未做分页导致超时"}],
    "conclusion_review": {
        "reviewed_at": "2026-09-03T12:00:00",
        "method": "delphi_multi_expert_consensus",
        "items": [],
    },
    "deep_root_causes": {"deep_root_causes": ["深度结论A"]},
}


def _master_provider(task_id: int) -> dict[str, Any] | None:
    return MASTER_REC if task_id == 200 else None


def _issue_provider(task_id: int) -> str | None:
    # 100 与 200 同属 IS22976（样例对形态）
    return "IS22976" if task_id in (100, 200) else None


def _task_dict(tid: int) -> dict[str, Any]:
    return {
        "task_id": tid,
        "title": "订单导出超时",
        "description": "导出接口超时",
        "create_time": "2026-01-04 15:30:00",
        "development": None,
    }


def _task_data(tid: int = 100) -> MagicMock:
    td = MagicMock()
    td.task_id = tid
    td.model_dump.return_value = _task_dict(tid)
    td.title = "订单导出超时"
    td.description = "导出接口超时"
    td.development = None
    return td


def _pipeline(
    provider: Any = _master_provider,
    issue_provider: Any = _issue_provider,
    use_reuse: bool = True,
    cache_tasks: list[dict[str, Any]] | None = None,
) -> AnalysisPipeline:
    cfg = PipelineConfig(
        use_llm=True,
        generate_labels=True,
        analyze_root_cause=True,
        reuse_related_conclusion=use_reuse,
        related_conclusion_provider=provider,
        issue_no_provider=issue_provider,
    )
    config = MagicMock()
    app_cfg = MagicMock()
    app_cfg.llm = LLMConfig(api_key="k", model="m")
    config.get_config.return_value = app_cfg
    pipeline = AnalysisPipeline(config, cfg)
    pipeline._cache_manager = MagicMock()
    pipeline._cache_manager.get_all_tasks.return_value = (
        cache_tasks if cache_tasks is not None else [_task_dict(200)]
    )
    return pipeline


class TestReuseApplied:
    @pytest.mark.asyncio
    async def test_try_reuse_fills_master_conclusion(self):
        pipeline = _pipeline()
        result = PipelineResult(task_id=100)
        reused = await pipeline._try_reuse_related_conclusion(_task_dict(100), result)
        assert reused is True
        assert result.root_causes == MASTER_REC["root_causes"]
        assert result.conclusion_review is not None
        reused_meta = result.conclusion_review["reused_from"]
        assert reused_meta["master_urId"] == 200
        assert reused_meta["source"] == "issue_no"
        assert result.deep_root_causes == {"deep_root_causes": ["深度结论A"]}

    @pytest.mark.asyncio
    async def test_analyze_with_llm_skips_root_cause_llm(self):
        pipeline = _pipeline()
        pipeline._generate_labels = AsyncMock(return_value=[])
        pipeline._analyze_root_cause = AsyncMock(return_value=[{"cause_type": "x"}])
        result = PipelineResult(task_id=100)
        await pipeline._analyze_with_llm(_task_data(100), MagicMock(), result)
        pipeline._analyze_root_cause.assert_not_called()
        assert result.root_causes == MASTER_REC["root_causes"]
        assert result.labels == []

    @pytest.mark.asyncio
    async def test_conclusion_review_skipped_for_reused(self):
        pipeline = _pipeline()
        pipeline._conclusion_reviewer = MagicMock()
        pipeline._conclusion_reviewer.review = AsyncMock()
        result = PipelineResult(task_id=100)
        result.conclusion_review = {"reused_from": {"master_urId": 200}}
        await pipeline._review_conclusions_with_delphi(_task_data(100), result)
        pipeline._conclusion_reviewer.review.assert_not_called()
        assert result.conclusion_review == {"reused_from": {"master_urId": 200}}


class TestReuseNotApplied:
    @pytest.mark.asyncio
    async def test_disabled_by_default_runs_llm(self):
        pipeline = _pipeline(use_reuse=False)
        pipeline._generate_labels = AsyncMock(return_value=[])
        pipeline._analyze_root_cause = AsyncMock(return_value=[{"cause_type": "x"}])
        result = PipelineResult(task_id=100)
        await pipeline._analyze_with_llm(_task_data(100), MagicMock(), result)
        pipeline._analyze_root_cause.assert_awaited_once()
        assert result.root_causes == [{"cause_type": "x"}]
        assert result.conclusion_review is None

    @pytest.mark.asyncio
    async def test_no_cache_runs_llm(self):
        pipeline = _pipeline()
        pipeline._cache_manager = None
        pipeline._generate_labels = AsyncMock(return_value=[])
        pipeline._analyze_root_cause = AsyncMock(return_value=[{"cause_type": "x"}])
        result = PipelineResult(task_id=100)
        await pipeline._analyze_with_llm(_task_data(100), MagicMock(), result)
        pipeline._analyze_root_cause.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_related_runs_llm(self):
        pipeline = _pipeline(
            cache_tasks=[_task_dict(999)]  # 无关单
        )
        pipeline._generate_labels = AsyncMock(return_value=[])
        pipeline._analyze_root_cause = AsyncMock(return_value=[{"cause_type": "x"}])
        result = PipelineResult(task_id=100)
        await pipeline._analyze_with_llm(_task_data(100), MagicMock(), result)
        pipeline._analyze_root_cause.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_related_without_conclusion_runs_llm(self):
        # 关联单存在但主单未复盘（provider 返回无结论记录）-> 照常 LLM
        empty_rec = {"urId": 200, "root_causes": []}
        pipeline = _pipeline(
            provider=lambda tid: empty_rec if tid == 200 else None,
        )
        pipeline._generate_labels = AsyncMock(return_value=[])
        pipeline._analyze_root_cause = AsyncMock(return_value=[{"cause_type": "x"}])
        result = PipelineResult(task_id=100)
        await pipeline._analyze_with_llm(_task_data(100), MagicMock(), result)
        pipeline._analyze_root_cause.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_content_strong_reuses_without_issue_no(self):
        # 无 issue_no 时内容相似度层兜底（title/desc 完全一致 + 主单已复盘）
        def provider(tid: int) -> dict[str, Any] | None:
            return MASTER_REC if tid == 200 else None

        pipeline = _pipeline(provider=provider, issue_provider=lambda _tid: None)  # noqa: ARG005
        result = PipelineResult(task_id=100)
        reused = await pipeline._try_reuse_related_conclusion(_task_dict(100), result)
        assert reused is True
        assert result.conclusion_review is not None
        assert result.conclusion_review["reused_from"]["source"] == "content"
