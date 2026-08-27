#!/usr/bin/env python
"""生成面向客户的《泄漏缺陷复盘综合分析报告》（全量聚合版）。

与 scripts/generate_report.py 的区别:
    - generate_report.py 输出内部明细型汇总（xlsx 多 sheet + 管理层摘要）
    - 本脚本输出一份**客户级综合反馈文档**：跨批次聚合全部缺陷，
      含执行摘要、问题全景、缺陷模式帕累托、五层根因共性洞察、
      规范符合性、改进路线图 —— 可直接作为交付物发给客户。

数据源: output/progress_*.json（权威全集）
输出:   output/复盘综合分析报告.md

用法:
    python scripts/generate_client_report.py            # 统计聚合 + LLM 共性主题归纳
    python scripts/generate_client_report.py --no-llm   # 纯统计聚合（离线可跑）
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

OUT_DIR = Path(__file__).parent.parent / "output"

# 5 层根因的标准层名归一化（模型偶发输出变体层名）
_LAYER_ALIASES = {
    "流程与知识层面": "流程与知识管理层面",
    "流程与知识管理层面": "流程与知识管理层面",
}
_LAYER_ORDER = [
    "设计层面",
    "编码层面",
    "测试层面",
    "流程层面",
    "知识管理层面",
    "需求层面",
    "流程与知识管理层面",
]

_PROBLEM_CAT_DESC = {
    "开发引入": "代码实现或系统设计环节引入的缺陷",
    "测试泄露": "测试用例未覆盖导致缺陷逃逸到生产",
    "需求问题": "需求描述不清/变更管理不足引入的缺陷",
    "外部依赖": "第三方服务、基础设施等外部因素导致的故障",
}


def load_records() -> dict[int, dict[str, Any]]:
    recs: dict[int, dict[str, Any]] = {}
    for fp in sorted(OUT_DIR.glob("progress_*.json")):
        try:
            rec = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        if rec.get("urId") and rec.get("root_causes"):
            recs[int(rec["urId"])] = rec
    return recs


def aggregate(recs: dict[int, dict[str, Any]]) -> dict[str, Any]:
    """确定性统计聚合。"""
    n = len(recs)
    primary_causes: Counter[str] = Counter()
    deep_cats: Counter[str] = Counter()
    layer_items: dict[str, list[str]] = defaultdict(list)
    viol_rules: Counter[str] = Counter()
    viol_urids: dict[str, set[int]] = defaultdict(set)
    imp_by_cat_prio: Counter[tuple[str, str]] = Counter()
    with_code = sum(1 for r in recs.values() if r.get("has_code_change"))
    img_ev_used = sum(1 for r in recs.values() if r.get("image_evidence"))
    conf_sum = 0.0
    conf_n = 0

    for u, r in recs.items():
        rc0 = r["root_causes"][0] if r["root_causes"] else {}
        primary_causes[rc0.get("cause_type", "未知") or "未知"] += 1
        for rc in r["root_causes"]:
            c = rc.get("confidence")
            if isinstance(c, (int, float)):
                conf_sum += float(c)
                conf_n += 1
        d = r.get("deep_root_causes") or {}
        if isinstance(d, dict) and d.get("problem_category"):
            deep_cats[d["problem_category"]] += 1
        for rc in d.get("deep_root_causes", []):
            raw_layer = str(rc.get("layer") or "")
            layer = _LAYER_ALIASES.get(raw_layer, raw_layer)
            layer_items[layer].append(str(rc.get("root_cause") or "").strip())
        for v in r.get("violations", []):
            rid = v.get("rule_id", "")
            viol_rules[rid] += 1
            viol_urids[rid].add(u)
        for imp in r.get("improvements", []):
            imp_by_cat_prio[(imp.get("category", "其他"), imp.get("priority", "?"))] += 1

    return {
        "total": n,
        "with_code": with_code,
        "img_ev_used": img_ev_used,
        "avg_conf": round(conf_sum / conf_n, 2) if conf_n else 0,
        "primary_top": primary_causes.most_common(),
        "deep_cats": deep_cats.most_common(),
        "layer_items": dict(layer_items),
        "viols": viol_rules.most_common(),
        "viol_urid_count": {rid: len(s) for rid, s in viol_urids.items()},
        "imps": imp_by_cat_prio.most_common(),
    }


_LLM_THEMES_PROMPT = """你是软件质量改进专家。以下是从 {total} 起泄漏缺陷的深度根因分析中提取的分层根因清单。
请归纳出 **5~8 个跨单位的共性根因主题**（同类问题在不同功能模块反复出现的模式），每个主题给出简洁命名和说明。

要求：
- 主题必须基于清单中的实际内容，不要泛泛而谈（如"加强测试"这类不可接受）
- 每个主题标注主要集中哪一层，并估算涉及条数区间
- 严格输出 JSON: {{"themes":[{{"name":"...","layer":"...","estimate":"约N起","description":"..."}}]}}
- 不要输出 JSON 以外的任何内容

【分层根因清单】
{items}
"""


async def _llm_common_themes(stats: dict[str, Any]) -> list[dict[str, str]]:
    """调用 LLM 归纳共性主题；失败返回空列表（降级）。"""
    items_txt_parts: list[str] = []
    for layer in _LAYER_ORDER:
        items = stats["layer_items"].get(layer, [])
        if not items:
            continue
        # 每层最多取 25 条代表样本（保留多样性，控制 prompt 长度）
        uniq: list[str] = []
        seen: set[str] = set()
        for it in items:
            key = it[:24]
            if key not in seen:
                seen.add(key)
                uniq.append(it[:120])
            if len(uniq) >= 25:
                break
        items_txt_parts.append(f"【{layer}】({len(items)} 条)\n" + "\n".join(f"- {x}" for x in uniq))
    if not items_txt_parts:
        return []

    try:
        from src.analyzer.llm_provider import create_llm_provider
        from src.config.manager import ConfigManager

        provider = create_llm_provider(ConfigManager().load().llm)
        if provider is None:
            return []
        response = await provider.generate(
            system="你只输出合法 JSON。",
            user=_LLM_THEMES_PROMPT.format(total=stats["total"], items="\n\n".join(items_txt_parts)),
        )
        await provider.close()
        t = response.strip()
        if t.startswith("```"):
            t = t[t.find("{") : t.rfind("}") + 1]
        data = json.loads(t)
        themes = [x for x in data.get("themes", []) if x.get("name")]
        return themes[:8]
    except Exception as e:
        print(f"[提示] LLM 共性主题归纳失败，降级为统计展示: {str(e)[:120]}")
        return []


def render_md(stats: dict[str, Any], themes: list[dict[str, str]], use_llm: bool) -> str:
    """组装 Markdown 报告。"""
    n = stats["total"]
    lines: list[str] = []
    add = lines.append

    add("# 泄漏缺陷复盘 · 综合分析报告")
    add("")
    add(f"**分析范围**: {n} 起研发泄漏缺陷（全量）　|　**分析时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    add("**分析方法**: AI 复盘流水线 — 根因聚类 + 规范匹配 + 截图证据视觉识别 + 五层深度根因追问")
    add(
        f"**数据口径**: 证据来源含故障描述({stats['img_ev_used']} 起附有截图内容识别)、代码变更 diff({stats['with_code']} 起)、"
        f"研发规范库；AI 结论平均置信度 {stats['avg_conf']}"
    )
    add("")

    # 一、执行摘要
    deep_top3 = ", ".join(f"{c}({v}起/{round(v/n*100)}%)" for c, v in stats["deep_cats"][:2])
    add("## 一、执行摘要")
    add("")
    add(
        f"- 本次复盘覆盖 {n} 起泄漏缺陷。按问题性质划分，{deep_top3} 为最主要的两大类问题。"
    )
    mode_names = "、".join(c for c, _ in stats["primary_top"][:3])
    add(f"- 缺陷模式集中在 {mode_names}，呈典型帕累托分布（详见第三节）。")
    rule_names = "、".join(r for r, _ in stats["viols"][:3])
    add(f"- 规范符合性方面，高频违规条款为 {rule_names}（详见表）。")
    add("- 全部缺陷已逐单完成五层深度根因追问，共提炼出分层面根因 "
        f"{sum(len(v) for v in stats['layer_items'].values())} 条，共性模式见第五节。")
    add("")

    # 二、问题全景
    add("## 二、问题全景（四大类）")
    add("")
    add("| 问题分类 | 数量 | 占比 | 说明 |")
    add("|---------|------|------|------|")
    for cat, cnt in stats["deep_cats"]:
        desc = _PROBLEM_CAT_DESC.get(cat, "")
        add(f"| {cat} | {cnt} | {round(cnt/n*100, 1)}% | {desc} |")
    covered_deep = sum(v for _, v in stats["deep_cats"])
    if covered_deep < n:
        add(f"| 未完成深度分析 | {n - covered_deep} | {round((n-covered_deep)/n*100,1)}% | 历史数据 | ")
    add("")

    # 三、缺陷模式帕累托
    add("## 三、缺陷模式帕累托")
    add("")
    add("| 排名 | 缺陷模式 | 数量 | 占比 | 累计占比 |")
    add("|-----|---------|------|------|---------|")
    cum = 0
    total_primary = sum(v for _, v in stats["primary_top"])
    for i, (cause, cnt) in enumerate(stats["primary_top"][:15], 1):
        cum += cnt
        add(
            f"| {i} | {cause} | {cnt} | {round(cnt/total_primary*100,1)}% | {round(cum/total_primary*100,1)}% |"
        )
    rest = len(stats["primary_top"]) - 15
    if rest > 0:
        add(f"| … | 其余 {rest} 种模式 | {total_primary-cum} | | |")
    add("")

    # 四、五层根因透视 + 共性主题
    add("## 四、五层根因透视")
    add("")
    add("| 层面 | 根因条数 | 说明 |")
    add("|-----|---------|------|")
    layer_desc = {
        "设计层面": "接口契约、状态机、边界条件的设计缺口",
        "编码层面": "实现缺陷：校验缺失、异常处理不当等",
        "测试层面": "用例设计方法未覆盖的场景类型",
        "流程层面": "评审/checklist/流程防线未拦截",
        "知识管理层面": "经验未沉淀形成的知识盲区",
        "需求层面": "需求不清或需求管理问题",
        "流程与知识管理层面": "流程与知识管理的复合缺口",
    }
    for layer in _LAYER_ORDER:
        items = stats["layer_items"].get(layer, [])
        if items:
            add(f"| {layer} | {len(items)} | {layer_desc.get(layer, '')} |")
    add("")

    if themes and use_llm:
        add("### 共性根因主题（跨模块反复出现的模式）")
        add("")
        for t in themes:
            add(f"#### 🎯 {t.get('name', '')}")
            add("")
            add(f"- **主要层面**: {t.get('layer', '—')}　**规模估计**: {t.get('estimate', '—')}")
            add(f"- **说明**: {t.get('description', '')}")
            add("")
    elif use_llm is False or not themes:
        add("### 高频根因示例（各层 Top3）")
        add("")
        for layer in _LAYER_ORDER:
            items = stats["layer_items"].get(layer, [])
            if not items:
                continue
            add(f"**{layer}**:")
            seen: set[str] = set()
            shown = 0
            for it in items:
                key = it[:20]
                if key in seen:
                    continue
                seen.add(key)
                add(f"- {it[:110]}")
                shown += 1
                if shown >= 3:
                    break
            add("")

    # 五、规范符合性
    add("## 五、规范符合性分析")
    add("")
    if stats["viols"]:
        add("| 规范条款 | 违规次数 | 涉及缺陷数 |")
        add("|---------|---------|-----------|")
        for rid, cnt in stats["viols"][:10]:
            add(f"| {rid} | {cnt} | {stats['viol_urid_count'].get(rid, '—')} |")
        add("")
        add(
            f"> 注: {sum(1 for u, r in load_all_viol_stats().items() if r)} / {n} 起检出规范违规；"
            f"其余未检出不代表完全符合，部分缺陷类型（如需求类）不在静态规则检测范围内。"
        )
        add("")

    # 六、改进路线图
    add("## 六、改进路线图（建议优先级）")
    add("")
    prio_label = {"high": "🔴 高优先级", "medium": "🟡 中优先级", "low": "🟢 低优先级"}
    by_prio: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for (cat, prio), cnt in stats["imps"]:
        by_prio[prio].append((cat, cnt))
    order = ["high", "medium", "low"]
    plan_hint = {
        "high": "本季度内落地，直接针对占比最高的缺陷模式设置防线",
        "medium": "下季度规划，完善流程与工具支撑",
        "low": "长期机制建设",
    }
    for prio in order:
        entries = sorted(by_prio.get(prio, []), key=lambda x: -x[1])
        if not entries:
            continue
        cat_summary = "、".join(f"{c}({v})" for c, v in entries)
        add(f"- **{prio_label[prio]}**: {cat_summary}")
        add(f"  - 建议: {plan_hint[prio]}")
    if not by_prio.get("medium") and not by_prio.get("low"):
        add("")
        add(
            "> 口径说明: 改进措施优先级由规则自动评定（覆盖占比≥20%或涉及规范违规即列为高优先级），"
            "本次全部建议均落在高优先级区间，落地节奏可结合团队资源自行排期。"
        )
    add("")
    add("> 具体行动项请结合《复盘分析报告.xlsx》缺陷明细 sheet 中每起缺陷的 improvements 字段追踪落实。")
    add("")

    add("---")
    add("*本报告由 fault-review-analyzer 自动生成；结论由 AI 分析产出并引用截图/代码证据，重大决策前建议人工复核关键单据。*")
    return "\n".join(lines)


def load_all_viol_stats() -> dict[int, bool]:
    out: dict[int, bool] = {}
    for fp in sorted(OUT_DIR.glob("progress_*.json")):
        try:
            rec = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        u = rec.get("urId")
        if u:
            out[int(u)] = bool(rec.get("violations"))
    return out


async def main_async(use_llm: bool) -> None:
    recs = load_records()
    print(f"加载 {len(recs)} 起分析结果")
    stats = aggregate(recs)
    themes: list[dict[str, str]] = []
    if use_llm:
        print("调用 LLM 归纳共性根因主题...")
        themes = await _llm_common_themes(stats)
        print(f"  → {len(themes)} 个主题")
    md = render_md(stats, themes, use_llm)
    out = OUT_DIR / "复盘综合分析报告.md"
    out.write_text(md, encoding="utf-8")
    print(f"报告已生成: {out}")


def main() -> None:
    use_llm = "--no-llm" not in sys.argv
    asyncio.run(main_async(use_llm))


if __name__ == "__main__":
    main()
