"""存量重复单结论一致性校正（sprint-20260902-77 R9）。

对 output/progress_*.json 的存量记录执行三层重复单识别（issue no 相同 /
显式关系 / 内容相似度，见 src/analyzer/duplicate），strong 裁决的从单整体
复用主单结论与复审状态（reused_from 审计入案）；borderline 对出清单供
人工确认，不自动写回。

行为契约（tests/scripts/test_align_duplicate_conclusions.py 锁定）：
1. 幂等跳过：从单 conclusion_review.reused_from 已存在 -> 跳过不重写；
   主从反转对（原主单在对方 reused_from 中登记）同样跳过，审计链防环
2. 字段保护：从单 violations/improvements/image_evidence 等自身字段零污染
   （仅 root_causes/conclusion_review/deep_root_causes 取自主单）
3. 主单保障：master 记录无 root_causes -> 该对 skipped，不写回
4. 备份：写回前复制原文件到 duplicate_align_backup_<ts>/
5. borderline 清单：output/duplicate_borderline_<ts>.md，原文件不改动
6. dry-run：只统计不写回不备份不出清单文件

用法（worktree 引擎 + 主仓库数据，路径参数指向主仓库）:
    python scripts/align_duplicate_conclusions.py \
        --out-dir <主仓库>/output --cache-db <主仓库>/data/cache/cache.db \
        --issue-map "E:\\...\\新电泄漏缺陷完整复盘结论.xlsx" --dry-run
    python scripts/align_duplicate_conclusions.py ...   # 去掉 --dry-run 实际写回
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analyzer.duplicate.detector import (
    DuplicateDetector,
    TaskCandidate,
    candidate_from_task,
)
from src.analyzer.duplicate.issue_map import load_issue_map
from src.analyzer.duplicate.reuser import apply_reused_conclusion

ROOT = Path(__file__).parent.parent

CacheLoader = Callable[[int], dict[str, Any] | None]


def _load_cache_task(cache_db: Path) -> CacheLoader:
    """构造 cache 任务 loader（与 rerun_conclusions 同一数据源）。"""

    def loader(task_id: int) -> dict[str, Any] | None:
        import sqlite3

        if not cache_db.exists():
            return None
        conn = sqlite3.connect(cache_db)
        try:
            row = conn.execute(
                "SELECT data FROM cache WHERE task_id = ?", (task_id,)
            ).fetchone()
        finally:
            conn.close()
        return json.loads(row[0]) if row else None

    return loader


def _candidate_for(
    urid: int,
    rec: dict[str, Any],
    cache_loader: CacheLoader,
    issue_map: dict[int, str] | None,
) -> TaskCandidate:
    """组装识别候选：任务数据（缓存）+ progress 记录 + issue no。

    缓存 miss 时用 progress 自身 title 兜底（issue 层不依赖内容，仍可
    命中；内容层因描述缺失相似度趋低，安全降级为不命中）。
    """
    task_data = cache_loader(urid) or {"task_id": urid, "title": rec.get("title") or ""}
    issue_no = (issue_map or {}).get(urid, "")
    return candidate_from_task(task_data, rec, issue_no)


def align(
    out_dir: Path,
    cache_loader: CacheLoader,
    issue_map: dict[int, str] | None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """全量扫描 progress 记录并执行一致性校正，返回统计。

    reused/skipped 为 (master_urId, slave_urId) 元组列表；borderline 为
    RelatedPair 关键字摘要；failed 为解析失败文件名。
    """
    records: dict[int, tuple[Path, dict[str, Any]]] = {}
    failed: list[str] = []
    for fp in sorted(out_dir.glob("progress_*.json")):
        try:
            rec = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 损坏文件不阻断批量流程
            failed.append(fp.name)
            continue
        urid = rec.get("urId")
        if isinstance(urid, int):
            records[urid] = (fp, rec)

    candidates = [
        _candidate_for(urid, rec, cache_loader, issue_map)
        for urid, (_, rec) in sorted(records.items())
    ]
    pairs = DuplicateDetector().find_all_pairs(candidates)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = out_dir / f"duplicate_align_backup_{ts}"
    borderline: list[dict[str, Any]] = []
    reused: list[tuple[int, int]] = []
    skipped: list[tuple[int, int]] = []

    for pair in pairs:
        slave_entry = records.get(pair.slave_id)
        master_entry = records.get(pair.master_id)
        if slave_entry is None or master_entry is None:
            skipped.append((pair.master_id, pair.slave_id))
            continue
        slave_fp, slave_rec = slave_entry
        _, master_rec = master_entry
        if (slave_rec.get("conclusion_review") or {}).get("reused_from"):
            # 幂等：从单已复用过（重跑安全）
            skipped.append((pair.master_id, pair.slave_id))
            continue
        master_rf = (master_rec.get("conclusion_review") or {}).get("reused_from") or {}
        if master_rf.get("master_urId") == pair.slave_id:
            # 幂等（主从反转）：复用写回令从单继承复审状态，重跑时
            # resolve_master 重裁致方向反转，原主单被误判为新从单；
            # 该对第一轮已按相反方向校正，二次写回会令审计链成环
            skipped.append((pair.master_id, pair.slave_id))
            continue
        if pair.verdict != "strong" or not master_rec.get("root_causes"):
            # 主单结论缺失（如缓存清理过）：宁可重盘不空转
            if pair.verdict == "borderline":
                borderline.append(
                    {
                        "master_id": pair.master_id,
                        "slave_id": pair.slave_id,
                        "title_sim": pair.title_sim,
                        "desc_sim": pair.desc_sim,
                        "diff_sim": pair.diff_sim,
                        "verdict": pair.verdict,
                        "source": pair.source,
                    }
                )
            else:
                skipped.append((pair.master_id, pair.slave_id))
            continue

        reused.append((pair.master_id, pair.slave_id))
        if dry_run:
            continue
        backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(slave_fp, backup_dir / slave_fp.name)
        aligned = apply_reused_conclusion(slave_rec, master_rec, pair)
        tmp = slave_fp.with_suffix(".json.tmp")  # 原子写：中断不留半截 JSON
        tmp.write_text(json.dumps(aligned, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(slave_fp)
        print(
            f"[{pair.slave_id}] 复用主单 {pair.master_id} 结论"
            f"（source={pair.source}，t={pair.title_sim:.2f}/d={pair.desc_sim:.2f}/"
            f"f={pair.diff_sim:.2f}）"
        )

    if borderline and not dry_run:
        list_fp = out_dir / f"duplicate_borderline_{ts}.md"
        lines = [
            "# 重复单 borderline 清单（人工确认）",
            "",
            "| 从单 | 主单 | source | title_sim | desc_sim | diff_sim |",
            "|---|---|---|---|---|---|",
        ]
        lines.extend(
            f"| {b['slave_id']} | {b['master_id']} | {b['source']} "
            f"| {b['title_sim']:.2f} | {b['desc_sim']:.2f} | {b['diff_sim']:.2f} |"
            for b in borderline
        )
        list_fp.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return {
        "reused": reused,
        "skipped": skipped,
        "borderline": borderline,
        "failed": failed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="存量重复单结论一致性校正")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "output")
    parser.add_argument("--cache-db", type=Path, default=ROOT / "data" / "cache" / "cache.db")
    parser.add_argument(
        "--issue-map",
        type=Path,
        default=None,
        help="泄漏缺陷复盘映射 Excel（Incident sheet，urId->Issue No）；缺省仅内容层",
    )
    parser.add_argument("--dry-run", action="store_true", help="只统计不写回")
    args = parser.parse_args()

    issue_map = load_issue_map(args.issue_map) if args.issue_map else None
    stats = align(args.out_dir, _load_cache_task(args.cache_db), issue_map, args.dry_run)
    mode = "（dry-run）" if args.dry_run else ""
    print(f"\n复用 {len(stats['reused'])} 对{mode}: {stats['reused']}")
    print(f"跳过 {len(stats['skipped'])} 对: {stats['skipped']}")
    print(f"borderline {len(stats['borderline'])} 对（见清单）")
    for b in stats["borderline"]:
        print(
            f"  - 从单 {b['slave_id']} ~ 主单 {b['master_id']}（source={b['source']}, "
            f"t={b['title_sim']:.2f}/d={b['desc_sim']:.2f}/f={b['diff_sim']:.2f}）"
        )
    if stats["failed"]:
        print(f"解析失败 {len(stats['failed'])} 文件: {stats['failed']}")


if __name__ == "__main__":
    main()
