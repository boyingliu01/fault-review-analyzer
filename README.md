# Fault Review Analyzer

AI驱动的故障复盘分析工具 - 不依赖预设故障根本原因，基于故障处理过程详细信息独立完成故障复盘分析。

## 功能特性

- **无预设标签**: 不预先定义故障原因分类，从数据中自动习得
- **自动聚类**: 使用HDBSCAN算法自动发现相似故障模式
- **知识自习得**: 通过LLM自动提取技术标签，形成动态知识库
- **规范冲突识别**: 自动识别违反研发规范的缺陷模式

## 安装

```bash
# 克隆项目
git clone <repo-url>
cd fault-review-analyzer

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 安装依赖
pip install -e ".[dev]"

# 安装 pre-commit 钩子
pre-commit install
```

## 快速开始

```bash
# 查看帮助
fault-analyzer --help

# 获取故障数据
fault-analyzer fetch --task-id 12345

# 分析故障
fault-analyzer analyze --task-id 12345

# 生成报告
fault-analyzer report --task-id 12345 --output ./reports/
```

## 配置

复制 `.env.example` 为 `.env` 并填写配置：

```bash
cp .env.example .env
```

主要配置项：
- `API_BASE_URL`: 研发管理系统API地址
- `LLM_PROVIDER`: LLM服务提供商 (openai/qwen/etc)
- `LLM_API_KEY`: LLM API密钥
- `EMBEDDING_PROVIDER`: Embedding服务提供商

## 开发

```bash
# 运行测试
pytest tests/ -v --cov=src

# 代码检查
ruff check src/ tests/

# 代码格式化
ruff format src/ tests/

# 类型检查
mypy src/
```

## 项目结构

```
fault-review-analyzer/
├── src/
│   ├── cli/              # 命令行接口
│   ├── api/              # API客户端
│   ├── cache/            # 缓存管理
│   ├── analyzer/         # 分析引擎
│   ├── report/           # 报告生成
│   ├── rules/            # 规范引擎
│   ├── config/           # 配置管理
│   └── utils/            # 工具函数
├── data/
│   ├── cache/            # 缓存数据
│   └── rules/            # 规范文档
├── output/               # 输出报告
├── tests/                # 测试
└── docs/                 # 文档
```

## License

MIT
