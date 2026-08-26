"""调试 ViolationDetector"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import re

from src.analysis.violation_detector import VIOLATION_PATTERNS, ViolationDetector
from src.api.client import APIClient
from src.config.manager import ConfigManager
from src.knowledge.manager import StandardsManager


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
    diff_content = commits[0].diff if commits else ""
    print(f"Diff 长度: {len(diff_content)} 字符")
    print(f"Diff 内容:\n{diff_content}")
    print()

    # 直接测试每个 pattern
    print("=== 直接测试每个违规模式 ===")
    for name, info in VIOLATION_PATTERNS.items():
        pattern = info["pattern"]
        if re.search(pattern, diff_content, re.IGNORECASE | re.MULTILINE):
            print(f"  ✅ 匹配: {name} -> {info['description']}")
        else:
            pass  # 不显示未匹配的

    # 使用 ViolationDetector
    print("\n=== ViolationDetector 检测 ===")
    standards_manager = StandardsManager()
    detector = ViolationDetector(standards_manager)

    fault_info = {
        "task_id": 11751534,
        "title": "[P3] 催缴邮件重复发送",
        "description": "流程实例判断26号为节假日",
        "code_snippet": diff_content,
    }

    detection = detector.detect(fault_info)
    print(f"  is_violation: {detection.is_violation}")
    print(f"  violated_rules: {detection.violated_rules}")
    print(f"  violation_type: {detection.violation_type}")
    print(f"  confidence: {detection.confidence}")

    await api.close()


asyncio.run(main())
