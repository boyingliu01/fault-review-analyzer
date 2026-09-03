#!/usr/bin/env python
"""对故障单跑 5 层深度根因分析（analyze_root_cause_deep），结果合并进 progress 文件。

特点:
    - 断点续跑: 已有 deep_root_causes 的单子自动跳过，可反复调用直至完成
    - 只跑深度分析: labels/root_cause/规则/规范匹配均关闭，避免重复 LLM 消耗
    - 图片证据自动注入: pipeline 内部会读取截图证据并入 deep prompt
    - 合并保存: 仅更新 deep_root_causes 字段，保留既有分析结论

用法:
    python scripts/run_deep_analysis.py              # 全部 181 起（续跑）
    python scripts/run_deep_analysis.py --urid 11757373 11773243   # 指定单子强制重跑

输出:
    更新 output/progress_<urId>.json 的 deep_root_causes / deep_analyzed_at 字段
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

from src.analyzer import AnalysisPipeline, PipelineConfig
from src.config.manager import ConfigManager

OUT_DIR = Path(__file__).parent.parent / "output"
MAX_CONCURRENCY = 5


def _all_urids() -> list[int]:
    data_file = Path(__file__).parent.parent / "data" / "all_urids.json"
    with data_file.open(encoding="utf-8") as f:
        return [int(u) for u in json.load(f)["urids"]]


def _pending_urids(force_urids: list[int] | None) -> list[int]:
    """待跑清单：指定 urid 强制重跑；否则收集尚无 deep_root_causes 的单子。"""
    if force_urids:
        return force_urids
    pending = []
    for fp in sorted(OUT_DIR.glob("progress_*.json")):
        try:
            rec = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        if rec.get("urId") and not rec.get("deep_root_causes"):
            pending.append(int(rec["urId"]))
    return pending


async def run_deep(urids: list[int]) -> dict[str, Any]:
    config_manager = ConfigManager()
    pipeline_config = PipelineConfig(
        use_cache=True,
        use_llm=True,
        generate_labels=False,
        analyze_root_cause=False,
        analyze_root_cause_deep=True,
        check_rules=False,
        match_standards=False,
        generate_report=False,
        max_concurrency=MAX_CONCURRENCY,
    )
    pipeline = AnalysisPipeline(config_manager, pipeline_config)
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
    stats = {"done": 0, "ok": 0, "empty": 0, "error": 0}
    errors: list[str] = []

    async with pipeline:

        async def one(tid: int) -> None:
            async with semaphore:
                try:
                    result = await pipeline.run_single(tid)
                except Exception as e:
                    stats["error"] += 1
                    errors.append(f"{tid}: {type(e).__name__} {str(e)[:60]}")
                    return
                stats["done"] += 1
                deep = result.deep_root_causes
                fp = OUT_DIR / f"progress_{tid}.json"
                try:
                    rec = json.loads(fp.read_text(encoding="utf-8"))
                except Exception as e:
                    stats["error"] += 1
                    errors.append(f"{tid}: progress 读取失败 {e}")
                    return
                if result.error:
                    stats["error"] += 1
                    errors.append(f"{tid}: {result.error}")
                    return
                if not deep:
                    # 深度分析失败(异常被 handler 吞掉返回 {}) → 标记空，下次续跑重试
                    stats["empty"] += 1
                    errors.append(f"{tid}: deep 结果为空")
                    return
                layers = len(deep.get("deep_root_causes", []))
                rec["deep_root_causes"] = deep
                rec["deep_analyzed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                fp.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
                stats["ok"] += 1
                logger.info(
                    "urId={} ✓ 深度完成 分类={} 层数={}",
                    tid,
                    deep.get("problem_category", "?"),
                    layers,
                )

        await asyncio.gather(*[one(tid) for tid in urids])

    return {"stats": stats, "errors": errors}


async def main() -> None:
    args = sys.argv[1:]
    force: list[int] | None = None
    if "--urid" in args:
        i = args.index("--urid")
        force = [int(x) for x in args[i + 1 :]]

    urids = _pending_urids(force)
    print(f"本次深度分析 {len(urids)} 起 (并发 {MAX_CONCURRENCY})")
    if not urids:
        print("全部单子已有深度分析结果。")
        return

    start = time.time()
    out = await run_deep(urids)
    s, errs = out["stats"], out["errors"]
    print(
        f"\n完成 {s['done']} 起: 成功 {s['ok']}, 空 {s['empty']}, 错误 {s['error']}，耗时 {time.time() - start:.0f}s"
    )
    if errs:
        print("问题清单:")
        for e in errs[:30]:
            print(f"  - {e}")
    remaining = len(_pending_urids(None))
    print(f"剩余未覆盖: {remaining}")


if __name__ == "__main__":
    asyncio.run(main())
