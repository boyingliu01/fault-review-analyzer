# ruff: noqa: E402
import asyncio
import sys

import pytest

sys.path.insert(0, "e:/Study/LLM/Bug聚类分析")

from src.api.client import APIClient


@pytest.mark.skip(reason="Manual e2e test script, requires real API credentials")
async def test_api():
    client = APIClient(
        base_url="https://dev.iwhalecloud.com",
        api_key="Bearer REDACTED_API_KEY",
        api_path_prefix="/portal/ai-gateway/devspace/rpc/v3/work-item",
    )
    client.ensure_client()

    try:
        print("Fetching task 11733177...")
        task = await client.get_task(11733177)
        print("Success!")
        print(f"  Task ID: {task.task_id}")
        print(f"  Title: {task.title}")
        print(f"  Status: {task.status}")
        print(f"  Priority: {task.priority}")
        print(f"  Description: {task.description[:200]}...")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
    finally:
        if client._client:
            await client._client.aclose()


if __name__ == "__main__":
    asyncio.run(test_api())
