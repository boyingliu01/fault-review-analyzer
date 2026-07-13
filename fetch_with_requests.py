#!/usr/bin/env python
"""使用 requests 库获取故障单（更稳定）"""

import requests
from dotenv import load_dotenv
import os
from pathlib import Path
import json
import time

load_dotenv(override=True)

TOKEN = os.getenv("DEVCLOUD_TOKEN")
BASE_URL = "https://dev.iwhalecloud.com"
API_PREFIX = "/portal/ai-gateway/devspace/rpc/v3/work-item"

# 要获取的任务（15个用于阶段2）
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
    11727062,
    11727055,
]


def fetch_task(task_id: int) -> dict:
    """获取单个任务"""
    try:
        response = requests.post(
            f"{BASE_URL}{API_PREFIX}/{task_id}/detail",
            json={},
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": TOKEN if TOKEN.startswith("Bearer ") else f"Bearer {TOKEN}",
            },
            timeout=60,
            verify=True,
        )
        print(f"  HTTP {response.status_code}")
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
        print(f"    错误: {str(e)[:50]}")
    return None


def main():
    print(f"准备获取 {len(TASK_IDS)} 个故障单 (使用 requests)...")
    print(f"Token: {TOKEN[:30]}...")
    print()

    tasks_data = []

    for i, task_id in enumerate(TASK_IDS, 1):
        print(f"[{i}/{len(TASK_IDS)}] 获取 {task_id}...", end=" ", flush=True)
        result = fetch_task(task_id)
        if result:
            tasks_data.append(result)
            print(f"✓ {result['title'][:35]}...")
        else:
            print("✗ 失败")
        time.sleep(0.3)

    print()
    print(f"成功获取: {len(tasks_data)} / {len(TASK_IDS)}")

    # 加载已有数据（11745664 和 11748712）
    output_file = Path("output/phase2_live/all_tasks.json")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # 从缓存读取已有数据
    existing_ids = [11745664, 11748712]
    existing_data = []

    print()
    print("加载已缓存的任务...")
    for tid in existing_ids:
        result = fetch_task(tid)
        if result:
            existing_data.append(result)
            print(f"  ✓ {tid}: {result['title'][:35]}...")

    all_data = existing_data + tasks_data

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    print()
    print(f"总共: {len(all_data)} 个任务")
    print(f"数据已保存: {output_file}")

    return all_data


if __name__ == "__main__":
    tasks = main()
