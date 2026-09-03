"""复盘分析结果数据加载 - 从 output/progress_*.json 读取分析结果，支持批次隔离、帕累托降序、研发云链接、规范条款内容。

数据来源:
- output/progress_*.json: 每起缺陷的分析结果
- output/all_analysis_*.json: 每次分析运行的批次汇总
- output/batches.json: 显式批次索引（可选）
- output/annotations.json: 批次批注（可选）
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

_OUT_DIR = Path(__file__).parent.parent.parent / "output"

# 研发云缺陷明细页 URL 模板（可用环境变量覆盖）
_DEFAULT_URL_TEMPLATE = "https://dev.iwhalecloud.com/portal/zcm-devspace/spa/task/pc/{urId}"

# 未归档批次名称
_UNFILED_BATCH_NAME = "⚠️ 未归档"


# ---------------------------------------------------------------------------
# 复盘记录加载
# ---------------------------------------------------------------------------
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
        # 结论域全撤单：区分"复审撤销待重建"与"本来无结论"（防统计口径混淆）
        if (rec.get("conclusion_review") or {}).get("conclusion_status") == "pending_rebuild":
            return "复审撤销待重建"
        return "无根因"
    return str(rcs[0].get("cause_type", "未知"))


# ---------------------------------------------------------------------------
# 批次加载与推断
# ---------------------------------------------------------------------------
def _read_all_analysis_batches() -> list[dict[str, Any]]:
    """从 all_analysis_*.json 文件名时间戳推断批次。"""
    batches: list[dict[str, Any]] = []
    for fp in sorted(_OUT_DIR.glob("all_analysis_*.json")):
        try:
            with fp.open(encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            continue

        def _keep_in_batch(r: dict[str, Any]) -> bool:
            if not r.get("urId") or r.get("error"):
                return False
            if r.get("root_causes"):
                return True
            # pending_rebuild 空结论单保留进批次（结论域复审不丢单）
            return (r.get("conclusion_review") or {}).get("conclusion_status") == "pending_rebuild"

        urids = [r.get("urId") for r in data.get("results", []) if _keep_in_batch(r)]
        if not urids:
            continue
        # 从文件名提取时间戳：all_analysis_YYYYMMDD_HHMMSS.json
        m = re.search(r"(\d{8})_(\d{6})", fp.stem)
        created_at = ""
        if m:
            try:
                created_at = datetime.strptime(
                    f"{m.group(1)} {m.group(2)}", "%Y%m%d %H%M%S"
                ).strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                created_at = ""
        batches.append(
            {
                "batch_id": f"batch-{m.group(1)}-{m.group(2)}" if m else f"batch-{fp.stem}",
                "name": f"分析批次 {created_at}" if created_at else fp.stem,
                "created_at": created_at,
                "source": fp.name,
                "urids": urids,
                "count": len(urids),
            }
        )
    return batches


def _infer_unfiled_batch(known_urids: set[int]) -> list[dict[str, Any]]:
    """孤儿 progress（不在任何已知批次中）归入未归档批次。"""
    all_urids = set(load_review_records().keys())
    orphan = sorted(all_urids - known_urids)
    if not orphan:
        return []
    return [
        {
            "batch_id": "batch-unfiled",
            "name": _UNFILED_BATCH_NAME,
            "created_at": "",
            "source": "progress_*.json（未归档）",
            "urids": orphan,
            "count": len(orphan),
        }
    ]


def load_batches() -> list[dict[str, Any]]:
    """加载批次列表（优先级：batches.json > all_analysis 推断 > 孤儿归并）。

    返回按 created_at 排序的批次列表。
    """
    # 1. 显式 batches.json
    batches: list[dict[str, Any]] = []
    batches_file = _OUT_DIR / "batches.json"
    if batches_file.exists():
        try:
            data = json.loads(batches_file.read_text(encoding="utf-8"))
            batches = data.get("batches", [])
        except Exception:
            batches = []  # 损坏则回退到自动推断

    # 2. 若无显式批次，从 all_analysis 推断
    if not batches:
        batches = _read_all_analysis_batches()

    # 3. 孤儿 progress 归入未归档批次
    known_urids = {u for b in batches for u in b.get("urids", [])}
    unfiled = _infer_unfiled_batch(known_urids)
    if unfiled:
        batches.extend(unfiled)

    # 排序：有 created_at 的按时间升序，无时间戳的排最后
    batches.sort(key=lambda b: b.get("created_at") or "9999")
    return batches


def save_batches(batches: list[dict[str, Any]]) -> None:
    """原子写批次索引（tmp + replace），按 batch_id 去重。"""
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    # 按 batch_id 去重（保留最后一次）
    dedup: dict[str, dict[str, Any]] = {}
    for b in batches:
        dedup[b["batch_id"]] = b
    payload = {"batches": list(dedup.values())}
    tmp_file = _OUT_DIR / "batches.json.tmp"
    tmp_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_file.replace(_OUT_DIR / "batches.json")


# ---------------------------------------------------------------------------
# 批次批注
# ---------------------------------------------------------------------------
def load_annotations() -> dict[str, list[dict[str, Any]]]:
    """加载批次批注，过滤掉不存在的 batch_id。"""
    annotations_file = _OUT_DIR / "annotations.json"
    if not annotations_file.exists():
        return {}
    try:
        data = json.loads(annotations_file.read_text(encoding="utf-8"))
        annotations = data.get("annotations", {})
    except Exception:
        return {}
    # 过滤掉不存在的 batch_id
    valid_ids = {b["batch_id"] for b in load_batches()}
    return {bid: anns for bid, anns in annotations.items() if bid in valid_ids}


def add_annotation(batch_id: str, text: str) -> None:
    """给指定批次添加一条批注。"""
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    annotations_file = _OUT_DIR / "annotations.json"
    if annotations_file.exists():
        try:
            data = json.loads(annotations_file.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    else:
        data = {}
    annotations = data.setdefault("annotations", {})
    anns = annotations.setdefault(batch_id, [])
    anns.append(
        {
            "id": f"a{int(datetime.now().timestamp() * 1000)}",
            "text": text,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    )
    tmp_file = _OUT_DIR / "annotations.json.tmp"
    tmp_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_file.replace(annotations_file)


# ---------------------------------------------------------------------------
# 研发云链接
# ---------------------------------------------------------------------------
def build_detail_url(urid: int) -> str:
    """生成研发云缺陷明细页链接。"""
    template = os.environ.get("RDEV_DETAIL_URL_TEMPLATE", _DEFAULT_URL_TEMPLATE)
    return template.replace("{urId}", str(urid))


# ---------------------------------------------------------------------------
# 统计 DataFrame 构建
# ---------------------------------------------------------------------------
def build_summary_df(recs: dict[int, dict[str, Any]]) -> pd.DataFrame:
    """构建根因分布统计（按缺陷数降序 + 累计占比，用于帕累托图）。"""
    if not recs:
        return pd.DataFrame(
            {col: pd.Series(dtype="int64") for col in ["根因类型", "缺陷数", "占比(%)"]}
            | {"累计占比(%)": pd.Series(dtype="float64")}
        )
    cause_counter = Counter(primary_cause(rec) for rec in recs.values())
    total = len(recs)
    items: list[tuple[str, int, float]] = [
        (cause, cnt, round(cnt / total * 100, 1)) for cause, cnt in cause_counter.items()
    ]
    items.sort(key=lambda x: x[1], reverse=True)
    df = pd.DataFrame([{"根因类型": c, "缺陷数": n, "占比(%)": p} for c, n, p in items])
    df["累计占比(%)"] = (df["缺陷数"].cumsum() / df["缺陷数"].sum() * 100).round(1)
    return df


def build_violation_df(recs: dict[int, dict[str, Any]]) -> pd.DataFrame:
    """构建规范违规分布（含条款内容，按 rule_id 聚合，rule_name 取首次值）。"""
    rule_counter: Counter[str] = Counter()
    rule_names: dict[str, str] = {}
    for rec in recs.values():
        for v in rec.get("violations", []):
            rid = v.get("rule_id", "未知")
            rule_counter[rid] += 1
            if rid not in rule_names:
                rule_names[rid] = v.get("rule_name", "")
    if not rule_counter:
        return pd.DataFrame(
            {"规范条款": pd.Series(dtype="object"), "条款内容": pd.Series(dtype="object")}
            | {"违规次数": pd.Series(dtype="int64")}
        )
    return pd.DataFrame(
        [
            {"规范条款": r, "条款内容": rule_names.get(r, ""), "违规次数": c}
            for r, c in rule_counter.most_common()
        ]
    )


def build_detail_df(recs: dict[int, dict[str, Any]]) -> pd.DataFrame:
    """构建缺陷明细表（含研发云链接列，支持筛选）。"""
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
                    f"{rc.get('cause_type', '')}:{rc.get('description', '')[:60]}" for rc in rcs[:2]
                ),
                "规范违规": "; ".join(v.get("rule_id", "") for v in viols),
                "违规数": len(viols),
                "改进建议数": len(imps),
                "改进建议摘要": "; ".join(
                    f"[{imp.get('priority', '')}]{imp.get('measure', '')[:50]}" for imp in imps[:3]
                ),
                "有代码变更": "是" if rec.get("has_code_change") else "否",
                "研发云链接": build_detail_url(u),
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
