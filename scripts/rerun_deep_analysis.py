"""重跑指定故障单的深度根因分析（5层追问），验证事实纪律修复效果.

背景（案例 11955497）：深度分析曾把截图中短信模板的变量占位符
${UTM_LINK$$$ClaimVoucher} 误判为"变量映射逻辑缺陷"，并据此脑补出
"缓存写入未实现幂等性"的机制性根因。修复后链路：
ROOT_CAUSE_SYSTEM_PROMPT 事实纪律约束 + LLM 温度降至 0.1。
本脚本用修复后的链路重跑深度分析并就地更新 progress 文件（先备份）。

链路: AnalyzeHandler.analyze_root_cause_deep
    = API 拉取现有复盘结论 + 图片证据注入 + DeepRootCauseAnalyzer
    （带事实纪律 system prompt，与全量分析走完全相同代码路径）

用法:
    python scripts/rerun_deep_analysis.py 11955497 [urid2 ...]
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

from src.analyzer.handlers.analyze import AnalyzeHandler
from src.analyzer.llm_provider import create_llm_provider
from src.api.client import APIClient
from src.config.manager import ConfigManager

ROOT = Path(__file__).parent.parent
OUT_DIR = ROOT / "output"
# 真实缓存库位于 data/cache/（config.cache.storage 指向该目录）
CACHE_DB_CANDIDATES = [ROOT / "data" / "cache" / "cache.db", ROOT / "data" / "cache.db"]
MAX_TEMPERATURE = 0.2  # 用户要求：复盘分析温度必须低于 0.2

# 高风险脑补词汇（提示人工复核用，不自动判定；命中≠一定错误）
SUSPICIOUS_WORDS = [
    "幂等",
    "暗示",
    "极有可能",
    "映射缺陷",
    "格式异常",
    "并发场景",
]


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


def print_deep_result(tag: str, deep: dict[str, Any]) -> None:
    """打印深度分析结果供人工比对。"""
    print(f"\n===== {tag} =====")
    print(f"问题类别: {deep.get('problem_category', '')}")
    print(f"初始原因: {deep.get('initial_cause', '')}")
    for item in deep.get("deep_root_causes", []):
        print(f"\n[{item.get('layer', '')}]")
        print(f"  根因: {item.get('root_cause', '')}")
        print(f"  为什么: {item.get('why_reason', '')}")
        print(f"  证据: {item.get('evidence', '')}")
    print("\n改进建议:")
    for imp in deep.get("actionable_improvements", []):
        owner = imp.get("owner", "")
        priority = imp.get("priority", "")
        print(f"  - [{imp.get('type', '')}] {imp.get('action', '')} ({owner}/{priority})")
    print("checklist 建议:")
    for checklist in deep.get("checklist_recommendations", []):
        print(f"  - {checklist}")


def scan_suspicious(deep: dict[str, Any]) -> list[str]:
    """扫描新结论中的高风险脑补词汇，返回命中提示（供人工复核）。"""
    hits: list[str] = []
    for item in deep.get("deep_root_causes", []):
        text = " | ".join(
            str(item.get(key, "")) for key in ("root_cause", "why_reason", "evidence")
        )
        for word in SUSPICIOUS_WORDS:
            if word in text:
                hits.append(f"[{item.get('layer', '')}] 命中 '{word}': {text[:120]}")
    return hits


def update_progress(urid: int, deep: dict[str, Any], ts: str) -> Path:
    """备份并就地更新 progress 文件的 deep_root_causes 字段。"""
    fp = OUT_DIR / f"progress_{urid}.json"
    if not fp.exists():
        raise FileNotFoundError(f"progress 文件不存在: {fp}")
    backup = fp.parent / f"{fp.name}.bak_{ts}"
    shutil.copyfile(fp, backup)
    rec: dict[str, Any] = json.loads(fp.read_text(encoding="utf-8"))
    rec["deep_root_causes"] = deep
    rec["deep_analyzed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fp.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    return backup


async def run(urids: list[int]) -> None:
    """重跑每个 urId 的深度分析，打印新旧对比并更新 progress。"""
    os.chdir(ROOT)  # ConfigManager 依赖 cwd 定位 .env 与 config/config.yaml

    config = ConfigManager().load()
    provider = create_llm_provider(config.llm)
    if provider is None:
        raise RuntimeError("LLM provider 创建失败：未配置 llm.api_key")
    logger.info(f"LLM: model={config.llm.model} temperature={config.llm.temperature}")
    if config.llm.temperature > MAX_TEMPERATURE:
        raise RuntimeError(
            f"温度 {config.llm.temperature} 高于 {MAX_TEMPERATURE}，违反事实纪律要求，中止重跑"
        )

    async with APIClient(
        base_url=config.api.base_url,
        api_key=config.api.api_key,
        timeout=config.api.timeout,
    ) as client:
        handler = AnalyzeHandler(llm_provider=provider, api_client=client)
        for urid in urids:
            await _rerun_one(handler, urid)

    await provider.close()


async def _rerun_one(handler: AnalyzeHandler, urid: int) -> None:
    """重跑单个故障单：分析 → 对比 → 更新 progress。"""
    logger.info(f"===== 重跑深度分析 urId={urid} =====")
    task_data = load_task_from_cache(urid)
    if task_data is None:
        logger.warning(f"urId={urid} 缓存缺失，跳过")
        return

    old_fp = OUT_DIR / f"progress_{urid}.json"
    old_deep: dict[str, Any] = {}
    prior_root_causes: list[dict[str, Any]] = []
    if old_fp.exists():
        old_rec: dict[str, Any] = json.loads(old_fp.read_text(encoding="utf-8"))
        old_deep = old_rec.get("deep_root_causes") or {}
        # 普通链路结论（基于代码 diff）作为深度分析的事实锚点，
        # 与 pipeline 运行时传 result.root_causes 的行为一致
        prior_root_causes = old_rec.get("root_causes") or []

    new_deep = await handler.analyze_root_cause_deep(task_data, prior_root_causes=prior_root_causes)
    if not new_deep:
        # 准确性优先：LLM 失败时绝不覆盖旧数据
        logger.error(f"urId={urid} 深度分析返回空结果，保留旧数据")
        return

    if old_deep:
        print_deep_result("旧结论（修复前）", old_deep)
    print_deep_result("新结论（事实纪律修复后）", new_deep)

    hits = scan_suspicious(new_deep)
    if hits:
        print("\n[人工复核提示] 新结论命中高风险表述（需人工判断是否有事实依据）:")
        for hit in hits:
            print(f"  - {hit}")
    else:
        print("\n[人工复核提示] 新结论未命中高风险表述词表。")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = update_progress(urid, new_deep, ts)
    print(f"\n已更新 progress_{urid}.json（原文件备份为 {backup.name}）")


def main() -> None:
    """Entry point."""
    args = [int(arg) for arg in sys.argv[1:] if arg.isdigit()]
    if not args:
        print(__doc__)
        raise SystemExit(1)
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
