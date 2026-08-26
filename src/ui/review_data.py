"""复盘分析结果数据加载 - 从 output/progress_*.json 读取 181 起分析结果。"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

_OUT_DIR = Path(__file__).parent.parent.parent / "output"


def load_review_records() -> dict[int, dict[str, Any]]:
    """加载所有复盘分析结果（progress_*.json）。"""
    recs: dict[int, dict[str, Any]] = {}
    for fp in _OUT_DIR.glob("progress_*.json"):
        try:
            with fp.open(encoding="utf-8") as fh:
                rec = json.load(fh)
            if rec.get("urId"):
                recs[rec["urId"]] = rec
        except Exception:
            continue
    return recs


def primary_cause(rec: dict[str, Any]) -> str:
    """获取首要根因类型。"""
    rcs = rec.get("root_causes", [])
    if not rcs:
        return "无根因"
    return rcs[0].get("cause_type", "未知")


def build_summary_df(recs: dict[int, dict[str, Any]]) -> pd.DataFrame:
    """构建根因分布统计。"""
    cause_counter = Counter(primary_cause(rec) for rec in recs.values())
    df = pd.DataFrame(
        [
            {"根因类型": cause, "缺陷数": cnt, "占比(%)": round(cnt / len(recs) * 100, 1)}
            for cause, cnt in cause_counter.most_common()
        ]
    )
    return df


def build_violation_df(recs: dict[int, dict[str, Any]]) -> pd.DataFrame:
    """构建规范违规分布。"""
    rule_counter: Counter[str] = Counter()
    for rec in recs.values():
        for v in rec.get("violations", []):
            rule_counter[v.get("rule_id", "未知")] += 1
    return pd.DataFrame(
        [{"规范条款": r, "违规次数": c} for r, c in rule_counter.most_common()]
    )


def build_detail_df(recs: dict[int, dict[str, Any]]) -> pd.DataFrame:
    """构建缺陷明细表（支持筛选）。"""
    rows = []
    for u, rec in recs.items():
        rcs = rec.get("root_causes", [])
        imps = rec.get("improvements", [])
        viols = rec.get("violations", [])
        rows.append(
            {
                "urId": u,
                "标题": rec.get("title", ""),
                "首要根因": primary_cause(rec),
                "根因数": len(rcs),
                "根因摘要": "; ".join(
                    f"{rc.get('cause_type','')}:{rc.get('description','')[:60]}"
                    for rc in rcs[:2]
                ),
                "规范违规": "; ".join(v.get("rule_id", "") for v in viols),
                "违规数": len(viols),
                "改进建议数": len(imps),
                "改进建议摘要": "; ".join(
                    f"[{imp.get('priority','')}]{imp.get('measure','')[:50]}"
                    for imp in imps[:3]
                ),
                "有代码变更": "是" if rec.get("has_code_change") else "否",
                "处理耗时(秒)": round(rec.get("processing_time", 0), 1),
            }
        )
    return pd.DataFrame(rows)


def get_detail_by_urid(recs: dict[int, dict[str, Any]], urid: int) -> dict[str, Any]:
    """获取单起缺陷的完整详情。"""
    rec = recs.get(urid)
    if not rec:
        return {}
    return rec
