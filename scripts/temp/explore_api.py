"""验证完整链路：get_full_task + code_change_analyzer"""
import os

with open(".env") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            os.environ[key.strip()] = val.strip()

import asyncio

from src.analysis.code_change_analyzer import CodeChangeAnalyzer
from src.api.client import APIClient
from src.config.manager import ConfigManager


async def main():
    config = ConfigManager()
    cfg = config.get_config()
    client = APIClient(
        base_url=cfg.api.base_url,
        api_key=cfg.api.api_key,
        timeout=cfg.api.timeout,
        retry=cfg.api.retry,
    )

    analyzer = CodeChangeAnalyzer()

    async with client:
        # 测试有代码分支的任务
        for task_id in [11751534, 11751363, 11750733]:
            print(f"\n{'='*60}")
            print(f"Task {task_id}")
            print('='*60)
            task = await client.get_full_task(task_id)
            print(f"标题: {task.title}")

            if task.development and task.development.commits:
                commits = task.development.commits
                print(f"Commits: {len(commits)}")
                print(f"CodeChanges: {len(task.development.code_changes)}")

                # 生成分析文本
                commits_data = []
                for c in commits:
                    commits_data.append({
                        "commit_id": c.commit_id,
                        "author": c.author,
                        "message": c.message,
                        "diff": c.diff,
                        "files_changed": c.changes,
                        "branch": c.branch,
                        "repository": c.repository,
                    })

                analysis_text = analyzer.generate_analysis_text(commits_data)
                print(f"\n分析文本长度: {len(analysis_text)}")
                print(f"分析文本前500字:\n{analysis_text[:500]}")

                # 分析 diff
                for c in commits:
                    if c.diff:
                        result = analyzer.analyze_diff(c.diff)
                        print("\nDiff分析结果:")
                        print(f"  added_lines: {result.get('added_lines', 0)}")
                        print(f"  removed_lines: {result.get('removed_lines', 0)}")
                        print(f"  files_added: {result.get('files_added', 0)}")
                        print(f"  files_modified: {result.get('files_modified', 0)}")
                        print(f"  files_removed: {result.get('files_removed', 0)}")
            else:
                print("无代码变更数据")


asyncio.run(main())
