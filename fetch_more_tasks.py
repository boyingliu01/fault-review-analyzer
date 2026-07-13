#!/usr/bin/env python
"""获取额外的故障单（逐个获取，更稳定）"""

import asyncio
import httpx
from dotenv import load_dotenv
import os
from pathlib import Path
import json
import time

load_dotenv(override=True)

TOKEN = os.getenv("DEVCLOUD_TOKEN")
BASE_URL = "https://dev.iwhalecloud.com"
API_PREFIX = "/portal/ai-gateway/devspace/rpc/v3/work-item"

# 要额外获取的任务（跳过已缓存的）
TASK_IDS = [
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


async def fetch_task(client: httpx.AsyncClient, task_id: int) -> dict:
    """获取单个任务"""
    try:
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/{task_id}/detail",
            json={},
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": TOKEN if TOKEN.startswith("Bearer ") else f"Bearer {TOKEN}",
            },
            timeout=60,
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 200 and data.get("data"):
                return {
                    "task_id": task_id,
                    "task_no": str(task_id),
                    "title": data["data"].get("title", ""),
                    "description": data["data"].get("description", ""),
                    "status": data["data"].get("status", ""),
                    "task_src": data["data"].get("taskSrc", ""),
                    "created_date": data["data"].get("createdDate", ""),
                    "finish_date": data["data"].get("finishDate", ""),
                }
    except Exception as e:
        print(f"    {task_id}: 跳过 ({str(e)[:30]})")
    return None


async def main():
    print(f"准备获取 {len(TASK_IDS)} 个额外故障单...")
    print()

    tasks_data = []

    # 逐个获取，更稳定
    async with httpx.AsyncClient() as client:
        for i, task_id in enumerate(TASK_IDS, 1):
            print(f"[{i}/{len(TASK_IDS)}] 获取 {task_id}...", end=" ")
            result = await fetch_task(client, task_id)
            if result:
                tasks_data.append(result)
                print(f"✓ {result['title'][:30]}...")
            else:
                print("✗ 失败")
            await asyncio.sleep(0.5)  # 避免请求过快

    print()
    print(f"成功获取: {len(tasks_data)} / {len(TASK_IDS)}")

    # 追加到现有数据
    output_file = Path("output/phase2_live/tasks_data.json")
    existing_data = []
    if output_file.exists():
        with open(output_file, "r", encoding="utf-8") as f:
            existing_data = json.load(f)

    all_data = existing_data + tasks_data

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    print(f"总共已有: {len(all_data)} 个任务")
    print(f"数据已保存: {output_file}")

    return tasks_data


if __name__ == "__main__":
    tasks = asyncio.run(main())
