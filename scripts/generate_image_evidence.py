#!/usr/bin/env python
"""预生成全部含图片故障单的图片证据缓存。

用于历史数据重跑前的缓存预热：批量调用视觉 LLM 读取故障单截图，
把提取结果写入 output/cos_images/<urId>/image_evidence.json。

这样后续用 run_all_parallel 重跑分析时，ImageEvidenceExtractor 能直接复用缓存，
无需现场读图，加快批量重跑。

用法:
    python scripts/generate_image_evidence.py [--urid 11757373 ...] [--concurrency 4]
        --urid        可选，只处理指定单子；缺省处理所有含占位符图片的单子
        --concurrency 视觉读图并发数（默认 3，本地视觉模型并发不宜过高）
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

from src.analyzer.image_evidence import ImageEvidenceExtractor, extract_image_refs

OUT_DIR = Path(__file__).parent.parent / "output"


async def generate_one(ext: ImageEvidenceExtractor, urid: int, sem: asyncio.Semaphore) -> bool:
    """生成单个单子的图片证据缓存。已存在缓存则跳过。"""
    fp = OUT_DIR / f"progress_{urid}.json"
    if not fp.exists():
        return False
    try:
        rec = json.loads(fp.read_text(encoding="utf-8"))
    except Exception:
        return False

    # 已有缓存 → 跳过
    cache_path = OUT_DIR / "cos_images" / str(urid) / "image_evidence.json"
    if cache_path.exists():
        logger.info("urId={} 已有缓存，跳过", urid)
        return True

    if not extract_image_refs(rec.get("description", "")):
        logger.info("urId={} 无占位符图片，跳过", urid)
        return False

    async with sem:
        try:
            evidence = await ext.get_image_evidence(rec)
            if evidence:
                logger.info("urId={} 生成证据（{} 字符）", urid, len(evidence))
                return True
            logger.warning("urId={} 证据为空", urid)
            return False
        except Exception as e:
            logger.error("urId={} 生成失败: {}", urid, str(e)[:100])
            return False


async def main() -> None:
    parser = argparse.ArgumentParser(description="预生成图片证据缓存")
    parser.add_argument("--urid", nargs="*", type=int, help="只处理指定单子")
    parser.add_argument("--concurrency", type=int, default=3, help="并发数")
    args = parser.parse_args()

    if args.urid:
        urids = args.urid
    else:
        urids = []
        for fp in sorted(OUT_DIR.glob("progress_*.json")):
            try:
                rec = json.loads(fp.read_text(encoding="utf-8"))
            except Exception:
                continue
            if rec.get("urId") and extract_image_refs(rec.get("description", "")):
                urids.append(rec["urId"])

    logger.info("处理 {} 个含图片单子，并发 {}", len(urids), args.concurrency)
    ext = ImageEvidenceExtractor()
    sem = asyncio.Semaphore(args.concurrency)

    # 分批处理，避免一次创建过多任务
    BATCH = 20
    done = 0
    for i in range(0, len(urids), BATCH):
        chunk = urids[i : i + BATCH]
        results = await asyncio.gather(*[generate_one(ext, u, sem) for u in chunk])
        done += sum(1 for r in results if r)
        logger.info("进度 {}/{}", min(i + BATCH, len(urids)), len(urids))

    logger.info("完成：成功生成 {} / {} 个单子的图片证据", done, len(urids))


if __name__ == "__main__":
    asyncio.run(main())
