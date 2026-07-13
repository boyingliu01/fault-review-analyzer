#!/usr/bin/env python3
"""严格代码检查脚本 - 运行所有静态检查工具"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], description: str) -> tuple[int, str, str]:
    """运行命令并返回结果"""
    print(f"\n{'='*60}")
    print(f"🔍 {description}")
    print(f"{'='*60}")
    print(f"命令: {' '.join(cmd)}")
    print()

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace'
    )

    if result.stdout:
        print("STDOUT:")
        print(result.stdout)

    if result.stderr:
        print("STDERR:")
        print(result.stderr)

    print(f"\n返回码: {result.returncode}")
    return result.returncode, result.stdout, result.stderr


def main():
    """主函数"""
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))

    print("🚀 启动严格代码检查")
    print(f"项目目录: {project_root}")

    results = []

    # 1. Ruff 格式检查
    results.append(run_command(
        ["python", "-m", "ruff", "format", "--check", "src/", "tests/"],
        "Ruff 格式检查"
    )[0])

    # 2. Ruff 代码检查
    results.append(run_command(
        ["python", "-m", "ruff", "check", "src/", "tests/"],
        "Ruff 代码检查"
    )[0])

    # 3. Ruff 严格检查 (更多规则)
    results.append(run_command(
        ["python", "-m", "ruff", "check", "--select", "ALL",
         "--ignore", "D,E501,W503,ANN101,ANN102,ANN401,FBT001,FBT002,TRY003,EM101,EM102,RET504,RET505,PLR0911,PLR0912,PLR0913,PLR0915,C901,PGH003,S101,S311,S105,S106,S108,S110,S607,S602,S603,S310",
         "src/", "tests/"],
        "Ruff 严格检查 (全部规则)"
    )[0])

    # 4. MyPy 类型检查
    results.append(run_command(
        ["python", "-m", "mypy", "src/", "--ignore-missing-imports"],
        "MyPy 类型检查"
    )[0])

    # 5. 运行测试
    results.append(run_command(
        ["python", "-m", "pytest", "tests/",
         "--ignore=tests/e2e",
         "--ignore=tests/rules/test_engine.py",
         "--ignore=tests/cache/test_manager_task22.py",
         "-q", "--tb=short"],
        "运行测试套件"
    )[0])

    # 汇总结果
    print(f"\n{'='*60}")
    print("📊 检查结果汇总")
    print(f"{'='*60}")

    passed = sum(1 for r in results if r == 0)
    failed = sum(1 for r in results if r != 0)

    print(f"✅ 通过: {passed}")
    print(f"❌ 失败: {failed}")

    if all(r == 0 for r in results):
        print("\n🎉 所有检查通过！代码质量优秀！")
        return 0
    else:
        print("\n⚠️ 部分检查未通过，请查看详细输出。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
