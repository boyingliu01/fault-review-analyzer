"""重算 181 单 improvements（改进措施去重）。

背景：ImprovementRecommender 按 (category, priority) 选模板，不同根因文本
命中同一模板时产生重复措施（93/181 单存在单内重复）。生成层已增加
_merge_duplicate_measures 合并逻辑，本脚本从 progress 中的 root_causes +
violations 离线重算 improvements 并就地更新（与 pipeline._generate_improvements
逻辑一致），无需重跑 LLM。

用法:
    python scripts/rerun_improvements.py
"""

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(r"E:\Study\LLM\Bug聚类分析")
sys.path.insert(0, str(ROOT))

from src.analysis.improvement_recommender import ImprovementRecommender  # noqa: E402

OUT = ROOT / "output"


def compute_improvements(rec: dict) -> list[dict]:
    """复现 pipeline._generate_improvements（改进后含合并去重）。"""
    root_causes: list[str] = []
    for rc in rec.get("root_causes") or []:
        cause = rc.get("cause_type") or rc.get("description")
        if cause:
            root_causes.append(str(cause))
    if not root_causes:
        return []

    violation_causes: list[str] = []
    rule_ids_by_cause: dict[str, list[str]] = {}
    for v in rec.get("violations") or []:
        name = v.get("rule_name") or v.get("rule_id")
        if not name:
            continue
        name_str = str(name)
        violation_causes.append(name_str)
        rule_id = v.get("rule_id")
        if rule_id:
            rule_ids_by_cause.setdefault(name_str, []).append(str(rule_id))

    recommender = ImprovementRecommender()
    measures = recommender.recommend_measures(
        root_causes=root_causes,
        violation_causes=violation_causes or None,
        top_n=5,
        rule_ids_by_cause=rule_ids_by_cause or None,
    )
    return [
        {
            "root_cause": m.root_cause,
            "measure": m.measure,
            "acceptance_criteria": m.acceptance_criteria,
            "expected_impact": m.expected_impact,
            "priority": m.priority,
            "category": m.category,
            "rule_ids": m.rule_ids,
        }
        for m in measures
    ]


def has_duplicate(imps: list[dict]) -> bool:
    keys = [(i.get("category"), i.get("priority"), i.get("measure")) for i in imps]
    return len(set(keys)) < len(keys)


def main() -> None:
    backup_dir = OUT / f"improvements_dedupe_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    backup_dir.mkdir(exist_ok=True)

    total = 0
    changed = 0
    dup_before = 0
    dup_after = 0
    count_before = 0
    count_dist: dict[int, int] = {}

    for fp in sorted(OUT.glob("progress_*.json")):
        rec = json.loads(fp.read_text(encoding="utf-8"))
        if not rec.get("root_causes"):
            continue
        total += 1

        old_imps = rec.get("improvements") or []
        count_before += len(old_imps)
        if has_duplicate(old_imps):
            dup_before += 1

        new_imps = compute_improvements(rec)
        if has_duplicate(new_imps):
            dup_after += 1

        if old_imps != new_imps:
            changed += 1
            shutil.copyfile(fp, backup_dir / fp.name)
            rec["improvements"] = new_imps
            rec["improvements_deduped_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            fp.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")

        count_dist[len(new_imps)] = count_dist.get(len(new_imps), 0) + 1

    print(f"处理单数: {total}")
    print(f"improvements 有变化: {changed} 单（备份至 {backup_dir.name}）")
    print(f"条数: {count_before} -> {sum(k * v for k, v in count_dist.items())}")
    print(f"单内重复: {dup_before} 单 -> {dup_after} 单")
    print(f"重算后条数分布: {dict(sorted(count_dist.items()))}")


if __name__ == "__main__":
    main()
