"""结论复用器：从单记录整体替换为主单结论 + 复审状态。

复用语义（用户裁定）：主单结论已通过 Delphi 复审，从单直接取用相同结论
与复审状态并标记 reused_from 审计，保证重复单复盘结论完全一致。
"""

from __future__ import annotations

import copy
from datetime import datetime
from typing import Any

from src.analyzer.duplicate.detector import RelatedPair  # noqa: TC001


def apply_reused_conclusion(
    slave_rec: dict[str, Any],
    master_rec: dict[str, Any],
    pair: RelatedPair,
) -> dict[str, Any]:
    """把主单结论与复审状态复用到从单，返回新记录（纯函数，不改入参）。

    - root_causes / conclusion_review / deep_root_causes 整体取自主单
      （深拷贝隔离，后续从单操作不串扰主单）
    - conclusion_review.reused_from 记录复用审计（主单号、识别来源、
      相似度证据、复用时间）
    - violations / improvements / image_evidence 等从单自身字段零污染
    """
    out = dict(slave_rec)
    out["root_causes"] = copy.deepcopy(master_rec.get("root_causes") or [])
    review = copy.deepcopy(master_rec.get("conclusion_review") or {})
    review["reused_from"] = {
        "master_urId": master_rec.get("urId") or pair.master_id,
        "source": pair.source,
        "title_sim": pair.title_sim,
        "desc_sim": pair.desc_sim,
        "diff_sim": pair.diff_sim,
        "reused_at": datetime.now().isoformat(timespec="seconds"),
    }
    out["conclusion_review"] = review
    if master_rec.get("deep_root_causes"):
        out["deep_root_causes"] = copy.deepcopy(master_rec["deep_root_causes"])
    return out
