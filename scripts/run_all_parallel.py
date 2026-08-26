"""对全部泄漏缺陷并行批量跑程序分析（支持断点续跑 + 增量保存）。

利用 run_batch 的任务间并行机制（Semaphore + asyncio.gather）。
基于并发测试，官方 g-deepseek-v4-flash 并发 5 稳定且速度最优。

用法:
  python scripts/run_all_parallel.py all           # 跑全部 194 起（续跑跳过已完成）
  python scripts/run_all_parallel.py <urId> [urId] # 只跑指定单子
输出: output/progress_<urId>.json（每起增量）+ output/all_analysis_<timestamp>.json
"""

from __future__ import annotations

import asyncio
import glob
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

from src.analyzer import AnalysisPipeline, PipelineConfig
from src.config.manager import ConfigManager

OUT_DIR = Path(__file__).parent.parent / "output"
MAX_CONCURRENCY = 5  # 官方 g-deepseek-v4-flash 并发 5 稳定


def _load_existing() -> dict[int, dict]:
    """读取已有进度（增量文件 + 批量输出），返回 urId -> 记录。"""
    merged: dict[int, dict] = {}
    for f in glob.glob(str(OUT_DIR / "progress_*.json")):
        try:
            with open(f, encoding="utf-8") as fh:
                rec = json.load(fh)
            if not rec.get("error") and rec.get("root_causes"):
                merged[rec["urId"]] = rec
        except Exception:
            continue
    for f in glob.glob(str(OUT_DIR / "all_analysis_*.json")):
        try:
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
            for rec in data.get("results", []):
                if not rec.get("error") and rec.get("root_causes"):
                    merged[rec["urId"]] = rec
        except Exception:
            continue
    return merged


def _save_progress(rec: dict) -> None:
    """每完成一个单子立即写增量文件，防中断丢进度。"""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / f"progress_{rec['urId']}.json", "w", encoding="utf-8") as fh:
        json.dump(rec, fh, ensure_ascii=False, indent=2)


def _to_record(result) -> dict:
    """把 PipelineResult 转为可序列化记录。"""
    task_data = result.task_data or {}
    return {
        "urId": result.task_id,
        "error": result.error,
        "processing_time": result.processing_time,
        "title": task_data.get("title", ""),
        "description": task_data.get("description", ""),
        "has_code_change": bool(
            task_data.get("development")
            and task_data.get("development", {}).get("commits")
        ),
        "labels": result.labels or [],
        "root_causes": result.root_causes or [],
        "violations": result.violations or [],
        "code_change_analysis": result.code_change_analysis or {},
        "improvements": result.improvements or [],
        "standard_matches": result.standard_matches or [],
    }


async def run_all(urids: list[int]) -> list[dict]:
    """并行跑所有 urId，每完成一个增量保存。"""
    config_manager = ConfigManager()
    config = config_manager.load()

    pipeline_config = PipelineConfig(
        use_cache=True,
        use_llm=True,
        generate_labels=True,
        analyze_root_cause=True,
        analyze_root_cause_deep=False,
        check_rules=True,
        match_standards=True,
        generate_report=False,
        max_concurrency=MAX_CONCURRENCY,
    )

    pipeline = AnalysisPipeline(config_manager, pipeline_config)
    async with pipeline:
        semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
        completed: list[dict] = []

        async def run_one(tid: int) -> None:
            async with semaphore:
                logger.info(f"分析 urId={tid}")
                try:
                    result = await pipeline.run_single(tid)
                    rec = _to_record(result)
                    _save_progress(rec)
                    completed.append(rec)
                    logger.info(
                        f"  urId={tid} 完成: 根因{len(rec['root_causes'])} 违规{len(rec['violations'])} "
                        f"改进{len(rec['improvements'])} 耗时{rec['processing_time']:.0f}s"
                    )
                except Exception as e:
                    logger.error(f"urId={tid} 异常: {type(e).__name__} {e}")
                    completed.append({"urId": tid, "error": f"{type(e).__name__}: {e}"})

        await asyncio.gather(*[run_one(tid) for tid in urids])

    return completed


def _save_batch(records: list[dict], elapsed: float) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = OUT_DIR / f"all_analysis_{ts}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({"results": records, "elapsed_sec": elapsed}, f, ensure_ascii=False, indent=2)
    _append_batch_index(records, out_file, ts)
    return out_file


def _append_batch_index(records: list[dict], source_file: Path, ts: str) -> None:
    """把本次运行追加到 output/batches.json（原子写 + 按 batch_id 去重）。

    批次记录含：batch_id、name、created_at、source、urids、count。
    """
    urids = [
        r["urId"] for r in records if not r.get("error") and r.get("root_causes")
    ]
    if not urids:
        return
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    batch = {
        "batch_id": f"batch-{ts}",
        "name": f"分析批次 {created_at}",
        "created_at": created_at,
        "source": source_file.name,
        "urids": urids,
        "count": len(urids),
    }
    # 读现有 batches.json（损坏则忽略，重新建）
    batches_file = OUT_DIR / "batches.json"
    batches: list[dict] = []
    if batches_file.exists():
        try:
            batches = json.loads(batches_file.read_text(encoding="utf-8")).get("batches", [])
        except Exception:
            batches = []
    # 按 batch_id 去重（保留最新）
    dedup: dict[str, dict] = {b["batch_id"]: b for b in batches}
    dedup[batch["batch_id"]] = batch
    # 原子写
    tmp_file = OUT_DIR / "batches.json.tmp"
    tmp_file.write_text(
        json.dumps({"batches": list(dedup.values())}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp_file.replace(batches_file)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] != "all":
        urids = [int(x) for x in sys.argv[1:]]
        existing = {}
    else:
        data_file = Path(__file__).parent.parent / "data" / "all_urids.json"
        with open(data_file) as f:
            all_urids = json.load(f)["urids"]
        existing = _load_existing()
        urids = [u for u in all_urids if u not in existing]
        if not urids:
            print("全部样本均已分析完成，无需续跑。")
            sys.exit(0)
        print(f"已完成: {len(existing)} 起，本次续跑: {len(urids)} 起")

    logger.info(f"开始并行分析 {len(urids)} 起，并发 {MAX_CONCURRENCY}")
    start = time.time()
    records = asyncio.run(run_all(urids))
    elapsed = time.time() - start

    out_file = _save_batch(records, elapsed)

    ok = sum(1 for r in records if not r.get("error"))
    failed = [r["urId"] for r in records if r.get("error")]
    no_rc = [r["urId"] for r in records if not r.get("error") and not r.get("root_causes")]
    print(f"\n本次完成 {len(records)} 起（成功 {ok}，失败 {len(failed)}），耗时 {elapsed:.0f} 秒")
    if no_rc:
        print(f"无根因(需关注): {no_rc}")
    if failed:
        print(f"失败单子: {failed}")
    print(f"结果已保存: {out_file}")
