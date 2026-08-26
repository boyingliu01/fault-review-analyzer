"""调试脚本：检查 API 返回的代码变更数据"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.api.client import APIClient
from src.config.manager import ConfigManager


async def main() -> None:
    cm = ConfigManager()
    cm.load()
    cfg = cm.get_config()

    api = APIClient(
        base_url=cfg.api.base_url,
        api_key=cfg.api.api_key,
        timeout=cfg.api.timeout,
        retry=cfg.api.retry,
    )
    api.ensure_client()

    task_id = 11751534

    # 1. 检查 get_commits 返回
    print("=== get_commits() ===")
    commits = await api.get_commits(task_id)
    print(f"返回 {len(commits)} 条 commit")

    for c in commits:
        print(f"\n  commit_id: {c.commit_id}")
        print(f"  message:   {c.message}")
        print(f"  branch:    {c.branch}")
        print(f"  changes:   {c.changes}")
        print(f"  diff 长度: {len(c.diff)} 字符")
        print(f"  diff 前200字符: {c.diff[:200]!r}")
        print(f"  code_changes 数量: {len(c.code_changes)}")
        for cc in c.code_changes:
            print(f"    - {cc.file_path} ({cc.change_type})")
            print(f"      old_content: {len(cc.old_content)} 字符")
            print(f"      new_content: {len(cc.new_content)} 字符")

    # 2. 检查 get_full_task 返回
    print("\n=== get_full_task() ===")
    task = await api.get_full_task(task_id)
    dev = task.development
    print(f"commits: {len(dev.commits) if dev else 0}")
    print(f"code_changes: {len(dev.code_changes) if dev else 0}")
    if dev and dev.commits:
        c = dev.commits[0]
        print(f"  commit.diff 长度: {len(c.diff)}")
        print(f"  commit.changes: {c.changes}")
        print(f"  commit.code_changes: {len(c.code_changes)}")

    await api.close()


asyncio.run(main())
