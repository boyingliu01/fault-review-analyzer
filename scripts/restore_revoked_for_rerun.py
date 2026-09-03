"""恢复被复审撤销的结论单到复审前快照（2026-09-03 返工重跑前置）。

背景：第一轮批量重审（备份目录 conclusions_rerun_backup_20260903_103737）
中 219 条结论被撤销，涉及 129 单（92 全撤 pending_rebuild + 37 部分撤）。
细分显示 68% 属裁决基准错位误撤：材料只喂 + 行缺修复前代码（77 条）、
截图证据未入材料（11 次）、prompt 缺裁决纪律条款。返工（master 50c3655）
补全材料并写入裁决纪律后，需将撤销单恢复到复审前快照再重审：

- 恢复范围：conclusion_review.revoked 非空的单据（撤销单）
- 不动：全保留单（revoked 为空）与未复审单（含空结论单 11843609）
- 恢复源：复审前快照（无 conclusion_review、root_causes 为原值）——
  直接覆盖后幂等续跑逻辑自动将其视为「未复审」纳入重审

用法:
    python scripts/restore_revoked_for_rerun.py --dry-run   # 只核对清单
    python scripts/restore_revoked_for_rerun.py             # 执行回灌
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

ROOT = Path(__file__).parent.parent
OUT_DIR = ROOT / "output"
BACKUP_DIR = OUT_DIR / "conclusions_rerun_backup_20260903_103737"


def load_json(fp: Path) -> dict[str, Any] | None:
    """读 JSON 文件，损坏/缺失返回 None（不中断批量核对）。"""
    try:
        value: Any = json.loads(fp.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 损坏文件只记录不中断
        return None
    return value if isinstance(value, dict) else None


def main() -> None:
    parser = argparse.ArgumentParser(description="恢复被撤销结论单到复审前快照")
    parser.add_argument("--dry-run", action="store_true", help="只核对清单不写回")
    parser.add_argument(
        "--backup-dir",
        default=str(BACKUP_DIR),
        help="复审前快照目录（默认 conclusions_rerun_backup_20260903_103737）",
    )
    args = parser.parse_args()
    backup_dir = Path(args.backup_dir)
    if not backup_dir.is_dir():
        print(f"备份目录不存在: {backup_dir}")
        sys.exit(1)

    to_restore: list[int] = []
    kept_ids: list[int] = []
    out_of_scope: list[int] = []
    for fp in sorted(OUT_DIR.glob("progress_*.json")):
        rec = load_json(fp)
        if rec is None:
            out_of_scope.append(-1)
            continue
        try:
            urid = int(str(rec.get("urId")))
        except (TypeError, ValueError):
            out_of_scope.append(-1)
            continue
        review = rec.get("conclusion_review") or {}
        if not review.get("reviewed_at"):
            # 未复审（空结论单 11843609 等），不在恢复范围
            out_of_scope.append(urid)
            continue
        if review.get("revoked"):
            to_restore.append(urid)
        else:
            kept_ids.append(urid)

    print(f"待恢复（撤销单）: {len(to_restore)} 单")
    print(f"不动（全保留单）: {len(kept_ids)} 单")
    print(f"不在范围（未复审/异常）: {len(out_of_scope)} 单 -> {out_of_scope}")
    if args.dry_run:
        print(f"撤销单清单: {to_restore}")
        return

    restored: list[int] = []
    broken: list[int] = []
    for urid in to_restore:
        snap = load_json(backup_dir / f"progress_{urid}.json")
        # 快照校验：必须可解析、无复审痕迹、结论原值非空，否则拒绝覆盖
        if (
            snap is None
            or (snap.get("conclusion_review") or {}).get("reviewed_at")
            or not snap.get("root_causes")
        ):
            broken.append(urid)
            continue
        shutil.copyfile(backup_dir / f"progress_{urid}.json", OUT_DIR / f"progress_{urid}.json")
        restored.append(urid)

    print(f"已恢复 {len(restored)} 单到复审前快照")
    if broken:
        print(f"快照异常未恢复 {len(broken)} 单: {broken}")
        sys.exit(1)


if __name__ == "__main__":
    main()
