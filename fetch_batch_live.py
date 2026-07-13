#!/usr/bin/env python
"""批量获取故障单数据"""

import asyncio
from dotenv import load_dotenv

load_dotenv(override=True)

from src.config.manager import ConfigManager
from src.api.client import APIClient
from src.cache.manager import CacheManager
from pathlib import Path

# 要获取的故障单列表
TASK_IDS = [
    11748712,
    11745664,
    11743724,
    11742292,
    11740454,
    11740449,
    11739485,
    11739484,
    11739476,
    11738437,
    11735590,
    11733177,
    11731908,
    11729459,
    11727858,
]


async def fetch_tasks():
    config_manager = ConfigManager()
    config = config_manager.load()

    cache_path = Path(config.cache.db_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_manager = CacheManager(db_path=cache_path, ttl=config.cache.ttl)

    print(f"准备获取 {len(TASK_IDS)} 个故障单...")
    print()

    success = 0
    failed = 0
    skipped = 0

    async with APIClient(
        base_url=config.api.base_url,
        api_key=config.api.api_key,
        timeout=config.api.timeout,
        retry=config.api.retry,
    ) as client:
        for task_id in TASK_IDS:
            # 检查缓存
            cached = cache_manager.get_task(task_id)
            if cached:
                print(f"  任务 {task_id}: [yellow]已在缓存中，跳过[/yellow]")
                skipped += 1
                continue

            try:
                task = await client.get_task(task_id)
                if task:
                    cache_manager.save_task(task_id, task.model_dump(mode="json"))
                    print(f"  任务 {task_id}: [green]成功[/green] - {task.title[:30]}...")
                    success += 1
                else:
                    print(f"  任务 {task_id}: [red]未找到[/red]")
                    failed += 1
            except Exception as e:
                print(f"  任务 {task_id}: [red]失败: {e}[/red]")
                failed += 1

    print()
    print(f"获取完成: 成功 {success}, 跳过 {skipped}, 失败 {failed}")

    # 显示缓存统计
    stats = cache_manager.get_stats()
    print(f"缓存统计: 总计 {stats['total_entries']}, 有效 {stats['valid_entries']}")


if __name__ == "__main__":
    asyncio.run(fetch_tasks())
