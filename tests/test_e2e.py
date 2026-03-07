import asyncio
import sys
sys.path.insert(0, "e:/Study/LLM/Bug聚类分析")

import pandas as pd
from src.api.client import APIClient
from src.preprocessor.processor import DataPreprocessor

async def test_real_data():
    client = APIClient(
        base_url='https://dev.iwhalecloud.com',
        api_key='Bearer REDACTED_API_KEY',
        api_path_prefix='/portal/ai-gateway/devspace/rpc/v3/work-item',
    )
    client.ensure_client()

    df = pd.read_excel('e:/Study/LLM/Bug聚类分析/SQL缺陷分析结果.xlsx')
    task_ids = df['泄露缺陷单号'].head(5).tolist()

    print("="*60)
    print("端到端测试 - 从API获取真实数据")
    print("="*60)

    tasks = []
    for task_id in task_ids:
        print(f"\n获取任务 {task_id}...")
        try:
            task = await client.get_task(int(task_id))
            tasks.append(task)
            print(f"  ✓ 成功: {task.title[:40]}...")
            print(f"    Status: {task.status}, Priority: {task.priority}")
        except Exception as e:
            print(f"  ✗ 失败: {type(e).__name__}: {e}")

    if client._client:
        await client._client.aclose()

    if tasks:
        print("\n" + "="*60)
        print("测试预处理器")
        print("="*60)
        preprocessor = DataPreprocessor()
        processed = preprocessor.process_batch(tasks)

        for i, p in enumerate(processed):
            print(f"\n任务 {tasks[i].task_id}:")
            print(f"  combined_text长度: {len(p.combined_text)}")
            print(f"  combined_text预览: {p.combined_text[:100]}...")

asyncio.run(test_real_data())
