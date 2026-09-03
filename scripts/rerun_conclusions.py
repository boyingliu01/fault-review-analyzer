"""批量重审复盘结论（结论域 Delphi 多专家复审，sprint-20260902-77 SLICE-5）。

对 output/progress_*.json 中含复盘结论（root_causes）的单据执行结论域
Delphi 复审（双模型交叉专家），共识撤销的结论移出主列表并记入
conclusion_review.revoked 审计；全单撤销标记 pending_rebuild 待人工重建。

行为契约（tests/scripts/test_rerun_conclusions.py 锁定）：
1. 幂等续跑：已含 conclusion_review.reviewed_at 的单据跳过（中断重跑
   不重复消费 LLM）；--force 强制重审（人工终裁 manual_review 迁移保留）
2. 字段保护：读-改-写仅触 root_causes / conclusion_review 两个键，
   violations/delphi_review/improvements 等其他字段零污染
3. 失败清单：任务数据不可得 → failed 口径，原文件不被改动
4. 备份：写回前先复制原文件到 conclusions_rerun_backup_<ts>/
5. INV-4 灰度：编程传参 ConclusionReviewConfig(enabled=True)，
   不落 config.yaml（yaml 的 conclusion_review.enabled 保持 false）

用法:
    python scripts/rerun_conclusions.py              # 仅缓存，miss 入失败清单
    python scripts/rerun_conclusions.py --fetch-api  # 缓存 miss 时 API 重拉
    python scripts/rerun_conclusions.py --force      # 强制重审已复审单据
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analyzer.review import ConclusionReviewer, apply_conclusion_review
from src.config.manager import ConfigManager
from src.config.models import ConclusionReviewConfig
from src.utils.diff_utils import extract_added_lines

ROOT = Path(__file__).parent.parent
OUT_DIR = ROOT / "output"

TaskLoader = Callable[[int], Awaitable[dict[str, Any] | None]]


def load_task_from_cache(task_id: int) -> dict[str, Any] | None:
    """从本地缓存读任务数据（与 rerun_violations 同一数据源）。"""
    import sqlite3

    db = ROOT / "data" / "cache" / "cache.db"
    if not db.exists():
        return None
    conn = sqlite3.connect(db)
    try:
        row = conn.execute("SELECT data FROM cache WHERE task_id = ?", (task_id,)).fetchone()
    finally:
        conn.close()
    return json.loads(row[0]) if row else None


async def _cache_only_loader(task_id: int) -> dict[str, Any] | None:
    """默认 loader：仅查缓存（miss 由调用方记入失败清单）。"""
    return load_task_from_cache(task_id)


def _fetch_api_loader(api_config: Any) -> TaskLoader:
    """构造缓存 miss 时 API 重拉 loader（--fetch-api 模式）。"""
    from src.api.client import APIClient

    async def loader(task_id: int) -> dict[str, Any] | None:
        try:
            data = load_task_from_cache(task_id)
            if data is not None:
                return data
            client = APIClient(
                base_url=api_config.base_url,
                api_key=api_config.api_key,
                timeout=api_config.timeout,
                retry=api_config.retry,
            )
            try:
                task = await client.get_task(task_id)
            finally:
                await client.close()
            return task.model_dump(mode="json")
        except Exception as e:  # noqa: BLE001 单据拉取失败不阻断批量流程
            print(f"[{task_id}] 缓存与 API 均无数据: {type(e).__name__} {e}")
            return None

    return loader


def build_fault_info(task_data: dict[str, Any]) -> dict[str, Any]:
    """构建复审上下文（与 pipeline 违规域 fault_info 同构）。"""
    return {
        "task_id": task_data.get("task_id", 0),
        "title": task_data.get("title", "") or "",
        "description": (task_data.get("description", "") or "")[:500],
        "code_snippet": "\n".join(
            line
            for commit in (task_data.get("development") or {}).get("commits", [])
            if commit.get("diff")
            for line in extract_added_lines(commit["diff"])
        ),
    }


def _mark_reviewer_error(review: dict[str, Any]) -> None:
    """全专家连续失败（opinions 全为 reviewer_error 前缀兜底）→ 可观测标注。"""
    opinions = [op for item in review.get("items", []) for op in item.get("opinions", [])]
    if opinions and all(str(op.get("reason", "")).startswith("reviewer_error") for op in opinions):
        review["reviewer_error"] = True


async def run_conclusion_review(
    out_dir: Path,
    reviewer: Any,
    task_loader: TaskLoader,
    force: bool = False,
) -> dict[str, list[int]]:
    """批量重审 progress 中的复盘结论（幂等续跑 + 字段保护 + 失败清单）。

    Returns:
        三口径统计 {"completed": [...], "skipped": [...], "failed": [...]}（urId）。
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = out_dir / f"conclusions_rerun_backup_{ts}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stats: dict[str, list[int]] = {"completed": [], "skipped": [], "failed": []}

    for fp in sorted(out_dir.glob("progress_*.json")):
        try:
            rec = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 损坏文件不阻断批量流程
            print(f"[{fp.name}] 解析失败，记入失败清单")
            stats["failed"].append(-1)
            continue
        raw_urid = rec.get("urId")
        if not raw_urid:
            print(f"[{fp.name}] 缺 urId，记入失败清单")
            stats["failed"].append(-1)
            continue
        urid = int(raw_urid)

        # 幂等续跑：已复审且非强制 → 跳过（中断重跑不重复消费 LLM）
        old_review = rec.get("conclusion_review") or {}
        if old_review.get("reviewed_at") and not force:
            stats["skipped"].append(urid)
            continue
        # 空结论单无复审候选（pending_rebuild 待人工重建后再审）
        if not rec.get("root_causes"):
            stats["skipped"].append(urid)
            continue

        try:
            task_data = await task_loader(urid)
            if task_data is None:
                stats["failed"].append(urid)
                print(f"[{urid}] 任务数据不可得（缓存/loader 均无），保留原值")
                continue

            shutil.copyfile(fp, backup_dir / fp.name)

            review = await reviewer.review(build_fault_info(task_data), rec["root_causes"])
            kept, revoked = apply_conclusion_review(rec["root_causes"], review)
            review["revoked"] = revoked
            if not kept:
                review["conclusion_status"] = "pending_rebuild"
            if old_review.get("manual_review"):
                # 人工终裁叠加：重审迁移保留（人工结论不丢）
                review["manual_review"] = old_review["manual_review"]
            _mark_reviewer_error(review)

            # 字段保护：仅触 root_causes / conclusion_review 两个键
            rec["root_causes"] = kept
            rec["conclusion_review"] = review
            fp.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
            stats["completed"].append(urid)
            print(
                f"[{urid}] 完成: 保留 {len(kept)} 条，撤销 {len(revoked)} 条"
                + ("（全撤，待人工重建）" if not kept else "")
            )
        except Exception as e:  # noqa: BLE001 单据失败不阻断批量流程
            stats["failed"].append(urid)
            print(f"[{urid}] 失败: {type(e).__name__} {e}")

    return stats


async def _amain(args: argparse.Namespace) -> None:
    config = ConfigManager().get_config()
    # INV-4 灰度：编程传参显式启用，不落 config.yaml（yaml 保持 enabled: false）
    conclusion_cfg = ConclusionReviewConfig(enabled=True)
    reviewer = ConclusionReviewer(config.llm, conclusion_cfg)
    loader: TaskLoader = _fetch_api_loader(config.api) if args.fetch_api else _cache_only_loader
    stats = await run_conclusion_review(OUT_DIR, reviewer, loader, force=args.force)

    print(f"\n完成 {len(stats['completed'])} 单: {stats['completed']}")
    print(f"跳过 {len(stats['skipped'])} 单（已复审/无结论）: {stats['skipped']}")
    print(f"失败 {len(stats['failed'])} 单: {stats['failed']}")
    print("备份与审计: output/conclusions_rerun_backup_*/ 与各 progress 的 conclusion_review")


def main() -> None:
    parser = argparse.ArgumentParser(description="批量重审复盘结论（结论域 Delphi 复审）")
    parser.add_argument(
        "--fetch-api", action="store_true", help="缓存 miss 时通过 API 重拉任务数据"
    )
    parser.add_argument("--force", action="store_true", help="强制重审已复审单据（人工终裁保留）")
    asyncio.run(_amain(parser.parse_args()))


if __name__ == "__main__":
    main()
