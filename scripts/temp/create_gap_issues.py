#!/usr/bin/env python3
"""批量创建 Gap Issues 到 GitHub。

使用前提: gh CLI 已登录且网络可访问 GitHub。

用法:
    python scripts/temp/create_gap_issues.py
"""

import json
import subprocess
from pathlib import Path


def main() -> None:
    issues_file = Path(__file__).parent / "gap_issues.json"
    issues = json.loads(issues_file.read_text(encoding="utf-8"))

    print(f"准备创建 {len(issues)} 个 issues...")
    print()

    created = 0
    for i, issue in enumerate(issues, 1):
        title = issue["title"]
        labels = ",".join(issue["labels"])
        body = issue["body"]

        # 写入临时 body 文件 (避免 PowerShell 转义问题)
        body_file = Path(__file__).parent / f"_issue_body_{i}.md"
        body_file.write_text(body, encoding="utf-8")

        cmd = [
            "gh", "issue", "create",
            "--title", title,
            "--label", labels,
            "--body-file", str(body_file),
        ]

        print(f"[{i}/{len(issues)}] 创建: {title}")
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=True, timeout=30
            )
            print(f"  ✅ {result.stdout.strip()}")
            created += 1
        except subprocess.CalledProcessError as e:
            print(f"  ❌ 失败: {e.stderr.strip()}")
        except subprocess.TimeoutExpired:
            print("  ⏰ 超时")
        finally:
            body_file.unlink(missing_ok=True)

        print()

    print(f"完成: 成功创建 {created}/{len(issues)} 个 issues")


if __name__ == "__main__":
    main()
