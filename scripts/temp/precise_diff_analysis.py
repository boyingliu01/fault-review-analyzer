"""精确分析代码变更 - 只看 diff 本身，不受描述影响"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.analyzer.llm_provider import create_llm_provider
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

    commits = await api.get_commits(11751534)
    c = commits[0]
    diff = c.diff
    old_content = c.code_changes[0].old_content if c.code_changes else ""
    new_content = c.code_changes[0].new_content if c.code_changes else ""

    print("=" * 60)
    print("  精确代码变更分析 - 仅基于 diff 和新旧文件内容")
    print("=" * 60)

    # 1. 只看 diff 本身
    print("\n### 1. Diff 原文 ###")
    print(diff)

    # 2. 提取变更行（+ 和 -）
    print("\n### 2. 变更行提取 ###")
    removed_lines = []
    added_lines = []
    for line in diff.split("\n"):
        if line.startswith("-") and not line.startswith("---"):
            removed_lines.append(line[1:])
        elif line.startswith("+") and not line.startswith("+++"):
            added_lines.append(line[1:])

    print(f"\n删除了 {len(removed_lines)} 行:")
    for l in removed_lines:
        print(f"  - {l.strip()}")

    print(f"\n新增了 {len(added_lines)} 行:")
    for l in added_lines:
        print(f"  + {l.strip()}")

    # 3. LLM 精确分析（仅基于代码，不含描述）
    print("\n### 3. LLM 精确分析（仅基于代码变更）###")
    provider = create_llm_provider(cfg.llm)
    if provider:
        system_prompt = (
            "你是一个资深 Java 代码审查专家。请**仅基于代码变更本身**进行分析，"
            "不要参考任何故障描述或工单信息。\n"
            "你需要准确理解：\n"
            "1. 代码**实际**做了什么改动（逐行分析）\n"
            "2. 改动前后的行为差异\n"
            "3. 这个改动的**真实目的**\n\n"
            "注意：区分'删除代码'和'将代码移入条件分支'是完全不同的操作。"
        )

        user_prompt = (
            "请分析以下 Java 代码变更。\n\n"
            f"**文件**: {c.changes[0] if c.changes else 'unknown'}\n\n"
            f"**Diff**:\n```\n{diff}\n```\n\n"
            "请回答：\n"
            "1. 这段代码变更**实际**做了什么？（逐行分析，区分删除/新增/移动）\n"
            "2. 修改前 `suspendProcessTask` 方法的行为是什么？\n"
            "3. 修改后 `suspendProcessTask` 方法的行为是什么？\n"
            "4. 这个改动的核心目的是什么？\n"
            "5. 这个改动能修复什么问题？\n"
            "6. 还有哪些问题这个改动**没有**解决？\n\n"
            "请用中文回答，简洁准确。"
        )

        result = await provider.generate(system=system_prompt, user=user_prompt)
        print(result)

    await api.close()


asyncio.run(main())
