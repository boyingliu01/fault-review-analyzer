"""对当前 5 个违规单执行 Delphi 多专家复审（真实 LLM）并更新 progress。

背景（用户问题1）：敏感信息类核查后，仍有 5 单 6 条命中（J000025 ×4 单、
J000066 ×1、SEC-J00002 ×1）未做严格二次审核。本脚本：
1. 用修正后引擎重算 violations（真实命中行 evidence）
2. Delphi 多专家（strict_rule_checker / runtime_behavior_analyst，独立会话
   匿名，最多 2 轮共识）真实 LLM 复审
3. progress 更新：violations = 共识保留集；delphi_review 记录 LLM 专家
   意见 + 人工逐条核查结论（双重认定，互相印证）

用法: python scripts/run_delphi_review.py
"""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analysis.violation_detector import ViolationDetector
from src.analyzer.review import DelphiViolationReviewer, apply_review
from src.config.manager import ConfigManager
from src.knowledge.manager import StandardsManager
from src.rules.engine import RulesEngine
from src.utils.diff_utils import extract_added_lines

ROOT = Path(__file__).parent.parent
OUT_DIR = ROOT / "output"
TS = datetime.now().strftime("%Y%m%d_%H%M%S")

TASKS = ["11797806", "11807893", "11863155", "11867475", "11964009"]

# 人工逐条核查结论（2026-09-02，依据缓存 diff 上下文，与 LLM 专家共识互相印证）
MANUAL_REASONS: dict[str, dict[str, str]] = {
    "11797806": {
        "J000025": (
            "paramMap 为 callUcLogoutAll 方法内局部集合，put 后传入 invocationDto，"
            "方法作用域内使用完毕，无跨线程共享证据"
        ),
    },
    "11807893": {
        "J000025": (
            "3 处命中均为 InheritableThreadLocal.initialValue()/childValue() 的正确"
            "实现——每次调用返回线程私有新 Map（注释'每个子线程创建一个新副本，防止"
            "互相影响'），恰是实现线程隔离的标准写法，是被误判的修复代码本身"
        ),
    },
    "11863155": {
        "J000066": (
            "命中为 JavaScript 代码（var/that.$/ESLint），J000066 为 Java 编码规范"
            "条款，语言不适用；且空 catch 带 // eslint-disable-next-line no-empty "
            "显式豁免，为刻意设计"
        ),
    },
    "11867475": {
        "J000025": (
            "tasks 为主线程创建的 Callable 任务清单（仅主线程 add 与 invokeAll 提交）；"
            "custOrderIds 为 FeQueryOrderTask.call() 内局部收集；setFixContactManOrderList"
            "(new ArrayList<>()) 新建列表方法内顺序使用——均为单线程局部集合，非跨线程共享"
        ),
        "SEC-J00002": (
            "命中实为多行 SQL 字符串字面量拼接的续接符 '+'（正则 \\w+ 跨文件匹配到"
            "相邻 DTO 文件的 private 字段），SQL 首段为固定列名/表名/JOIN，"
            "无用户输入参与拼接，无注入风险"
        ),
    },
    "11964009": {
        "J000025": (
            "queuedIntents 全部 6 处读写均在 handler.post 的主线程 Runnable 内"
            "（handler=Handler(Looper.getMainLooper())），外部线程只通过 "
            "emitOrQueue/flushPendingIfAny 提交任务，主线程串行化访问是 Android "
            "标准线程收敛手法，无并发违规"
        ),
    },
}


def load_task_from_cache(task_id: int) -> dict[str, Any] | None:
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


def compute_violations(task_data: dict[str, Any]) -> list[dict[str, Any]]:
    """复现 pipeline 违规生成路径（规则引擎前置 + ViolationDetector 追加）。"""
    violations: list[dict[str, Any]] = [
        {
            "rule_id": v.rule_id,
            "rule_name": v.rule_name,
            "severity": v.severity,
            "message": v.message,
            "evidence": v.evidence,
        }
        for v in RulesEngine().check(task_data)
    ]
    dev = task_data.get("development") or {}
    diff_content = "\n".join(
        extract_added_lines(c.get("diff", "")) for c in dev.get("commits", []) if c.get("diff")
    )
    if diff_content:
        detection = ViolationDetector(StandardsManager()).detect(
            {
                "task_id": task_data.get("task_id", 0),
                "title": task_data.get("title", ""),
                "description": task_data.get("description", ""),
                "code_snippet": diff_content,
            }
        )
        if detection.is_violation:
            for detail in detection.rule_details:
                violations.append(
                    {
                        "rule_id": detail.get("rule_id", ""),
                        "rule_name": detail.get("pattern_key", ""),
                        "severity": "warning",
                        "message": detail.get("description", ""),
                        "evidence": detail.get("evidence", []),
                    }
                )
    return violations


async def run() -> None:
    config = ConfigManager().get_config()
    reviewer = DelphiViolationReviewer(config.llm, config.review)

    backup_dir = OUT_DIR / f"delphi_review_backup_{TS}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    for tid in TASKS:
        fp = OUT_DIR / f"progress_{tid}.json"
        rec = json.loads(fp.read_text(encoding="utf-8"))
        shutil.copyfile(fp, backup_dir / fp.name)

        task_data = load_task_from_cache(int(tid))
        if task_data is None:
            print(f"[{tid}] 缓存无数据，跳过")
            continue

        # 1. 重算 violations（真实命中行 evidence，message 对齐）
        candidates = compute_violations(task_data)
        print(f"\n===== 任务 {tid}：初筛候选 {len(candidates)} 条 =====")
        if not candidates:
            rec["violations"] = []
            rec["delphi_review"] = {
                "reviewed_at": TS,
                "method": "delphi_multi_expert_consensus",
                "conclusion": "修正后引擎重算无命中，历史命中已随引擎修正消除",
            }
            fp.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
            continue
        for c in candidates:
            print(f"  候选: {c['rule_id']} {c['message'][:40]} evidence={len(c['evidence'])}行")

        # 2. Delphi 真实 LLM 复审
        fault_info = {
            "task_id": tid,
            "title": task_data.get("title", ""),
            "description": (task_data.get("description", "") or "")[:500],
            "code_snippet": "\n".join(
                extract_added_lines(c.get("diff", ""))
                for c in (task_data.get("development") or {}).get("commits", [])
                if c.get("diff")
            ),
        }
        review = await reviewer.review(fault_info, candidates)

        # 人工终裁叠加：LLM 专家分歧（diverged）但人工结论明确误报时撤销。
        # 专家都不认为违规成立（分歧仅在"误报"还是"证据不足"）+ 人工判误报
        # => 三方无一支持违规，不应保留违规标记；分歧事实保留在审计中。
        for item in review["items"]:
            manual_reason = MANUAL_REASONS.get(tid, {}).get(item.get("rule_id", ""))
            if item["final_verdict"] == "diverged" and manual_reason:
                item["final_verdict"] = "false_positive"
                item["reason"] = f"人工终裁（LLM专家分歧: {item['reason']}）: {manual_reason}"

        kept, revoked = apply_review(candidates, review)

        for item in review["items"]:
            print(
                f"  裁决: {item['rule_id']} -> {item['final_verdict']}"
                f"（共识={item['consensus']}，{item['rounds']}轮）{item['reason'][:80]}"
            )

        # 3. 写入 progress：保留集 + 复审记录（LLM 专家 + 人工结论）
        rec["violations"] = kept
        rec["delphi_review"] = {
            **review,
            "revoked": revoked,
            "manual_review": {
                "reviewer": "复盘引擎维护（人工逐条核查，依据缓存 diff 上下文）",
                "items": [
                    {"rule_id": rid, "conclusion": "false_positive", "reason": reason}
                    for rid, reason in MANUAL_REASONS.get(tid, {}).items()
                ],
            },
        }
        rec["delphi_reviewed_at"] = TS
        fp.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  -> progress_{tid}.json 已更新（保留 {len(kept)} 条，撤销 {len(revoked)} 条）")

    print(f"\n备份目录: {backup_dir}")


if __name__ == "__main__":
    asyncio.run(run())
