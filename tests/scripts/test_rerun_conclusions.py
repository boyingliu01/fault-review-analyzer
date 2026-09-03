"""rerun_conclusions.py 批量结论重审不变量锁定（sprint-20260902-77 SLICE-5）。

- REQ-7 幂等续跑：已含 conclusion_review.reviewed_at 的单据跳过（中断重跑
  不重复消费 LLM）；force=True 可强制重审
- 字段保护：读-改-写仅触 root_causes / conclusion_review 两个键，
  violations/delphi_review/improvements 等其他字段零污染
- 人工终裁叠加：重审时旧记录 manual_review 迁移保留（人工结论不丢）
- 失败清单：缓存与注入 loader 均无数据 → failed，原文件不被改动
- INV-4 灰度：脚本编程传参 ConclusionReviewConfig(enabled=True)，
  config.yaml 的 conclusion_review.enabled 保持 false 不落盘
"""

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from scripts.rerun_conclusions import run_conclusion_review

ROOT = Path(__file__).parent.parent.parent


def _rec(urid: int = 1001, with_review: bool = False) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "urId": urid,
        "title": "订单导出失败",
        "root_causes": [
            {
                "cause_type": "设计缺陷",
                "description": "查询未做分页导致全量加载超时",
                "evidence": ["return orderMapper.queryAll();"],
            }
        ],
        "violations": [{"rule_id": "J000025", "rule_name": "线程安全"}],
        "delphi_review": {"reviewed_at": "t0", "method": "m", "items": []},
        "improvements": [{"priority": "high", "measure": "加索引"}],
    }
    if with_review:
        rec["conclusion_review"] = {
            "reviewed_at": "2026-09-01T00:00:00",
            "method": "delphi_multi_expert_consensus",
            "items": [],
            "manual_review": {"reviewer": "人工", "items": [{"cause_type": "设计缺陷"}]},
        }
    return rec


def _review_record(verdicts: list[str], reason: str = "r") -> dict[str, Any]:
    items = [
        {
            "cause_type": "设计缺陷",
            "description": "查询未做分页导致全量加载超时",
            "final_verdict": v,
            "consensus": True,
            "rounds": 1,
            "reason": reason,
            "opinions": [
                {"reviewer": "a", "round": 1, "verdict": v, "reason": reason, "key_evidence": "e"}
            ],
        }
        for v in verdicts
    ]
    return {"reviewed_at": "t", "method": "delphi_multi_expert_consensus", "items": items}


def _write_progress(out_dir: Path, urid: int, rec: dict[str, Any]) -> Path:
    fp = out_dir / f"progress_{urid}.json"
    fp.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    return fp


def _reviewer(record: dict[str, Any]) -> Any:
    fake = AsyncMock()
    fake.review = AsyncMock(return_value=record)
    return fake


async def _loader_ok(task_id: int) -> dict[str, Any] | None:
    return {
        "task_id": task_id,
        "title": "订单导出失败",
        "description": "导出超时",
        "development": None,
    }


async def _loader_miss(task_id: int) -> dict[str, Any] | None:
    return None


class TestRunConclusionReview:
    """批量重审核心行为（REQ-7）。"""

    @pytest.mark.asyncio
    async def test_idempotent_skip_reviewed(self, tmp_path: Path):
        """已复审单据跳过且不消费 LLM（中断可恢复）。"""
        fp = _write_progress(tmp_path, 1001, _rec(with_review=True))
        reviewer = _reviewer(_review_record(["refuted"]))
        stats = await run_conclusion_review(tmp_path, reviewer, task_loader=_loader_ok)
        assert stats["skipped"] == [1001] and not stats["completed"]
        reviewer.review.assert_not_awaited()
        assert json.loads(fp.read_text(encoding="utf-8")) == _rec(with_review=True)

    @pytest.mark.asyncio
    async def test_skips_empty_conclusions(self, tmp_path: Path):
        """无结论单据跳过（空单无复审候选）。"""
        rec = _rec(urid=1002)
        rec["root_causes"] = []
        _write_progress(tmp_path, 1002, rec)
        reviewer = _reviewer(_review_record([]))
        stats = await run_conclusion_review(tmp_path, reviewer, task_loader=_loader_ok)
        assert stats["skipped"] == [1002]
        reviewer.review.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_completed_updates_only_two_keys(self, tmp_path: Path):
        """读-改-写仅触 root_causes/conclusion_review，其他字段零污染。"""
        fp = _write_progress(tmp_path, 1001, _rec())
        before = _rec()
        reviewer = _reviewer(_review_record(["confirmed"]))
        stats = await run_conclusion_review(tmp_path, reviewer, task_loader=_loader_ok)
        assert stats["completed"] == [1001]
        after = json.loads(fp.read_text(encoding="utf-8"))
        assert after["violations"] == before["violations"]
        assert after["delphi_review"] == before["delphi_review"]
        assert after["improvements"] == before["improvements"]
        assert after["root_causes"][0]["conclusion_verdict"] == "confirmed"
        assert after["conclusion_review"]["revoked"] == []

    @pytest.mark.asyncio
    async def test_full_revoke_marks_pending_rebuild(self, tmp_path: Path):
        """全单撤销 → root_causes 清空 + pending_rebuild 标记。"""
        fp = _write_progress(tmp_path, 1001, _rec())
        reviewer = _reviewer(_review_record(["refuted"], reason="反证不足"))
        await run_conclusion_review(tmp_path, reviewer, task_loader=_loader_ok)
        after = json.loads(fp.read_text(encoding="utf-8"))
        assert after["root_causes"] == []
        assert after["conclusion_review"]["conclusion_status"] == "pending_rebuild"
        assert after["conclusion_review"]["revoked"][0]["conclusion_reason"] == "反证不足"

    @pytest.mark.asyncio
    async def test_manual_review_carried_over_on_force(self, tmp_path: Path):
        """force 重审时旧人工终裁迁移保留（人工结论不丢）。"""
        fp = _write_progress(tmp_path, 1001, _rec(with_review=True))
        reviewer = _reviewer(_review_record(["confirmed"]))
        await run_conclusion_review(tmp_path, reviewer, task_loader=_loader_ok, force=True)
        after = json.loads(fp.read_text(encoding="utf-8"))
        assert after["conclusion_review"]["manual_review"] == {
            "reviewer": "人工",
            "items": [{"cause_type": "设计缺陷"}],
        }

    @pytest.mark.asyncio
    async def test_failed_list_on_loader_miss(self, tmp_path: Path):
        """缓存与 loader 均无数据 → failed 清单，原文件不被改动。"""
        fp = _write_progress(tmp_path, 1003, _rec(urid=1003))
        before = fp.read_text(encoding="utf-8")
        reviewer = _reviewer(_review_record(["confirmed"]))
        stats = await run_conclusion_review(tmp_path, reviewer, task_loader=_loader_miss)
        assert stats["failed"] == [1003]
        reviewer.review.assert_not_awaited()
        assert fp.read_text(encoding="utf-8") == before

    @pytest.mark.asyncio
    async def test_backup_created_before_write(self, tmp_path: Path):
        """写回前先备份原文件（可恢复）。"""
        _write_progress(tmp_path, 1001, _rec())
        reviewer = _reviewer(_review_record(["confirmed"]))
        stats = await run_conclusion_review(tmp_path, reviewer, task_loader=_loader_ok)
        assert stats["completed"] == [1001]
        backups = list(tmp_path.glob("conclusions_rerun_backup_*/progress_1001.json"))
        assert len(backups) == 1
        backup_rec = json.loads(backups[0].read_text(encoding="utf-8"))
        assert "conclusion_review" not in backup_rec

    @pytest.mark.asyncio
    async def test_reviewer_error_flagged(self, tmp_path: Path):
        """全专家失败（opinions 全 reviewer_error 前缀）→ 可观测标注。"""
        fp = _write_progress(tmp_path, 1001, _rec())
        record = _review_record(["diverged"])
        for item in record["items"]:
            for op in item["opinions"]:
                op["reason"] = "reviewer_error: net timeout"
        reviewer = _reviewer(record)
        await run_conclusion_review(tmp_path, reviewer, task_loader=_loader_ok)
        after = json.loads(fp.read_text(encoding="utf-8"))
        assert after["conclusion_review"]["reviewer_error"] is True
        assert after["root_causes"][0]["conclusion_verdict"] == "diverged"


class TestExplicitConfig:
    """INV-4 灰度：显式启用走编程传参，yaml 保持关闭。"""

    def test_yaml_conclusion_review_disabled(self):
        """config.yaml conclusion_review.enabled 保持 false（脚本不落 yaml）。"""
        text = (ROOT / "config" / "config.yaml").read_text(encoding="utf-8")
        assert "conclusion_review:" in text
        assert "enabled: false" in text.split("conclusion_review:", 1)[1].split("\n\n", 1)[0]


class TestWalkthroughRework:
    """code-walkthrough 返工锁定（C1 diff 拼接 / M1 urId 容错 / M2 失败标注 / M3 失败重试）。"""

    def test_build_fault_info_joins_added_lines(self):
        """C1：extract_added_lines 返回 str，须整段拼接而非逐字符迭代。"""
        from scripts.rerun_conclusions import build_fault_info

        task = {
            "task_id": 1,
            "title": "订单导出失败",
            "description": None,
            "development": {
                "commits": [
                    {
                        "diff": (
                            "--- a/A.java\n+++ b/A.java\n@@ -1,2 +1,3 @@\n"
                            " context\n-removed\n+return orderMapper.queryAll();\n+// added"
                        )
                    }
                ]
            },
        }
        info = build_fault_info(task)
        assert info["code_snippet"].splitlines() == [
            "return orderMapper.queryAll();",
            "// added",
        ]

    @pytest.mark.asyncio
    async def test_failed_list_on_non_numeric_urid(self, tmp_path: Path):
        """M1：非数字 urId 不崩溃，记入失败清单继续批量。"""
        (tmp_path / "progress_bad.json").write_text(
            json.dumps({"urId": "abc", "root_causes": []}), encoding="utf-8"
        )
        reviewer = _reviewer(_review_record(["confirmed"]))
        stats = await run_conclusion_review(tmp_path, reviewer, task_loader=_loader_ok)
        assert stats["failed"] == [-1]
        reviewer.review.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_reviewer_error_prefixes_extended(self, tmp_path: Path):
        """M2：全专家失败标注覆盖全部兜底前缀（含解析失败/非法 verdict）。"""
        from src.analyzer.review.base import FAILURE_REASON_PREFIXES

        assert FAILURE_REASON_PREFIXES == (
            "reviewer_error",
            "unparseable_response",
            "invalid_verdict",
            "review_error",
        )
        fp = _write_progress(tmp_path, 1001, _rec())
        record = _review_record(["diverged"])
        for item in record["items"]:
            for op in item["opinions"]:
                op["reason"] = "unparseable_response: not json"
        reviewer = _reviewer(record)
        await run_conclusion_review(tmp_path, reviewer, task_loader=_loader_ok)
        after = json.loads(fp.read_text(encoding="utf-8"))
        assert after["conclusion_review"]["reviewer_error"] is True

    @pytest.mark.asyncio
    async def test_retries_reviewer_error_on_rerun(self, tmp_path: Path):
        """M3：全专家失败单据不固化为已复审，续跑自动重试。"""
        rec = _rec(with_review=True)
        rec["conclusion_review"]["reviewer_error"] = True
        _write_progress(tmp_path, 1001, rec)
        reviewer = _reviewer(_review_record(["confirmed"]))
        stats = await run_conclusion_review(tmp_path, reviewer, task_loader=_loader_ok)
        assert stats["completed"] == [1001]
        reviewer.review.assert_awaited_once()
