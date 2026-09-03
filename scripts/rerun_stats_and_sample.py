"""复盘结论批量重审：结果统计 + UAT 抽样比对材料生成（手动调试脚本）。

直接运行: python scripts/rerun_stats_and_sample.py

扫描 output/progress_*.json 的 conclusion_review 段：
1. 汇总三口径（已复审 / 跳过 / 全专家失败）与撤销分布
2. 按确定性规则抽取 5 单（用户点名案例 + 撤销条数最多全撤x2 + 部分撤x1
   + 全保留x1），生成人工比对材料 output/uat_sample_<日期>.md，
   并对撤销条目做复审前备份原文一致性校验
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"
SAMPLE_REPORT = OUTPUT_DIR / f"uat_sample_{datetime.now().strftime('%Y%m%d')}.md"
BREAKDOWN_REPORT = OUTPUT_DIR / f"revoke_reason_breakdown_{datetime.now().strftime('%Y%m%d')}.md"
FORCED_SAMPLE_IDS = [11757372]
SAMPLE_SIZE = 5

# 撤销理由证据缺口分类——信号词取自 219 条撤销理由原文逐条归纳。
# 「缺修复前代码」「无代码证据」「diff覆盖不全」「图片证据未入材料」四类
# 属于裁决基准错位：引入单号非必填、图片证据客观存在，缺失辅助信息不构成
# 「证据不足」判据，应按故障单本身能提供的信息裁决（用户裁定口径）。
GAP_PATTERNS: list[tuple[str, str]] = [
    ("证据矛盾", r"(矛盾|不存在结论所述|原文中不存在|本就不参与|结论与证据不符|并非直接)"),
    (
        "缺修复前代码",
        r"(未提供修复前|无.{0,10}修复前|未含修复前|未展示.{0,16}修复前"
        r"|仅(展示|显示|含)修复后"
        r"|无法(确认|证明|核对|验证|直接证明|直接核对|直接验证).{0,14}修复前|修复前.{0,8}原文)",
    ),
    (
        "无代码证据",
        r"(代码 ?diff ?(上下文(窗口)?)?为空|无(任何)?代码 ?diff|未提供(任何)?代码 ?diff"
        r"|无代码(变更|证据|依据))",
    ),
    (
        "diff覆盖不全",
        r"(证据(上下文)?窗口|diff ?上下文(窗口)?(仅|未|不完整|全部为)"
        r"|未包含.{0,25}(的)?(diff|内容|代码)|diff.{0,4}未(展示|包含|涉及)"
        r"|未涉及|与结论无直接(关联|对应)|非代码证据|无法在代码层面验证|不在(提供|证据)"
        r"|diff ?(中|里)无|代码diff中无)",
    ),
    (
        "测试证据缺失",
        r"(测试用例|测试记录|测试报告|测试计划|测试覆盖|测试执行|未(包含|提供)?(任何)?测试)",
    ),
    (
        "图片证据未入材料",
        r"(截图.{0,18}(无法核实|未在|未提供|不在)|截图未提供|截图内容未在"
        r"|(未提供|未在).{0,4}截图(原文|内容)?)",
    ),
    (
        "运行时数据缺失",
        r"(执行计划|性能数据|性能测试|实测|运行(数据|证据|记录)|日志原文|扫描范围|资源占用)",
    ),
    ("文档依据缺失", r"(设计文档|需求原文|评审记录|设计(说明|阶段).{0,12}(原文|记录|评审))"),
]
# 主缺口判定顺序（ cause_type 含「测试」时测试证据缺失优先——验证测试类
# 结论的决定性证据是测试数据而非代码）
GAP_PRIORITY = [
    "证据矛盾",
    "缺修复前代码",
    "无代码证据",
    "diff覆盖不全",
    "测试证据缺失",
    "图片证据未入材料",
    "运行时数据缺失",
    "文档依据缺失",
]
# 三大类归属：裁决基准错位（按用户口径属误撤）/ 数据源缺口 / 正当撤销
GAP_GROUPS: dict[str, str] = {
    "证据矛盾": "正当撤销",
    "测试证据缺失": "数据源缺口",
    "运行时数据缺失": "数据源缺口",
    "文档依据缺失": "数据源缺口",
    "缺修复前代码": "裁决基准错位",
    "无代码证据": "裁决基准错位",
    "diff覆盖不全": "裁决基准错位",
    "图片证据未入材料": "裁决基准错位",
}


def load_records() -> list[dict[str, Any]]:
    files = sorted(OUTPUT_DIR.glob("progress_*.json"))
    return [json.loads(fp.read_text(encoding="utf-8")) for fp in files]


def classify(
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[int], list[int]]:
    """按 conclusion_review 状态分为已复审 / 跳过 / 全专家失败三口径。"""
    reviewed: list[dict[str, Any]] = []
    skipped: list[int] = []
    errored: list[int] = []
    for rec in records:
        review = rec.get("conclusion_review") or {}
        if review.get("reviewer_error"):
            errored.append(int(rec["urId"]))
        elif not review.get("reviewed_at"):
            skipped.append(int(rec["urId"]))
        else:
            reviewed.append(rec)
    return reviewed, skipped, errored


def find_backup_dir() -> Path | None:
    candidates = sorted(OUTPUT_DIR.glob("conclusions_rerun_backup_*"))
    return candidates[-1] if candidates else None


def verify_backup(rec: dict[str, Any], backup_dir: Path | None) -> str:
    """校验撤销条目原文与复审前备份一致（防撤销时篡改原文）。"""
    if backup_dir is None:
        return "未找到备份目录"
    fp = backup_dir / f"progress_{rec['urId']}.json"
    if not fp.exists():
        return "备份缺失"
    backup = json.loads(fp.read_text(encoding="utf-8"))
    orig = {c.get("description", "") for c in backup.get("root_causes") or []}
    revoked = (rec.get("conclusion_review") or {}).get("revoked") or []
    if not revoked:
        return "无撤销条目"
    mismatch = sum(1 for r in revoked if r.get("description", "") not in orig)
    if mismatch:
        return f"不一致 x{mismatch}"
    return f"一致 x{len(revoked)}"


def gaps_of(reason: str) -> list[str]:
    """撤销理由命中的全部证据缺口标签（多标签，可空）。"""
    return [label for label, pattern in GAP_PATTERNS if re.search(pattern, reason)]


def primary_gap(reason: str, cause_type: str) -> str:
    """单标签主缺口：测试类结论优先看测试数据，其余按 GAP_PRIORITY，兜底纯推理缺口。"""
    test_pattern = dict(GAP_PATTERNS)["测试证据缺失"]
    if "测试" in cause_type and re.search(test_pattern, reason):
        return "测试证据缺失"
    for label in GAP_PRIORITY:
        pattern = dict(GAP_PATTERNS)[label]
        if re.search(pattern, reason):
            return label
    return "纯推理缺口"


def problem_category_dist(records: list[dict[str, Any]]) -> Counter[str]:
    """故障单业务特征分布（深度根因链路 problem_category，未复审，参考口径）。"""
    counter: Counter[str] = Counter()
    for rec in records:
        deep = rec.get("deep_root_causes") or {}
        counter[str(deep.get("problem_category") or "无深度根因")] += 1
    return counter


def _gap_samples(revocations: list[dict[str, Any]], label: str, n: int = 2) -> list[str]:
    picked = [r for r in revocations if r["primary"] == label][:n]
    return [f"- [{r['urId']}][{r['cause_type']}] {r['reason'][:90]}…" for r in picked]


def build_breakdown_md(
    revocations: list[dict[str, Any]],
    full_categories: Counter[str],
    all_categories: Counter[str],
    n_full_revoked: int,
    n_records: int,
) -> str:
    """撤销理由证据缺口细分报告（含三类归属、主缺口分布、纯推理缺口全量清单）。"""
    total = max(len(revocations), 1)
    primary_counter: Counter[str] = Counter(r["primary"] for r in revocations)
    multi_counter: Counter[str] = Counter()
    group_counter: Counter[str] = Counter()
    for r in revocations:
        multi_counter.update(r["gaps"])
        group_counter[r["group"]] += 1

    lines: list[str] = [
        "# 撤销理由证据缺口细分报告",
        "",
        f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')} ｜ 撤销条目 {len(revocations)} 条",
        "",
        "## 裁决口径",
        "",
        "引入单号非必填，引入单信息（含修复前代码）只是辅助证据；缺失时应按故障单",
        "本身能提供的信息（描述、截图证据、修复 diff 新增行）裁决，而不是跳过。",
        "据此将撤销理由归为三大类：",
        "",
        "- **正当撤销**：结论与材料内事实矛盾，或断言超出材料所能支撑（宁缺毋滥）；",
        "- **数据源缺口**：验证结论需要测试/监控/文档数据，当前数据源未接入；",
        "- **裁决基准错位**：以「缺修复前代码 / 无代码 diff / diff 覆盖不全 / 截图未入材料」",
        "  这类辅助信息缺失为由撤销——按上述口径属误撤，应通过补全复审材料解决。",
        "",
        "## 三大类分布",
        "",
        "| 大类 | 条数 | 占比 |",
        "|------|------|------|",
    ]
    for group in ["正当撤销", "数据源缺口", "裁决基准错位"]:
        n = group_counter.get(group, 0)
        lines.append(f"| {group} | {n} | {n / total:.0%} |")

    lines += [
        "",
        "## 主缺口分布（单标签）",
        "",
        "| 主缺口 | 条数 | 占比 | 归属 |",
        "|--------|------|------|------|",
    ]
    for label in [*GAP_PRIORITY, "纯推理缺口"]:
        n = primary_counter.get(label, 0)
        if not n:
            continue
        lines.append(f"| {label} | {n} | {n / total:.0%} | {GAP_GROUPS.get(label, '正当撤销')} |")

    lines += ["", "## 信号词命中分布（多标签，一条理由可命中多个）", ""]
    for label, _ in GAP_PATTERNS:
        n = multi_counter.get(label, 0)
        if n:
            lines.append(f"- {label}: {n} 次 ({n / total:.0%})")

    lines += ["", "## 各主缺口样例（供核验分类质量）", ""]
    for label in [*GAP_PRIORITY, "纯推理缺口"]:
        if not primary_counter.get(label):
            continue
        lines.append(f"### {label}")
        lines += _gap_samples(revocations, label)
        lines.append("")

    reasoning_all = [r for r in revocations if r["primary"] == "纯推理缺口"]
    lines += ["## 纯推理缺口全量清单（未命中任何数据缺口信号词）", ""]
    if reasoning_all:
        for r in reasoning_all:
            lines.append(f"- [{r['urId']}][{r['cause_type']}] {r['reason']}")
    else:
        lines.append("-（无）")

    lines += [
        "",
        "## 全撤单业务特征（深度根因链路 problem_category，未复审，参考口径）",
        "",
        f"全撤 {n_full_revoked} 单 vs 全体 {n_records} 单：",
        "",
        "| problem_category | 全撤单 | 占比 | 全体 | 占比 |",
        "|------------------|--------|------|------|------|",
    ]
    for cat in sorted(set(full_categories) | set(all_categories), key=lambda c: -all_categories[c]):
        f_n = full_categories.get(cat, 0)
        a_n = all_categories.get(cat, 0)
        lines.append(
            f"| {cat} | {f_n} | {f_n / max(n_full_revoked, 1):.0%} | {a_n} | {a_n / max(n_records, 1):.0%} |"
        )

    lines += [
        "",
        "## 改进指向（按影响面排序）",
        "",
        "1. **复审材料补删除行**：build_fault_info 仅喂 extract_added_lines（+ 行），",
        "   修复前代码（- 行）从未进入材料——「缺修复前代码」类缺口的系统性根因。",
        "2. **复审材料补 image_evidence**：截图 OCR 文本在 progress 中存在但未进材料，",
        "   「截图无法核实」类撤销可直接消除。",
        "3. **裁决纪律进 prompt**：CONCLUSION_SYSTEM_PROMPT 明确——引入单信息缺失不是",
        "   证据不足的理由，按故障单信息裁决；结论断言超出材料支撑或与材料矛盾时才撤。",
        "4. **数据源建设（长期）**：测试用例/执行记录、性能监控数据接入后，",
        "   「测试证据缺失」「运行时数据缺失」类结论可重审。",
        "",
    ]
    return "\n".join(lines)


def pick_sample(
    reviewed: list[dict[str, Any]],
    full_revoked: list[dict[str, Any]],
    partial: list[dict[str, Any]],
    kept: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """确定性抽样：点名案例 + 全撤x2 + 部分撤x1 + 全保留x1，共 SAMPLE_SIZE 单。"""
    by_id = {int(r["urId"]): r for r in reviewed}
    sample: list[dict[str, Any]] = []
    seen: set[int] = set()

    def take(recs: list[dict[str, Any]], n: int) -> None:
        for rec in recs:
            if n <= 0 or len(sample) >= SAMPLE_SIZE:
                return
            urid = int(rec["urId"])
            if urid in seen:
                continue
            sample.append(rec)
            seen.add(urid)
            n -= 1

    take([by_id[u] for u in FORCED_SAMPLE_IDS if u in by_id], len(FORCED_SAMPLE_IDS))
    take(
        sorted(
            full_revoked,
            key=lambda r: (-len(r["conclusion_review"].get("revoked") or []), int(r["urId"])),
        ),
        2,
    )
    take(
        sorted(
            partial,
            key=lambda r: (-len(r["conclusion_review"].get("revoked") or []), int(r["urId"])),
        ),
        1,
    )
    take(
        sorted(
            kept,
            key=lambda r: (-len(r["conclusion_review"].get("items") or []), int(r["urId"])),
        ),
        1,
    )
    return sample


def build_sample_md(sample: list[dict[str, Any]], backup_dir: Path | None) -> str:
    lines: list[str] = [
        "# 复盘结论重审 UAT 抽样比对材料",
        "",
        f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')} ｜ 抽样 {len(sample)} 单",
        "> 抽样规则: 用户点名 11757372 + 撤销条数最多全撤 x2 + 部分撤 x1 + 全保留 x1",
        "",
        "## 比对要点",
        "",
        "1. 撤销是否误撤——原结论所引证据是否其实足以支撑结论；",
        "2. 撤销理由是否成立——理由是否指出结论中缺乏原文依据的具体断言；",
        "3. 保留条目是否本应撤销——结论是否同样存在无证据支撑的推断成分；",
        "4. 撤销仅标记 pending_rebuild 待人工重建，原结论已存备份，可随时恢复。",
        "",
    ]
    for idx, rec in enumerate(sample, 1):
        review = rec.get("conclusion_review") or {}
        items = review.get("items") or []
        revoked = review.get("revoked") or []
        lines.append(f"## 样本 {idx}: {rec['urId']} {rec.get('title', '')}")
        lines.append("")
        lines.append(
            f"- 复审状态: {review.get('conclusion_status', '?')} ｜ "
            f"裁决 {len(items)} 条 / 撤销 {len(revoked)} 条 ｜ "
            f"备份原文校验: {verify_backup(rec, backup_dir)}"
        )
        lines.append("")
        lines.append("### 裁决摘要")
        lines.append("")
        lines.append("| # | 结论类型 | 最终裁决 | 共识 | 轮数 |")
        lines.append("|---|----------|----------|------|------|")
        for j, it in enumerate(items, 1):
            lines.append(
                f"| {j} | {it.get('cause_type', '?')} | {it.get('final_verdict', '?')} "
                f"| {it.get('consensus', '?')} | {it.get('rounds', '?')} |"
            )
        lines.append("")
        if revoked:
            lines.append("### 被撤销的结论（原文 + 撤销理由）")
            lines.append("")
            for j, rev in enumerate(revoked, 1):
                lines.append(f"**{j}. [{rev.get('cause_type', '?')}] 原结论**")
                lines.append("")
                lines.append(str(rev.get("description", "")))
                lines.append("")
                lines.append(f"- 复审裁决: {rev.get('conclusion_verdict', '?')}")
                lines.append(f"- 撤销理由: {rev.get('conclusion_reason', '')}")
                ev = rev.get("evidence") or []
                if ev:
                    lines.append("- 原结论所引证据:")
                    for k, e in enumerate(ev, 1):
                        lines.append(f"  {k}. {e}")
                lines.append("")
        kept_causes = rec.get("root_causes") or []
        confirmed = [it for it in items if it.get("final_verdict") == "confirmed"]
        if kept_causes:
            lines.append("### 被保留的结论（原文 + 保留理由）")
            lines.append("")
            for j, c in enumerate(kept_causes, 1):
                lines.append(f"**{j}. [{c.get('cause_type', '?')}] 结论（保留）**")
                lines.append("")
                lines.append(str(c.get("description", "")))
                lines.append("")
            for it in confirmed:
                lines.append(f"- 保留理由[{it.get('cause_type', '?')}]: {it.get('reason', '')}")
            lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    records = load_records()
    reviewed, skipped, errored = classify(records)

    full_revoked: list[dict[str, Any]] = []
    partial: list[dict[str, Any]] = []
    kept: list[dict[str, Any]] = []
    verdicts: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    total_items = 0
    total_revoked = 0
    revocations: list[dict[str, Any]] = []
    for rec in reviewed:
        review = rec["conclusion_review"]
        items = review.get("items") or []
        revoked = review.get("revoked") or []
        total_items += len(items)
        total_revoked += len(revoked)
        statuses[str(review.get("conclusion_status", "unknown"))] += 1
        for it in items:
            verdicts[str(it.get("final_verdict", "unknown"))] += 1
        if items and len(revoked) == len(items):
            full_revoked.append(rec)
        elif revoked:
            partial.append(rec)
        else:
            kept.append(rec)
        for rev in revoked:
            reason = str(rev.get("conclusion_reason", ""))
            cause_type = str(rev.get("cause_type", ""))
            primary = primary_gap(reason, cause_type)
            revocations.append(
                {
                    "urId": rec["urId"],
                    "cause_type": cause_type,
                    "reason": reason,
                    "gaps": gaps_of(reason),
                    "primary": primary,
                    "group": GAP_GROUPS.get(primary, "正当撤销"),
                }
            )

    ratio = total_revoked / total_items if total_items else 0.0
    print(f"progress 文件总数: {len(records)}")
    print(f"已复审: {len(reviewed)}")
    print(f"跳过(无结论/未复审): {len(skipped)} {skipped}")
    print(f"全专家失败: {len(errored)} {errored}")
    print(
        f"结论条目: {total_items} ｜ 撤销 {total_revoked} 条 ({ratio:.0%}) ｜ "
        f"保留 {total_items - total_revoked} 条"
    )
    print(f"全撤单: {len(full_revoked)} ｜ 部分撤单: {len(partial)} ｜ 全保留单: {len(kept)}")
    print(f"final_verdict 分布: {dict(verdicts)}")
    print(f"conclusion_status 分布: {dict(statuses)}")

    group_counter: Counter[str] = Counter(r["group"] for r in revocations)
    n_rev = max(len(revocations), 1)
    print(
        "撤销理由三大类: "
        + " ｜ ".join(f"{g} {n}条({n / n_rev:.0%})" for g, n in group_counter.most_common())
    )
    BREAKDOWN_REPORT.write_text(
        build_breakdown_md(
            revocations,
            problem_category_dist(full_revoked),
            problem_category_dist(records),
            len(full_revoked),
            len(records),
        ),
        encoding="utf-8",
    )
    print(f"细分报告: {BREAKDOWN_REPORT}")

    sample = pick_sample(reviewed, full_revoked, partial, kept)
    backup_dir = find_backup_dir()
    SAMPLE_REPORT.write_text(build_sample_md(sample, backup_dir), encoding="utf-8")
    print(f"UAT 抽样材料: {SAMPLE_REPORT}")


if __name__ == "__main__":
    main()
