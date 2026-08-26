"""对抽样样本串行批量跑程序分析（支持断点续跑）。

串行执行以保证结果正确（本地 LLM 模型偶发不稳定，并行会放大失败率）。
已通过重试机制处理偶发空/不完整响应。

用法:
  python scripts/run_sample_analysis.py all           # 跑全部 25 起（续跑跳过已完成的）
  python scripts/run_sample_analysis.py <urId> [urId] # 只跑指定单子
输出: output/sample_analysis_<timestamp>.json
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


def _load_existing_results() -> dict[int, dict]:
    """读取已有的输出文件，返回 urId -> 结果记录 的映射。"""
    merged: dict[int, dict] = {}
    # 读取增量进度文件（每个单子一个）
    for f in glob.glob(str(OUT_DIR / "progress_*.json")):
        try:
            with open(f, encoding="utf-8") as fh:
                rec = json.load(fh)
            if not rec.get("error") and rec.get("root_causes"):
                merged[rec["urId"]] = rec
        except Exception:
            continue
    # 读取批量输出文件
    for f in glob.glob(str(OUT_DIR / "sample_analysis_*.json")):
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
    """每完成一个单子立即写入增量进度文件。"""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    f = OUT_DIR / f"progress_{rec['urId']}.json"
    with open(f, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, ensure_ascii=False, indent=2)


async def run_one(pipeline: AnalysisPipeline, tid: int) -> dict:
    """串行跑单个 urId。"""
    logger.info(f"分析 urId={tid}")
    result = await pipeline.run_single(tid)
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
    """串行跑所有 urId，跳过已完成的。"""
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
    )

    pipeline = AnalysisPipeline(config_manager, pipeline_config)
    async with pipeline:
        results = []
        for i, tid in enumerate(urids):
            try:
                rec = await run_one(pipeline, tid)
                results.append(rec)
                _save_progress(rec)  # 增量保存，防中途中断丢进度
                logger.info(
                    f"  [{i+1}/{len(urids)}] urId={tid} 完成: "
                    f"根因{len(rec['root_causes'])}个 违规{len(rec['violations'])}个 "
                    f"改进{len(rec['improvements'])}条 耗时{rec['processing_time']:.0f}s"
                )
            except Exception as e:
                logger.error(f"urId={tid} 异常: {type(e).__name__} {e}")
                results.append({"urId": tid, "error": f"{type(e).__name__}: {e}"})
    return results


def _save(records: list[dict], elapsed: float) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = OUT_DIR / f"sample_analysis_{ts}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({"results": records, "elapsed_sec": elapsed}, f, ensure_ascii=False, indent=2)
    return out_file


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] != "all":
        urids = [int(x) for x in sys.argv[1:]]
        existing = {}
    else:
        sample_file = Path(__file__).parent.parent / "data" / "sample_urids.json"
        with open(sample_file) as f:
            all_urids = json.load(f)["urids"]
        existing = _load_existing_results()
        urids = [u for u in all_urids if u not in existing]
        if not urids:
            print("所有样本均已分析完成，无需续跑。")
            sys.exit(0)
        print(f"已完成的样本: {len(existing)} 起，本次续跑: {len(urids)} 起")
        for u in urids:
            print(f"  待跑: {u}")

    logger.info(f"开始串行分析 {len(urids)} 起")
    start = time.time()
    records = asyncio.run(run_all(urids))
    elapsed = time.time() - start

    out_file = _save(records, elapsed)

    ok = sum(1 for r in records if not r.get("error"))
    failed = [r["urId"] for r in records if r.get("error")]
    no_rc = [r["urId"] for r in records if not r.get("error") and not r.get("root_causes")]
    print(f"\n本次完成 {len(records)} 起（成功 {ok}，失败 {len(failed)}），耗时 {elapsed:.0f} 秒")
    if no_rc:
        print(f"无根因(需关注): {no_rc}")
    if failed:
        print(f"失败单子: {failed}")
    print(f"结果已保存: {out_file}")
