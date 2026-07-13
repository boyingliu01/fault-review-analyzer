#!/usr/bin/env bash
# 测试运行脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "=========================================="
echo "故障复盘分析工具 - 测试运行器"
echo "=========================================="

# 默认参数
COVERAGE=false
VERBOSE=false
TYPE_CHECK=false
LINT=false
ALL=false
TEST_PATH="tests/"

# 显示帮助
show_help() {
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -a, --all          运行所有检查 (lint, type-check, test, coverage)"
    echo "  -c, --coverage     运行测试并生成覆盖率报告"
    echo "  -v, --verbose      详细输出"
    echo "  -t, --type-check   运行类型检查 (mypy)"
    echo "  -l, --lint         运行代码检查 (ruff)"
    echo "  -f, --file <path>  运行指定文件/目录的测试"
    echo "  -h, --help         显示帮助信息"
    echo ""
    echo "示例:"
    echo "  $0                    # 运行所有测试"
    echo "  $0 -c                 # 运行测试并生成覆盖率报告"
    echo "  $0 -a                 # 运行所有检查"
    echo "  $0 -f tests/api/      # 只运行 API 相关测试"
}

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -a|--all)
            ALL=true
            shift
            ;;
        -c|--coverage)
            COVERAGE=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -t|--type-check)
            TYPE_CHECK=true
            shift
            ;;
        -l|--lint)
            LINT=true
            shift
            ;;
        -f|--file)
            TEST_PATH="$2"
            shift 2
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
    LINT=true
    TYPE_CHECK=true
    COVERAGE=true
fi

# 运行代码检查
if [ "$LINT" = true ]; then
    echo ""
    echo "----------------------------------------"
    echo "运行代码检查 (ruff)..."
    echo "----------------------------------------"
    ruff check src/ tests/
    ruff format --check src/ tests/
    echo "代码检查通过 ✓"
fi

# 运行类型检查
if [ "$TYPE_CHECK" = true ]; then
    echo ""
    echo "----------------------------------------"
    echo "运行类型检查 (mypy)..."
    echo "----------------------------------------"
    mypy src/
    echo "类型检查通过 ✓"
fi

# 构建 pytest 命令
echo ""
echo "----------------------------------------"
echo "运行测试..."
echo "----------------------------------------"

PYTEST_ARGS=()

if [ "$VERBOSE" = true ]; then
    PYTEST_ARGS+=("-v")
fi

if [ "$COVERAGE" = true ]; then
    PYTEST_ARGS+=("--cov=src")
    PYTEST_ARGS+=("--cov-report=term")
    PYTEST_ARGS+=("--cov-report=html")
    PYTEST_ARGS+=("--cov-report=xml")
fi

PYTEST_ARGS+=("$TEST_PATH")

# 运行测试
echo "执行: pytest ${PYTEST_ARGS[*]}"
echo ""

pytest "${PYTEST_ARGS[@]}"

echo ""
echo "----------------------------------------"
echo "测试完成 ✓"
echo "----------------------------------------"

if [ "$COVERAGE" = true ]; then
    echo ""
    echo "覆盖率报告已生成:"
    echo "  - 终端输出 (见上方)"
    echo "  - HTML 报告: htmlcov/index.html"
    echo "  - XML 报告: coverage.xml"
fi
