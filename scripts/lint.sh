#!/usr/bin/env bash
# 代码检查脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "=========================================="
echo "故障复盘分析工具 - 代码检查"
echo "=========================================="

# 默认参数
FIX=false
FORMAT=false
TYPE_CHECK=false
ALL=false

# 显示帮助
show_help() {
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -a, --all          运行所有检查 (lint, format, type-check)"
    echo "  -f, --fix          自动修复可修复的问题"
    echo "  -t, --type-check   运行类型检查 (mypy)"
    echo "  -F, --format       运行代码格式化"
    echo "  -h, --help         显示帮助信息"
    echo ""
    echo "示例:"
    echo "  $0                    # 仅运行代码检查 (不修复)"
    echo "  $0 -f                 # 运行检查并自动修复"
    echo "  $0 -a                 # 运行所有检查"
    echo "  $0 -a -f              # 运行所有检查并自动修复"
}

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -a|--all)
            ALL=true
            shift
            ;;
        -f|--fix)
            FIX=true
            shift
            ;;
        -t|--type-check)
            TYPE_CHECK=true
            shift
            ;;
        -F|--format)
            FORMAT=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "未知选项: $1"
            show_help
            exit 1
            ;;
    esac
done

# 如果指定了 --all，则启用所有检查
if [ "$ALL" = true ]; then
    FORMAT=true
    TYPE_CHECK=true
fi

# 运行 ruff 检查
echo ""
echo "----------------------------------------"
echo "运行 Ruff 代码检查..."
echo "----------------------------------------"

if [ "$FIX" = true ]; then
    echo "模式: 检查并自动修复"
    ruff check src/ tests/ --fix
else
    echo "模式: 仅检查 (使用 --fix 自动修复)"
    ruff check src/ tests/
fi

echo "Ruff 检查完成 ✓"

# 运行代码格式化
if [ "$FORMAT" = true ]; then
    echo ""
    echo "----------------------------------------"
    echo "运行代码格式化..."
    echo "----------------------------------------"

    if [ "$FIX" = true ]; then
        ruff format src/ tests/
        echo "代码格式化完成 ✓"
    else
        ruff format --check src/ tests/
        echo "代码格式检查完成 ✓ (使用 --fix 自动格式化)"
    fi
fi

# 运行类型检查
if [ "$TYPE_CHECK" = true ]; then
    echo ""
    echo "----------------------------------------"
    echo "运行类型检查 (mypy)..."
    echo "----------------------------------------"
    mypy src/
    echo "类型检查完成 ✓"
fi

echo ""
echo "=========================================="
echo "代码检查完成！"
echo "=========================================="
