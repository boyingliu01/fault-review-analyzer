"""对抽样样本并行批量跑程序分析。

利用 run_batch 的任务间并行机制（Semaphore + asyncio.gather）。
基于并发测试，本地 LLM 服务最大并发约 3，故 max_concurrency=3。

用法: python scripts/run_sample_parallel.py [urId...]
  无参数: 跑 data/sample_urids.json 全部
  传 urId: 只跑指定的（可多个）
输出: output/sample_analysis_<timestamp>.json
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

from src.analyzer import AnalysisPipeline, PipelineConfig
from src.config.manager import ConfigManager

MAX_CONCURRENCY = 3  # 本地 LLM 服务并发上限约 3-4，超过触发 429


async def run_all(urids: list[int]) -> list[dict]:
    """用 run_batch 并行跑所有 urId。"""
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
        generate_report=False,  # 验证阶段不需要报告，加速
        max_concurrency=MAX_CONCURRENCY,
    )

    pipeline = AnalysisPipeline(config_manager, pipeline_config)
    async with pipeline:
        results = await pipeline.run_batch(urids)

    # 转换为可序列化记录
    records = []
    for result in results:
        task_data = result.task_data or {}
        records.append(
            {
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
        )
    return records


if __name__ == "__main__":
    if len(sys.argv) > 1:
        urids = [int(x) for x in sys.argv[1:]]
    else:
        sample_file = Path(__file__).parent.parent / "data" / "sample_urids.json"
        with open(sample_file) as f:
            urids = json.load(f)["urids"]

    logger.info(f"开始并行分析 {len(urids)} 起，并发 {MAX_CONCURRENCY}")
    start = time.time()
    records = asyncio.run(run_all(urids))
    elapsed = time.time() - start

    out_dir = Path(__file__).parent.parent / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = out_dir / f"sample_analysis_{ts}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({"results": records, "elapsed_sec": elapsed}, f, ensure_ascii=False, indent=2)

    ok = sum(1 for r in records if not r.get("error"))
    failed = [r["urId"] for r in records if r.get("error")]
    print(f"\n完成 {len(records)} 起（成功 {ok}，失败 {len(failed)}），耗时 {elapsed:.0f} 秒")
    if failed:
        print(f"失败单子: {failed}")
    print(f"结果已保存: {out_file}")
