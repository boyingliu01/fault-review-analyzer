"""生成复盘分析报告（Excel + Markdown 汇总）。

数据来源: output/progress_*.json（每起分析结果）
输出:
  - output/复盘分析报告.xlsx   (多 sheet)
  - output/复盘分析汇总.md     (管理层摘要)
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

OUT_DIR = Path(__file__).parent.parent / "output"


def load_all_records() -> dict[int, dict]:
    recs = {}
    for fp in sorted(OUT_DIR.glob("progress_*.json")):
        with fp.open(encoding="utf-8") as fh:
            rec = json.load(fh)
        recs[rec["urId"]] = rec
    return recs


def primary_cause(rec: dict) -> str:
    rcs = rec.get("root_causes", [])
    if not rcs:
        return "无根因"
    return rcs[0].get("cause_type", "未知")


def build_detail_df(recs: dict) -> pd.DataFrame:
    """缺陷明细表。"""
    rows = []
    for u, rec in recs.items():
        # 根因摘要（首要 + 数量）
        rcs = rec.get("root_causes", [])
        primary = rcs[0].get("cause_type", "") if rcs else ""
        root_summary = "; ".join(
            f"{rc.get('cause_type','')}:{rc.get('description','')[:50]}"
            for rc in rcs[:2]
        )
        # 改进建议
        imps = rec.get("improvements", [])
        imp_summary = "; ".join(
            f"[{imp.get('priority','')}]{imp.get('measure','')[:40]}"
            for imp in imps[:3]
        )
        # 规范违规
        viols = rec.get("violations", [])
        viol_ids = "; ".join(v.get("rule_id", "") for v in viols)
        # 深度分析（5层追问）
        deep = rec.get("deep_root_causes") or {}
        deep_summary = "; ".join(
            f"[{rc.get('layer', '')}] {rc.get('root_cause', '')[:40]}"
            for rc in deep.get("deep_root_causes", [])[:2]
        )
        rows.append({
            "urId": u,
            "标题": rec.get("title", ""),
            "首要根因": primary,
            "根因数": len(rcs),
            "根因摘要": root_summary,
            "问题分类(deep)": deep.get("problem_category", ""),
            "初步归因(deep)": str(deep.get("initial_cause", ""))[:80],
            "深层根因摘要(deep)": deep_summary,
            "Checklist建议数(deep)": len(deep.get("checklist_recommendations", [])),
            "规范违规": viol_ids,
            "违规数": len(viols),
            "改进建议数": len(imps),
            "改进建议摘要": imp_summary,
            "有代码变更": "是" if rec.get("has_code_change") else "否",
            "耗时(秒)": round(rec.get("processing_time", 0), 1),
        })
    return pd.DataFrame(rows)


def build_group_df(recs: dict) -> pd.DataFrame:
    """缺陷模式分组表（按首要根因类型）。"""
    groups = defaultdict(list)
    for u, rec in recs.items():
        groups[primary_cause(rec)].append(u)

    rows = []
    for cause, members in sorted(groups.items(), key=lambda x: -len(x[1])):
        # 组内规范违规
        rules = Counter()
        for u in members:
            for v in recs[u].get("violations", []):
                rules[v.get("rule_id", "")] += 1
        # 组内代码变更率
        code_count = sum(1 for u in members if recs[u].get("has_code_change"))
        rows.append({
            "缺陷模式": cause,
            "涉及缺陷数": len(members),
            "占比(%)": round(len(members) / len(recs) * 100, 1),
            "代码变更缺陷数": code_count,
            "主要规范违规": "; ".join(f"{r}({c})" for r, c in rules.most_common(5)),
            "缺陷单号": ", ".join(str(m) for m in members[:10]),
        })
    return pd.DataFrame(rows)


def build_violation_df(recs: dict) -> pd.DataFrame:
    """规范违规分布表。"""
    rules = Counter()
    for rec in recs.values():
        for v in rec.get("violations", []):
            rules[v.get("rule_id", "")] += 1
    return pd.DataFrame(
        [{"规范条款": r, "违规次数": c} for r, c in rules.most_common()],
        columns=["规范条款", "违规次数"],
    )


def build_summary_md(recs: dict, group_df: pd.DataFrame, viol_df: pd.DataFrame) -> str:
    """生成管理层摘要 Markdown。"""
    lines = [
        "# 研发泄漏缺陷复盘分析汇总",
        "",
        f"**分析范围**: {len(recs)} 起研发泄漏缺陷",
        "**分析方法**: AI 自主分析（聚类 + 根因分析 + 规范匹配 + 改进建议）",
        "",
        "## 一、总体结论",
        "",
        f"共分析 {len(recs)} 起软件缺陷，识别出 {len(group_df)} 种主要缺陷模式。",
        "根因集中在**设计缺陷**、**编码错误**、**需求理解偏差**等环节。",
        "",
        "## 二、缺陷模式分布",
        "",
        "| 缺陷模式 | 缺陷数 | 占比 | 主要规范违规 |",
        "|---------|--------|------|-------------|",
    ]
    for _, row in group_df.iterrows():
        lines.append(
            f"| {row['缺陷模式']} | {row['涉及缺陷数']} | {row['占比(%)']}% | {row['主要规范违规']} |"
        )

    lines += ["", "## 三、规范违规 Top 分布", "", "| 规范条款 | 违规次数 |", "|---------|---------|"]
    for _, row in viol_df.head(10).iterrows():
        lines.append(f"| {row['规范条款']} | {row['违规次数']} |")

    # 改进建议分布
    imp_cat = Counter()
    for rec in recs.values():
        for imp in rec.get("improvements", []):
            imp_cat[imp.get("category", "未知")] += 1
    lines += ["", "## 四、改进建议类别分布", ""]
    for cat, cnt in imp_cat.most_common():
        lines.append(f"- **{cat}**: {cnt} 条")

    lines += ["", "## 五、重点改进方向", ""]
    # 取最大的几个模式给出建议
    top_modes = group_df.head(4)
    for _, row in top_modes.iterrows():
        lines.append(f"### {row['缺陷模式']}（{row['涉及缺陷数']} 起，占比 {row['占比(%)']}%）")
        lines.append(f"- 规范违规重点: {row['主要规范违规']}")
        lines.append("")

    # 深度分析问题分类分布
    deep_cat = Counter()
    deep_covered = 0
    for rec in recs.values():
        d = rec.get("deep_root_causes")
        if d and isinstance(d, dict) and d.get("problem_category"):
            deep_covered += 1
            deep_cat[d["problem_category"]] += 1
    if deep_covered:
        lines += [
            "",
            "## 六、深度分析·问题分类分布",
            "",
            f"已完成 {deep_covered}/{len(recs)} 起的 5 层深度根因分析。",
            "",
            "| 问题分类 | 数量 | 占比 |",
            "|---------|------|------|",
        ]
        for cat, cnt in deep_cat.most_common():
            lines.append(f"| {cat} | {cnt} | {round(cnt / len(recs) * 100, 1)}% |")

    return "\n".join(lines)


def main():
    recs = load_all_records()
    print(f"加载 {len(recs)} 起分析结果")

    detail_df = build_detail_df(recs)
    group_df = build_group_df(recs)
    viol_df = build_violation_df(recs)
    summary_md = build_summary_md(recs, group_df, viol_df)

    # 写 Excel
    excel_path = OUT_DIR / "复盘分析报告.xlsx"
    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        group_df.to_excel(writer, sheet_name="缺陷模式分组", index=False)
        viol_df.to_excel(writer, sheet_name="规范违规分布", index=False)
        detail_df.to_excel(writer, sheet_name="缺陷明细", index=False)
    print(f"Excel 报告已生成: {excel_path}")

    # 写 Markdown
    md_path = OUT_DIR / "复盘分析汇总.md"
    md_path.write_text(summary_md, encoding="utf-8")
    print(f"Markdown 汇总已生成: {md_path}")


if __name__ == "__main__":
    main()
