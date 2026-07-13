"""
正确的故障分析流程 - 基于实际可用字段 (title + comments)
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import numpy as np
from dotenv import load_dotenv

# 加载环境变量
load_dotenv(override=True)

TOKEN = os.getenv("DEVCLOUD_TOKEN", "")
BASE_URL = "https://dev.iwhalecloud.com"
API_PREFIX = "/portal/ai-gateway/devspace/rpc/v3/work-item"

# 要分析的故障单ID
TASK_IDS = [
    11743724,
    11745664,
    11751363,
    11748726,
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
]


def validate_task_data(task_data: dict) -> tuple[bool, str]:
    """数据质量校验 - 拒绝空数据

    Returns:
        (is_valid, error_message)
    """
    title = task_data.get("title", "").strip()
    description = task_data.get("description", "").strip()

    # 清理markdown图片后的内容检查
    import re

    cleaned_desc = re.sub(r"!\[.*?\]\(.*?\)", "", description)
    cleaned_desc = re.sub(r"\[.*?\]:\s*https?://\S+", "", cleaned_desc)
    cleaned_desc = cleaned_desc.strip()

    if not title and not cleaned_desc:
        return False, "标题和描述均为空"

    if len(title) < 5 and len(cleaned_desc) < 20:
        return False, f"内容过少 (标题:{len(title)}字, 描述:{len(cleaned_desc)}字)"

    # 检查是否只有图片没有文字
    text_content = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9]", "", cleaned_desc)
    if len(title) < 5 and len(text_content) < 10:
        return False, "有效文本内容过少(可能只有图片)"

    return True, ""


def prepare_analysis_text(task_data: dict) -> str:
    """准备用于分析的真实文本"""
    title = task_data.get("title", "").strip()
    description = task_data.get("description", "").strip()

    # 清理markdown图片
    import re

    cleaned_desc = re.sub(r"!\[.*?\]\(.*?\)", "", description)
    cleaned_desc = re.sub(r"\[.*?\]:\s*https?://\S+", "", cleaned_desc)
    cleaned_desc = cleaned_desc.strip()

    parts = []
    if title:
        parts.append(f"故障标题: {title}")
    if cleaned_desc:
        # 限制长度避免token过多
        if len(cleaned_desc) > 1000:
            cleaned_desc = cleaned_desc[:1000] + "..."
        parts.append(f"故障描述: {cleaned_desc}")

    return "\n\n".join(parts)


async def fetch_task(task_id: int) -> dict | None:
    """获取故障单数据"""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{BASE_URL}{API_PREFIX}/{task_id}/detail",
                json={},
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Authorization": TOKEN if TOKEN.startswith("Bearer ") else f"Bearer {TOKEN}",
                },
            )

            if response.status_code == 200:
                data = response.json()
                task_data = data.get("data", {})
                api_task = task_data.get("apiTask", {}) if isinstance(task_data, dict) else {}

                if api_task:
                    return {
                        "task_id": task_id,
                        "task_no": api_task.get("taskNo", str(task_id)),
                        "title": api_task.get("taskTitle", ""),
                        "description": api_task.get("comments", ""),
                        "status": "finished" if api_task.get("finishFlag") == 1 else "open",
                        "task_src": api_task.get("taskSrc", ""),
                        "created_date": api_task.get("createdDate", ""),
                    }
    except Exception as e:
        print(f"    获取失败: {e}")
    return None


async def main():
    """验证真实数据并生成分析"""
    print("=" * 80)
    print("真实数据验证与修复")
    print("=" * 80)
    print()

    results = []

    for task_id in TASK_IDS:
        print(f"处理 {task_id}...", end=" ", flush=True)

        task_data = await fetch_task(task_id)
        if not task_data:
            print("❌ 获取失败")
            continue

        # 数据质量校验
        is_valid, error_msg = validate_task_data(task_data)
        if not is_valid:
            print(f"❌ 数据质量不合格: {error_msg}")
            results.append(
                {
                    "task_id": task_id,
                    "status": "rejected",
                    "reason": error_msg,
                    "title": task_data.get("title", "")[:50],
                    "description_sample": task_data.get("description", "")[:50],
                }
            )
            continue

        # 准备分析文本
        analysis_text = prepare_analysis_text(task_data)

        print(f"✅ 有效 (文本长度: {len(analysis_text)})")
        results.append(
            {
                "task_id": task_id,
                "status": "valid",
                "title": task_data.get("title", ""),
                "description": task_data.get("description", ""),
                "analysis_text": analysis_text,
            }
        )

    # 保存结果
    output_dir = Path("output/data_validation")
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_dir / "validated_tasks.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 统计
    valid_count = sum(1 for r in results if r["status"] == "valid")
    rejected_count = sum(1 for r in results if r["status"] == "rejected")

    print()
    print("=" * 80)
    print("验证结果汇总")
    print("=" * 80)
    print(f"总任务数: {len(TASK_IDS)}")
    print(f"✅ 有效数据: {valid_count}")
    print(f"❌ 被拒绝: {rejected_count}")
    print(f"通过率: {valid_count / len(TASK_IDS) * 100:.1f}%")
    print()
    print(f"结果已保存: {output_dir / 'validated_tasks.json'}")

    # 显示被拒绝的任务
    if rejected_count > 0:
        print()
        print("被拒绝的任务详情:")
        for r in results:
            if r["status"] == "rejected":
                print(f"  - {r['task_id']}: {r['reason']}")
                print(f"    标题: {r['title']}")
                print(f"    描述片段: {r['description_sample']}")


if __name__ == "__main__":
    asyncio.run(main())
