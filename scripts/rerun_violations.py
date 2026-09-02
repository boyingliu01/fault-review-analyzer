"""重算全部 progress 的 violations 字段（不重跑 LLM）。

背景：A1/A2/A3/A7 修复（diff 新增行过滤、security-001 正则收紧、
J000025 多线程上下文检测、规则级 flags）后，progress 数据中的
violations 基于旧检测逻辑，需用修复后逻辑重算；root_causes 等其他
字段保持不变。

数据源: data/cache.db（原始 task 数据，含 commit diff）
输出:   就地更新 output/progress_<urId>.json（更新前整目录备份）

用法:
    python scripts/rerun_violations.py
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analysis.violation_detector import ViolationDetector
from src.knowledge.manager import StandardsManager
from src.rules.engine import RulesEngine
from src.utils.diff_utils import extract_added_lines

ROOT = Path(__file__).parent.parent
OUT_DIR = ROOT / "output"
# 真实缓存库位于 data/cache/（config.cache.storage 指向该目录）
CACHE_DB_CANDIDATES = [ROOT / "data" / "cache" / "cache.db", ROOT / "data" / "cache.db"]


def load_task_from_cache(task_id: int) -> dict[str, Any] | None:
    """直接读 cache.db 原始数据（绕过 TTL 过期检查）。"""
    db_path = next((p for p in CACHE_DB_CANDIDATES if p.exists()), None)
    if db_path is None:
        return None
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT data FROM cache WHERE task_id = ?", (task_id,)).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    data: dict[str, Any] = json.loads(row[0])
    return data


def compute_violations(
    task_data: dict[str, Any], detector: ViolationDetector
) -> list[dict[str, Any]]:
    """复现 pipeline 的违规生成路径：RulesEngine.check + ViolationDetector.detect。

    顺序与 pipeline 一致：规则引擎违规在前，ViolationDetector 违规追加在后。
    """
    rule_violations: list[dict[str, Any]] = [
        {
            "rule_id": v.rule_id,
            "rule_name": v.rule_name,
            "severity": v.severity,
            "message": v.message,
            "evidence": v.evidence,
        }
        for v in RulesEngine().check(task_data)
    ]

    # ViolationDetector 输入与 pipeline._analyze_code_changes 一致：新增行拼接
    dev = task_data.get("development") or {}
    parts: list[str] = []
    for commit in dev.get("commits", []):
        diff = commit.get("diff", "")
        if diff:
            parts.append(extract_added_lines(diff))
    diff_content = "\n".join(parts)

    if diff_content:
        detection = detector.detect(
            {
                "task_id": task_data.get("task_id", 0),
                "title": task_data.get("title", ""),
                "description": task_data.get("description", ""),
                "code_snippet": diff_content,
            }
        )
        if detection.is_violation:
            # 逐规则对齐输出（rule_details 与 pipeline._detect_violations 一致）：
            # 旧实现所有规则共用 violation_types[0]，多规则命中时 message 错位
            if detection.rule_details:
                for detail in detection.rule_details:
                    rule_violations.append(
                        {
                            "rule_id": detail.get("rule_id", ""),
                            "rule_name": detail.get("pattern_key", ""),
                            "severity": "warning",
                            "message": detail.get("description", ""),
                            "evidence": detail.get("evidence", []),
                        }
                    )
            else:
                for rule_label in detection.violated_rules:
                    segs = rule_label.split(":", 1) if ":" in rule_label else ["", rule_label]
                    rule_id = segs[0] if len(segs) > 1 else ""
                    rule_name = segs[1] if len(segs) > 1 else segs[0]
                    rule_violations.append(
                        {
                            "rule_id": rule_id,
                            "rule_name": rule_name,
                            "severity": "warning",
                            "message": detection.violation_type or "",
                            "evidence": [detection.evidence] if detection.evidence else [],
                        }
                    )

    return rule_violations


def main() -> None:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = OUT_DIR / f"violations_rerun_backup_{ts}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    detector = ViolationDetector(StandardsManager())

    progress_files = sorted(OUT_DIR.glob("progress_*.json"))
    updated = 0
    changed = 0
    rule_counter: dict[str, int] = {}
    no_cache: list[int] = []
    before_total = 0
    after_total = 0

    for fp in progress_files:
        rec = json.loads(fp.read_text(encoding="utf-8"))
        urid = rec.get("urId")
        if not urid or rec.get("error") or not rec.get("root_causes"):
            continue
        shutil.copyfile(fp, backup_dir / fp.name)

        task_data = load_task_from_cache(int(urid))
        if task_data is None:
            no_cache.append(int(urid))
            continue

        before_total += len(rec.get("violations") or [])
        new_violations = compute_violations(task_data, detector)
        after_total += len(new_violations)
        for v in new_violations:
            rid = v["rule_id"]
            rule_counter[rid] = rule_counter.get(rid, 0) + 1

        if new_violations != (rec.get("violations") or []):
            changed += 1
        rec["violations"] = new_violations
        rec["violations_recomputed_at"] = ts
        fp.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        updated += 1

    print(f"更新 {updated} 个 progress；violations 有变化的 {changed} 个")
    print(f"违规总数: {before_total} -> {after_total}")
    print(f"规则分布: {rule_counter}")
    if no_cache:
        print(f"缓存缺失（保留原值）: {no_cache}")
    print(f"备份目录: {backup_dir}")


if __name__ == "__main__":
    main()
