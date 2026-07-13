#!/usr/bin/env python
"""数据验证测试：检查API实际返回的字段内容"""

import asyncio
import json
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(override=True)

TOKEN = os.getenv("DEVCLOUD_TOKEN", "")
BASE_URL = "https://dev.iwhalecloud.com"
API_PREFIX = "/portal/ai-gateway/devspace/rpc/v3/work-item"

# 测试样本 - 包含之前分析过的任务ID
TEST_TASK_IDS = [11743724, 11745664, 11751363, 11748726]


async def fetch_task_detail(task_id: int) -> dict | None:
    """获取任务详情"""
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
                return data.get("data", {})
    except Exception as e:
        print(f"  错误: {e}")
    return None


def analyze_field_content(data: dict, path: str = "") -> dict:
    """递归分析字段内容"""
    result = {}

    if isinstance(data, dict):
        for key, value in data.items():
            current_path = f"{path}.{key}" if path else key

            if isinstance(value, (dict, list)):
                result[current_path] = analyze_field_content(value, current_path)
            else:
                # 分析字段内容
                content_info = {
                    "type": type(value).__name__,
                    "is_empty": value is None or value == "" or value == [],
                    "length": len(str(value)) if value is not None else 0,
                    "sample": str(value)[:100] if value is not None else None,
                }
                result[current_path] = content_info
    elif isinstance(data, list):
        result[path] = {
            "type": "list",
            "length": len(data),
            "is_empty": len(data) == 0,
            "sample": data[:2] if data else None,
        }

    return result


async def main():
    """主流程：验证API字段"""
    print("=" * 80)
    print("API数据字段验证测试")
    print("=" * 80)

    all_results = {}

    for task_id in TEST_TASK_IDS:
        print(f"\n\n{'=' * 80}")
        print(f"任务ID: {task_id}")
        print(f"{'=' * 80}")

        data = await fetch_task_detail(task_id)
        if not data:
            print("  ❌ 获取失败")
            continue

        # 检查apiTask字段
        api_task = data.get("apiTask", {}) if isinstance(data, dict) else {}

        print(f"\napiTask字段数量: {len(api_task)}")
        print(f"apiTask keys: {list(api_task.keys())[:20]}")

        # 检查关键字段
        key_fields = [
            "taskId",
            "taskNo",
            "taskTitle",
            "comments",
            "requirement",
            "design",
            "development",
            "testing",
            "production",
        ]

        print(f"\n关键字段内容检查:")
        print("-" * 80)

        field_analysis = {}
        for field in key_fields:
            value = api_task.get(field)

            if field in ["requirement", "design", "development", "testing", "production"]:
                # 这些字段可能是对象，检查content
                if isinstance(value, dict):
                    content = value.get("content", "")
                    has_content = content and len(str(content).strip()) > 10
                    field_analysis[field] = {
                        "exists": True,
                        "is_object": True,
                        "has_content": has_content,
                        "content_length": len(str(content)) if content else 0,
                        "content_sample": str(content)[:150] if content else None,
                    }
                    status = "✅" if has_content else "❌"
                    print(
                        f"  {status} {field}: {'有内容' if has_content else '空/无内容'} (长度: {len(str(content)) if content else 0})"
                    )
                else:
                    field_analysis[field] = {"exists": False, "type": type(value).__name__}
                    print(f"  ❌ {field}: 不存在或格式错误 (类型: {type(value).__name__})")
            else:
                # 简单字段
                exists = value is not None and str(value).strip() != ""
                field_analysis[field] = {
                    "exists": exists,
                    "value": str(value)[:100] if value else None,
                }
                status = "✅" if exists else "⚠️"
                print(f"  {status} {field}: {str(value)[:80] if value else '空'}")

        all_results[task_id] = {
            "api_task_keys": list(api_task.keys()),
            "field_analysis": field_analysis,
        }

    # 保存验证结果
    output_dir = Path("output/data_validation")
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_dir / "api_field_validation.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print(f"\n\n{'=' * 80}")
    print("验证完成!")
    print(f"{'=' * 80}")
    print(f"\n结果已保存: {output_dir / 'api_field_validation.json'}")

    # 生成汇总报告
    print("\n\n数据质量汇总:")
    print("-" * 80)

    total_tasks = len([r for r in all_results.values() if r])
    fields_with_content = {
        field: 0 for field in ["requirement", "design", "development", "testing", "production"]
    }

    for task_id, result in all_results.items():
        if "field_analysis" in result:
            for field in fields_with_content:
                analysis = result["field_analysis"].get(field, {})
                if analysis.get("has_content"):
                    fields_with_content[field] += 1

    print(f"\n分析的任务数: {total_tasks}")
    print(f"\n各阶段内容可用性:")
    for field, count in fields_with_content.items():
        pct = (count / total_tasks * 100) if total_tasks > 0 else 0
        status = "✅" if pct > 50 else "⚠️" if pct > 0 else "❌"
        print(f"  {status} {field}: {count}/{total_tasks} ({pct:.1f}%)")

    # 判断结论
    has_enough_data = any(count >= total_tasks * 0.5 for count in fields_with_content.values())

    print(f"\n{'=' * 80}")
    if not has_enough_data:
        print(
            "❌ 结论: API返回的阶段性分析字段(requirement/design/development/testing/production)基本为空"
        )
        print("   必须改用 taskTitle + comments 字段进行根因分析")
    else:
        print("✅ 结论: 部分阶段性分析字段有内容可用")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    asyncio.run(main())
