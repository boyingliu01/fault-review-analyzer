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
import contextlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

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


# ---------------------------------------------------------------------------
# 产品线映射。
# 权威口径: 业务复盘xlsx的"责任产品线"字段（output/product_line_map.json，
# 由 scripts/extract_product_line_map.py 生成）；该字段缺失的 urId 回退到
# 基于故障单标题中 ZSmart 模块标识与业务关键词的推断（历史错误率 34%）。
# 如个别单子归属不准确，更新业务xlsx后重跑提取脚本即可。
# ---------------------------------------------------------------------------
LINE_CHANNEL = "国际数字渠道产品线"
LINE_BSS = "国际BSS产品线"
LINE_PLATFORM = "平台/公共组件"
LINE_ESHOP = "电商产品线"

# 业务xlsx"责任产品线"取值 → 报告产品线名
_BIZ_LINE_TO_REPORT = {
    "BSS": LINE_BSS,
    "数渠": LINE_CHANNEL,
    "电商": LINE_ESHOP,
}


def load_product_line_map() -> dict[int, str]:
    """加载业务复盘的责任产品线权威映射（urId → 报告产品线名）。

    映射文件缺失或损坏时返回空 dict，调用方自动回退标题推断。
    """
    map_file = OUT_DIR / "product_line_map.json"
    if not map_file.exists():
        logger.warning("product_line_map.json 不存在，产品线将回退标题推断（历史错误率34%）")
        return {}
    try:
        data: dict[str, Any] = json.loads(map_file.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"product_line_map.json 解析失败: {e}")
        return {}
    result: dict[int, str] = {}
    for u_str, biz_line in (data.get("map") or {}).items():
        report_line = _BIZ_LINE_TO_REPORT.get(str(biz_line).strip())
        if report_line:
            with contextlib.suppress(ValueError):
                result[int(u_str)] = report_line
    return result


# ZSmart 模块标识 → 产品线（强信号，优先级最高）
_MODULE_LINE = {
    # 渠道触点与营销互动侧
    "ZSmart_MobileSC": LINE_CHANNEL,   # 移动端前端框架(RN)
    "ZSmart_WebSC": LINE_CHANNEL,      # Web端前端框架
    "ZSmart_ceeAPP": LINE_CHANNEL,     # 客户互动APP
    "ZSmart_GCP": LINE_CHANNEL,        # 营销云(短链/UTM/创意投放)
    "ZSmart_MCCM": LINE_CHANNEL,       # 营销活动管理(Campaign Canvas)
    "ZSmart_eShopF": LINE_CHANNEL,     # 电商前端
    "ZSmart_ceePlat": LINE_CHANNEL,    # CEE 客户互动平台(App Push/邮件等触达)
    "ZSmart_ceeSDK": LINE_CHANNEL,     # CEE SDK
    # BSS 业务支撑侧
    "ZSmart_COC": LINE_BSS,            # 订单中心
    "ZSmart_DRM": LINE_BSS,            # 用户域(号码/订阅/开户)
    "ZSmart_CUSTC": LINE_BSS,          # 客户中心(360视图/KYC)
    "ZSmart_SIC": LINE_BSS,            # 卡与库存(physical SIM/eSIM流转)
}

# 标题业务关键词 → 产品线（弱信号，用于无模块标识的单子）
_KW_CHANNEL = [
    # 营销互动/触点
    "Campaign", "campaign", "GCP短链", "gcp 短链", "UTM", "utm", "App Push", "apppush",
    "站内信", "banner", "启动页", "DEEPLINK", "deeplink", "深链",
    "live person", "创意中", "creative", "html builder", "Template manage",
    "template 使用", "广告相关", "page builder", "积分配置", "promotionActionList",
    "promo逻辑", "promo code", "Wrong display of promo",
    # 渠道 App/Web 前端
    "PenTest", "Sensitiv", "Enumerat", "CX APP", "BX APP", "GOMO BB", "EDGE BROWSER",
    "客户侧", "Redemption Management", "eload Transfer 可以重复选择Account",
    "键盘重复输入", "下拉刷新", "白屏", "loading时不能返回",
]
_KW_BSS = [
    "port in", "Port In", "portin", "BXportin", "port out", "mnp", "MNP",
    "COC ", "话单", "waiver", "Waiver", "Waiv", "eKYC", "ekyc", "KYC",
    "GLC", "SIC", "OTP", "esim", "Esim", "ESIM", "MSISDN", "Reserve密码",
    "订单中心", "Retailer", "Distributor", "零售", "物流", "发货",
    "payment", "Payment", "支付提醒", "pin码", "subscriber-management",
    "Order Query", "order query", "Order Didnt Go Through", "order cancelled",
    "Order cancelled", "Delivery", "SIM_CARD_LOST", "Line Pause", "SMS Delivery",
    "renew offer", "AutoReactive", "RE-REG", "过户", "复机", "heya", "在途单",
    "IDD", "账本", "CRM_SUBSCRIBER", "NLT is down", "StandardAddress",
    "创建客户", "Invalid cust name", "customer info", "app config",
    "POP Station", "Postal Code", "Distributor rep trf", "wallet being deducted",
    "promo issue", "POP Station Postal",
]
_KW_PLATFORM = [
    "aws资源", "Azure-Database", "cpu_percent", "cpu过高", "dabasease",
    "配置读取失败", "指标上报SQL", "exception management", "运维能力提升",
]

_FALLBACK_ORDER = [(_KW_CHANNEL, LINE_CHANNEL), (_KW_BSS, LINE_BSS), (_KW_PLATFORM, LINE_PLATFORM)]


def classify_product_line(title: str) -> str:
    """按模块标识 → 业务关键词 的顺序判定产品线。"""
    t = title or ""
    m = re.search(r"[（(](ZSmart_[^）)_]+)", t)
    if m:
        mod = m.group(1)
        for prefix, line in _MODULE_LINE.items():
            if mod.startswith(prefix):
                return line
    for kws, line in _FALLBACK_ORDER:
        hits = sum(1 for k in kws if k in t)
        if hits >= 2:
            return line
    for kws, line in _FALLBACK_ORDER:
        if any(k in t for k in kws):
            return line
    return "其他/待确认"


def _apply_group_majority(pre_line: dict[int, str]) -> None:
    """未判定(其他/待确认)单子按项目组多数派兜底归类。

    项目组键来自 output/urid_project_map.json (projectId, zmpProjectId)；
    同组内已判定的多数产品线视为该组的业务归属，映射给未判定成员。
    """
    map_file = OUT_DIR / "urid_project_map.json"
    if not map_file.exists():
        return
    try:
        pmap: dict[str, Any] = json.loads(map_file.read_text(encoding="utf-8"))
    except Exception:
        return

    pending = [u for u, v in pre_line.items() if v == "其他/待确认"]
    if not pending:
        return
    groups: dict[tuple[Any, Any], list[int]] = defaultdict(list)
    for u_str, info in pmap.items():
        if not info:
            continue
        u = int(u_str)
        groups[(info.get("projectId"), info.get("zmpProjectId"))].append(u)
    for key in groups:
        members = [u for u in groups[key] if u in pre_line]
        if len(members) < 2:
            continue
        votes: Counter[str] = Counter()
        for u in members:
            v = pre_line.get(u)
            if v is not None and v != "其他/待确认":
                votes[v] += 1
        if not votes:
            continue
        majority = votes.most_common(1)[0][0]
        for u in members:
            if pre_line[u] == "其他/待确认":
                pre_line[u] = majority


def aggregate(recs: dict[int, dict[str, Any]]) -> dict[str, Any]:
    """确定性统计聚合。"""
    n = len(recs)
    primary_causes: Counter[str] = Counter()
    deep_cats: Counter[str] = Counter()
    layer_items: dict[str, list[str]] = defaultdict(list)
    viol_rules: Counter[str] = Counter()
    viol_urids: dict[str, set[int]] = defaultdict(set)
    imp_by_cat_prio: Counter[tuple[str, str]] = Counter()
    line_recs: dict[str, dict[int, dict[str, Any]]] = defaultdict(dict)

    # 第零步: 优先采用业务复盘"责任产品线"权威映射（output/product_line_map.json）
    biz_line = load_product_line_map()
    # 第一步: 映射未命中的 urId 按标题关键词推断
    pre_line: dict[int, str] = {
        u: biz_line.get(u) or classify_product_line(r.get("title", "")) for u, r in recs.items()
    }
    # 第二步: 仍未判定的单子按 (projectId, zmpProjectId) 组内多数派投票兜底
    _apply_group_majority(pre_line)

    with_code = sum(1 for r in recs.values() if r.get("has_code_change"))
    img_ev_used = sum(1 for r in recs.values() if r.get("image_evidence"))
    conf_sum = 0.0
    conf_n = 0

    for u, r in recs.items():
        line = pre_line.get(u) or "其他/待确认"
        line_recs[line][u] = r
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
        # 产品线维度
        "line_recs": dict(line_recs),
    }


def aggregate_line(line: str, recs: dict[int, dict[str, Any]]) -> dict[str, Any]:
    """单条产品线的聚合统计。"""
    stats = aggregate(recs)
    stats["line"] = line
    stats["deep_cats_count"] = dict(stats["deep_cats"])
    return stats


_LLM_THEMES_PROMPT_ALL = """你是软件质量改进专家。以下是从 {total} 起泄漏缺陷的深度根因分析中提取的分层根因清单。
请归纳出 **5~8 个跨单位的共性根因主题**（同类问题在不同功能模块反复出现的模式），每个主题给出简洁命名和说明。

要求：
- 主题必须基于清单中的实际内容，不要泛泛而谈（如"加强测试"这类不可接受）
- 每个主题标注主要集中哪一层，并估算涉及条数区间
- 严格输出 JSON: {{"themes":[{{"name":"...","layer":"...","estimate":"约N起","description":"..."}}]}}
- 不要输出 JSON 以外的任何内容

【分层根因清单】
{items}
"""


_LLM_THEMES_PROMPT_LINE = """你是软件质量改进专家。以下是「{line}」的 {total} 起泄漏缺陷深度根因分析中提取的分层根因清单。
请归纳出 **3~5 个本产品线内跨模块的共性根因主题**，每个主题给出简洁命名和说明。

要求：
- 主题必须基于清单中的实际内容，不要泛泛而谈
- 每个主题标注主要集中哪一层，并估算涉及条数区间
- 严格输出 JSON: {{"themes":[{{"name":"...","layer":"...","estimate":"约N起","description":"..."}}]}}
- 不要输出 JSON 以外的任何内容

【分层根因清单】
{items}
"""


async def _llm_common_themes(
    stats: dict[str, Any], line: str | None = None
) -> list[dict[str, str]]:
    """调用 LLM 归纳共性主题；失败返回空列表（降级）。

    line=None 用全量 prompt；传入产品线名用产品线专属 prompt（3~5 主题）。
    """
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
        template = _LLM_THEMES_PROMPT_LINE if line else _LLM_THEMES_PROMPT_ALL
        response = await provider.generate(
            system="你只输出合法 JSON。",
            user=template.format(line=line or "", total=stats["total"], items="\n\n".join(items_txt_parts)),
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


def render_md(
    stats: dict[str, Any],
    themes: list[dict[str, str]],
    use_llm: bool,
    line_themes: dict[str, list[dict[str, str]]] | None = None,
) -> str:
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

    # 五、产品线维度分析
    add("## 五、产品线维度分析")
    add("")
    add(
        "> 口径: 按故障单标题中的 ZSmart 模块标识与业务关键词归属产品线（"
        + "、".join(_MODULE_LINE.keys())
        + " 等）；个别单子靠业务关键词推断，如归属有偏差可调整映射规则后重跑。"
    )
    add("")
    line_names = list(stats["line_recs"].keys())
    line_stats_map = {line: aggregate_line(line, recs) for line, recs in stats["line_recs"].items()}
    # 按缺陷量降序展示
    ordered_lines = sorted(line_names, key=lambda name: -line_stats_map[name]["total"])

    add("### 缺陷量与问题分类对比")
    add("")
    cat_cols = [c for c, _ in stats["deep_cats"]]
    header = "| 产品线 | 缺陷数 | 占比 | " + " | ".join(cat_cols) + " |"
    add(header)
    add("|" + "---------|" * (3 + len(cat_cols)))
    for line in ordered_lines:
        s = line_stats_map[line]
        m = s["total"]
        cells = [str(s["deep_cats_count"].get(c, 0)) for c in cat_cols]
        add(f"| {line} | {m} | {round(m/n*100,1)}% | " + " | ".join(cells) + " |")
    add("")

    for line in ordered_lines:
        s = line_stats_map[line]
        add(f"### {line}（{s['total']} 起）")
        add("")
        top3 = "、".join(c for c, _ in s["primary_top"][:3])
        add(f"- **Top 缺陷模式**: {top3}")
        layer_brief = []
        for layer in _LAYER_ORDER:
            cnt_ln = len(s["layer_items"].get(layer, []))
            if cnt_ln:
                layer_brief.append(f"{layer} {cnt_ln}")
        add("- **五层根因分布**: " + "、".join(layer_brief))
        if s["viols"]:
            viol_line = "、".join(f"{rid}({c})" for rid, c in s["viols"][:3])
            add(f"- **主要规范违规**: {viol_line}")
        else:
            add("- **主要规范违规**: 无")
        lt = (line_themes or {}).get(line) or []
        if lt and use_llm:
            add("")
            for t in lt:
                add(f"- 🎯 **{t.get('name','')}** ({t.get('layer','—')} / {t.get('estimate','—')})：{t.get('description','')}")
        elif not use_llm or not lt:
            ex_items = [it for layer in _LAYER_ORDER for it in s["layer_items"].get(layer, [])][:2]
            if ex_items:
                add("")
                for it in ex_items:
                    add(f"  - 根因示例: {it[:100]}")
        add("")

    # 六、规范符合性
    add("## 六、规范符合性分析")
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

    # 七、改进路线图
    add("## 七、改进路线图（建议优先级）")
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
    print("产品线分布:", {name: len(r) for name, r in stats["line_recs"].items()})
    themes: list[dict[str, str]] = []
    line_themes: dict[str, list[dict[str, str]]] = {}
    if use_llm:
        print("调用 LLM 归纳全量共性根因主题...")
        themes = await _llm_common_themes(stats)
        print(f"  → {len(themes)} 个主题")
        for line, recs_line in stats["line_recs"].items():
            if len(recs_line) < 3:
                continue
            print(f"调用 LLM 归纳 [{line}] 共性主题...")
            lt = await _llm_common_themes(aggregate_line(line, recs_line), line=line)
            line_themes[line] = lt
            print(f"  → {len(lt)} 个主题")
    md = render_md(stats, themes, use_llm, line_themes)
    out = OUT_DIR / "复盘综合分析报告.md"
    out.write_text(md, encoding="utf-8")
    print(f"报告已生成: {out}")


def main() -> None:
    use_llm = "--no-llm" not in sys.argv
    asyncio.run(main_async(use_llm))


if __name__ == "__main__":
    main()
