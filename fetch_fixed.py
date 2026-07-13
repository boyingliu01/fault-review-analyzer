#!/usr/bin/env python
"""修复版：获取故障单数据（正确解析apiTask）"""

import requests
import os
from dotenv import load_dotenv
from pathlib import Path
import json
import time

load_dotenv(override=True)

TOKEN = os.getenv("DEVCLOUD_TOKEN")
BASE_URL = "https://dev.iwhalecloud.com"
API_PREFIX = "/portal/ai-gateway/devspace/rpc/v3/work-item"

# 要获取的任务
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
        )
        if response.status_code == 200:
            data = response.json()
            # 数据在 apiTask 字段里
            api_task = data.get("data", {}).get("apiTask", {})
            if api_task:
                return {
                    "task_id": task_id,
                    "task_no": api_task.get("taskNo", str(task_id)),
                    "title": api_task.get("title", ""),
                    "description": api_task.get("description", ""),
                    "status": api_task.get("status", ""),
                    "task_src": api_task.get("taskSrc", ""),
                    "created_date": api_task.get("createdDate", ""),
                    "finish_date": api_task.get("finishDate", ""),
                }
    except Exception as e:
        print(f"    错误: {str(e)[:50]}")
    return None


def main():
    print(f"准备获取 {len(TASK_IDS)} 个故障单...")
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

    # 保存数据
    output_file = Path("output/phase2_live/tasks_data.json")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(tasks_data, f, ensure_ascii=False, indent=2)

    print(f"数据已保存: {output_file}")

    return tasks_data


if __name__ == "__main__":
    tasks = main()
