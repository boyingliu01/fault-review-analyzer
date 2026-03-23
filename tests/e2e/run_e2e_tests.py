#!/usr/bin/env python
"""
E2E 测试运行脚本

用法:
    python tests/e2e/run_e2e_tests.py              # 运行所有 E2E 测试
    python tests/e2e/run_e2e_tests.py --cli         # 只运行 CLI 测试
    python tests/e2e/run_e2e_tests.py --pipeline   # 只运行 Pipeline 测试
    python tests/e2e/run_e2e_tests.py --ui          # 只运行 UI 测试
    python tests/e2e/run_e2e_tests.py --headed      # UI 测试以 headed 模式运行
"""

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent


def run_tests(args):
    """运行 E2E 测试"""
    cmd = [sys.executable, "-m", "pytest", "tests/e2e/", "-v"]

    # 根据参数添加标记过滤器
    if args.cli:
        cmd.extend(["-m", "e2e", "--ignore=tests/e2e/ui/", "--ignore=tests/e2e/pipeline/"])
    elif args.pipeline:
        cmd.extend(["-m", "e2e", "--ignore=tests/e2e/cli/", "--ignore=tests/e2e/ui/"])
    elif args.ui:
        cmd.append("tests/e2e/ui/")
    else:
        # 运行所有 E2E 测试（跳过需要真实浏览器的 UI 测试，除非指定）
        if not args.ui:
            cmd.extend(["--ignore=tests/e2e/ui/"])

    # headed 模式
    if args.headed:
        cmd.append("--headed")

    # 报告
    if args.html:
        cmd.extend(["--html=playwright-report.html", "--self-contained-html"])

    # 并行
    if args.parallel:
        cmd.extend(["-n", "auto"])

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description="运行 E2E 测试")
    parser.add_argument("--cli", action="store_true", help="只运行 CLI 测试")
    parser.add_argument("--pipeline", action="store_true", help="只运行 Pipeline 测试")
    parser.add_argument("--ui", action="store_true", help="只运行 UI 测试")
    parser.add_argument("--headed", action="store_true", help="UI 测试以 headed 模式运行")
    parser.add_argument("--html", action="store_true", help="生成 HTML 报告")
    parser.add_argument("--parallel", action="store_true", help="并行运行测试")
    args = parser.parse_args()

    sys.exit(run_tests(args))


if __name__ == "__main__":
    main()
