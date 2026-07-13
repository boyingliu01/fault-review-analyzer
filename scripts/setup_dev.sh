#!/usr/bin/env bash
# 开发环境初始化脚本

set -e

echo "=========================================="
echo "故障复盘分析工具 - 开发环境初始化"
echo "=========================================="

# 检查 Python 版本
echo ""
echo "[1/5] 检查 Python 版本..."
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 Python3，请先安装 Python 3.10 或更高版本"
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print('.'.join(map(str, sys.version_info[:2])))")
echo "当前 Python 版本: $PYTHON_VERSION"

# 检查 Python 版本是否符合要求 (3.10+)
if ! python3 -c "import sys; assert sys.version_info >= (3, 10), 'Python 3.10+ required'"; then
    echo "错误: 需要 Python 3.10 或更高版本"
    exit 1
fi

# 创建虚拟环境
echo ""
echo "[2/5] 创建虚拟环境..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "虚拟环境已创建: .venv/"
else
    echo "虚拟环境已存在，跳过创建"
fi

# 激活虚拟环境
echo ""
echo "[3/5] 激活虚拟环境并安装依赖..."
source .venv/bin/activate

# 升级 pip
pip install --upgrade pip

# 安装开发依赖
pip install -e ".[dev]"

# 安装 pre-commit 钩子
echo ""
echo "[4/5] 安装 pre-commit 钩子..."
pre-commit install

# 复制环境配置文件
echo ""
echo "[5/5] 设置环境配置..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "已创建 .env 文件，请填写相关配置项"
else
    echo ".env 文件已存在，跳过创建"
fi

# 创建必要的目录
mkdir -p data/chroma
mkdir -p data/rules/custom
mkdir -p data/standards
mkdir -p output

echo ""
echo "=========================================="
echo "开发环境初始化完成！"
echo "=========================================="
echo ""
echo "下一步："
echo "1. 编辑 .env 文件，填写 API 密钥等配置"
echo "2. 运行 'source .venv/bin/activate' 激活虚拟环境"
echo "3. 运行 'pytest tests/ -v' 验证安装"
echo ""
