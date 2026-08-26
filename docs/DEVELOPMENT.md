# 开发指南

本指南提供了故障复盘分析工具的开发环境设置、代码结构、开发流程等详细信息，帮助开发者快速上手。

## 目录

- [开发环境](#开发环境)
- [项目结构](#项目结构)
- [开发流程](#开发流程)
- [代码规范](#代码规范)
- [依赖管理](#依赖管理)
- [配置系统](#配置系统)
- [数据模型](#数据模型)
- [开发工具](#开发工具)
- [测试指南](#测试指南)
- [调试技巧](#调试技巧)
- [常见问题](#常见问题)

## 开发环境

### 系统要求

- **操作系统**: Linux、macOS 或 Windows
- **Python 版本**: 3.10 或更高
- **内存**: 至少 8GB（推荐 16GB 或更多）
- **磁盘空间**: 至少 20GB 可用空间

### 软件依赖

- **Git**: 版本控制工具
- **Docker**: 容器化工具（可选）
- **编辑器**: VS Code、PyCharm 等
- **Python 工具**: pip、venv 或 conda

## 项目结构

```
fault-review-analyzer/
├── src/                          # 源代码目录
│   ├── api/                      # API 服务相关
│   │   ├── server.py            # FastAPI 服务器主文件
│   │   ├── middleware.py       # 认证和速率限制中间件
│   │   ├── server_models.py    # API 数据模型
│   │   ├── dependencies.py     # 依赖注入
│   │   ├── client.py           # API 客户端（与研发管理系统通信）
│   │   ├── models.py           # API 客户端模型
│   │   ├── exceptions.py       # 异常定义
│   │   └── routes/             # 路由实现
│   │       ├── health.py       # 健康检查路由
│   │       ├── analyze.py      # 分析路由
│   │       ├── clusters.py     # 聚类路由
│   │       ├── reports.py      # 报告路由
│   │       └── feedback.py     # 反馈路由
│   ├── cli/                      # 命令行接口
│   │   ├── main.py            # CLI 入口点
│   │   └── commands/          # 各命令实现
│   │       ├── fetch.py       # 数据获取命令
│   │       ├── analyze.py     # 分析命令
│   │       ├── report.py      # 报告生成命令
│   │       ├── cache.py       # 缓存管理命令
│   │       └── config.py      # 配置管理命令
│   ├── analyzer/                # 分析引擎
│   │   ├── pipeline.py        # 分析管道
│   │   ├── llm_provider.py    # LLM 服务提供者抽象
│   │   ├── labeling/          # 标签生成
│   │   └── reasoning/         # 根因分析
│   ├── preprocessor/           # 数据预处理
│   │   ├── processor.py       # 数据预处理程序
│   │   └── models.py          # 预处理数据模型
│   ├── embedding/              # 嵌入生成
│   │   ├── generator.py       # 嵌入生成器
│   │   └── models.py          # 嵌入数据模型
│   ├── clustering/             # 聚类分析
│   │   ├── analyzer.py        # 聚类分析器
│   │   └── models.py          # 聚类数据模型
│   ├── rules/                  # 规范检查
│   │   ├── engine.py          # 规范检查引擎
│   │   ├── models.py          # 规范检查数据模型
│   │   ├── categories.py      # 规范类别定义
│   │   ├── builtin/           # 内置规范
│   │   └── custom/            # 自定义规范
│   ├── report/                 # 报告生成
│   │   ├── generator.py       # 报告生成器
│   │   ├── models.py          # 报告数据模型
│   │   └── templates/         # 报告模板（Jinja2）
│   ├── cache/                  # 缓存管理
│   │   ├── manager.py         # 缓存管理器
│   │   └── models.py          # 缓存数据模型
│   ├── embedding/               # Embedding 生成
│   │   ├── generator.py        # Embedding 生成器
│   │   └── models.py          # Embedding 数据模型
│   ├── feedback/               # 反馈管理
│   │   ├── manager.py         # 反馈管理器
│   │   ├── models.py          # 反馈数据模型
│   │   └── trigger.py         # 反馈触发机制
│   ├── config/                 # 配置管理
│   │   ├── manager.py         # 配置管理器
│   │   ├── models.py          # 配置数据模型
│   │   └── validator.py       # 配置验证器
│   ├── visualization/          # 可视化
│   │   ├── charts.py          # 图表生成
│   │   └── cluster_scatter.py # 聚类散点图
│   ├── utils/                  # 工具和辅助函数
│   │   ├── helpers.py         # 通用工具函数
│   │   ├── metrics.py         # 指标计算
│   │   ├── logger.py          # 日志管理
│   │   └── circuit_breaker.py # 熔断器模式
│   ├── i18n/                   # 国际化
│   │   └── translations.py    # 翻译文件
│   └── __init__.py            # 包初始化
├── config/                      # 配置文件
│   └── config.yaml             # 系统配置（可选）
├── data/                        # 数据目录
│   ├── cache/                  # SQLite 缓存
│   ├── rules/                 # 规则文件
│   ├── standards/             # 开发规范文档
│   └── cache.db               # SQLite 缓存数据库
├── output/                      # 输出目录（报告文件）
├── logs/                        # 日志目录
├── tests/                       # 测试目录
├── docs/                        # 文档目录
├── .venv/                       # 虚拟环境（可选）
├── .env                        # 环境变量
├── .env.example                # 环境变量示例
├── pyproject.toml             # 项目配置
├── requirements.txt           # 依赖列表（自动生成）
├── README.md                  # 项目说明
└── LICENSE                    # 许可证
```

## 开发流程

### 1. 获取代码

```bash
# 克隆仓库
git clone https://github.com/your-org/fault-review-analyzer.git
cd fault-review-analyzer
```

### 2. 创建虚拟环境

```bash
# 使用 venv
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate  # Windows

# 或使用 conda
conda create -n fault-review python=3.11
conda activate fault-review
```

### 3. 安装依赖

```bash
# 安装所有依赖（包括开发依赖）
pip install -e ".[dev]"

# 安装 pre-commit 钩子
pre-commit install
```

### 4. 配置环境

```bash
# 复制环境变量示例文件
cp .env.example .env

# 编辑 .env 文件，填入必要的配置
# 必填项：API_BASE_URL、DEVCLOUD_TOKEN、LLM_API_KEY、EMBEDDING_API_KEY
```

### 5. 创建必要的目录

```bash
mkdir -p data/cache
mkdir -p data/rules/custom
mkdir -p data/standards
mkdir -p output
mkdir -p logs
```

### 6. 运行测试

```bash
# 运行所有测试
pytest tests/ -v --cov=src

# 运行特定测试文件
pytest tests/test_clustering.py -v

# 运行特定测试
pytest tests/test_clustering.py::test_cluster_analysis -v
```

### 7. 开发

根据你的需求修改代码。建议使用以下开发流程：

1. 创建一个新的分支
2. 实现功能或修复 bug
3. 编写测试
4. 运行测试
5. 提交更改
6. 创建 Pull Request

### 8. 测试修改后的代码

```bash
# 使用 CLI 测试
fault-analyzer --help

# 运行 API 服务
python -m src.api.server

# 使用 HTTP 客户端测试 API（如 curl 或 Postman）
curl http://localhost:8000/health
```

## 代码规范

### 代码风格

我们使用 Ruff 进行代码风格检查和格式化，使用 mypy 进行类型检查。

```bash
# 代码检查
ruff check src/ tests/

# 代码格式化
ruff format src/ tests/

# 类型检查
mypy src/
```

### 文档字符串

使用 NumPy 风格的文档字符串：

```python
def analyze_task(task_id: str, use_cache: bool = True) -> AnalysisResult:
    """
    分析任务的故障信息

    Parameters
    ----------
    task_id : str
        任务编号
    use_cache : bool, optional
        是否使用缓存数据，默认为 True

    Returns
    -------
    AnalysisResult
        分析结果对象

    Raises
    ------
    TaskNotFoundError
        任务不存在
    AnalysisError
        分析过程中发生错误

    Examples
    --------
    >>> result = analyze_task("11745664")
    >>> print(result.summary)
    "任务分析完成"
    """
    pass
```

## 依赖管理

依赖管理使用 `pyproject.toml` 文件和 `pip` 工具。

### 添加依赖

```bash
# 安装新依赖
pip install <package-name>

# 将依赖添加到 pyproject.toml
pip install -e ".[dev]"  # 或直接编辑 pyproject.toml
```

### 更新依赖

```bash
# 更新所有依赖
pip install -U pip
pip install -e ".[dev]" --upgrade

# 更新单个依赖
pip install -U <package-name>
```

### 检查依赖安全性

```bash
# 使用 pip-audit 检查依赖安全性
pip install pip-audit
pip-audit
```

## 配置系统

系统支持通过以下方式配置：

1. 环境变量（.env 文件）
2. YAML 配置文件（config/config.yaml）
3. 命令行参数（CLI）

### 配置加载顺序

1. 命令行参数（优先级最高）
2. 环境变量
3. 配置文件
4. 默认值

### 使用配置

```python
from src.config.manager import ConfigManager

# 获取配置实例
config = ConfigManager()

# 访问配置项
api_base_url = config.api.base_url
devcloud_token = config.api.devcloud_token
llm_provider = config.llm.provider
```

### 自定义配置

在 `config/config.yaml` 文件中添加自定义配置：

```yaml
api:
  base_url: "https://dev.iwhalecloud.com"
  timeout: 60

llm:
  provider: "openai"
  model: "gpt-4"
  temperature: 0.7

clustering:
  min_cluster_size: 3
  metric: "cosine"
```

## 数据模型

系统使用 Pydantic 进行数据验证和解析。主要数据模型分为以下几类：

1. **API 数据模型**: `src/api/models.py`、`src/api/server_models.py`
2. **分析数据模型**: `src/analyzer/labeling/models.py`、`src/analyzer/reasoning/models.py`
3. **预处理数据模型**: `src/preprocessor/models.py`
4. **嵌入数据模型**: `src/embedding/models.py`
5. **聚类数据模型**: `src/clustering/models.py`
6. **规范检查数据模型**: `src/rules/models.py`
7. **报告数据模型**: `src/report/models.py`

### 创建新数据模型

```python
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class AnalysisResult(BaseModel):
    """分析结果数据模型"""

    task_id: str = Field(..., description="任务编号")
    title: str = Field(..., description="任务标题")
    summary: str = Field(..., description="分析摘要")
    root_causes: List[str] = Field(default_factory=list, description="根因列表")
    labels: List[str] = Field(default_factory=list, description="标签列表")
    violations: List[str] = Field(default_factory=list, description="规范冲突列表")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")

    class Config:
        """配置类"""
        extra = "forbid"  # 禁止字段扩展
        frozen = False    # 允许修改字段
        from_attributes = True  # 支持从属性创建模型实例
```

## 开发工具

### VS Code 配置

创建 `.vscode/settings.json` 文件：

```json
{
  "python.analysis.typeCheckingMode": "basic",
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": false,
  "python.linting.ruffEnabled": true,
  "python.formatting.provider": "none",
  "[python]": {
    "editor.formatOnSave": false,
    "editor.codeActionsOnSave": {
      "source.fixAll": "explicit"
    }
  },
  "files.associations": {
    "**/.env*": "properties"
  }
}
```

### 调试配置

创建 `.vscode/launch.json` 文件：

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Debug API Server",
      "type": "python",
      "request": "launch",
      "program": "${workspaceFolder}/src/api/server.py",
      "console": "integratedTerminal",
      "envFile": "${workspaceFolder}/.env",
      "cwd": "${workspaceFolder}"
    },
    {
      "name": "Debug CLI Command",
      "type": "python",
      "request": "launch",
      "program": "${workspaceFolder}/src/cli/main.py",
      "console": "integratedTerminal",
      "envFile": "${workspaceFolder}/.env",
      "cwd": "${workspaceFolder}",
      "args": ["analyze", "--task-id", "11745664"]
    },
    {
      "name": "Debug Test File",
      "type": "python",
      "request": "launch",
      "module": "pytest",
      "console": "integratedTerminal",
      "envFile": "${workspaceFolder}/.env",
      "cwd": "${workspaceFolder}",
      "args": ["tests/test_clustering.py", "-v"]
    }
  ]
}
```

## 测试指南

### 运行测试

```bash
# 运行所有测试
pytest tests/ -v --cov=src

# 运行特定测试文件
pytest tests/test_clustering.py -v

# 运行特定测试
pytest tests/test_clustering.py::test_cluster_analysis -v

# 运行端到端测试
pytest tests/e2e/ -v

# 生成覆盖率报告
pytest tests/ -v --cov=src --cov-report=html
```

### 测试框架

系统使用 pytest 作为测试框架，支持以下功能：

- 简单的测试定义
- 测试装置（fixtures）
- 参数化测试
- 异步测试（使用 pytest-asyncio）
- 覆盖率分析（使用 pytest-cov）

### 测试装置

在 `tests/conftest.py` 中定义了全局的测试装置：

```python
import pytest
from src.config.manager import ConfigManager

@pytest.fixture(scope="session")
def test_config():
    """测试配置装置"""
    return ConfigManager()

@pytest.fixture(scope="function")
def mock_task_data():
    """模拟任务数据装置"""
    return {
        "task_id": "11745664",
        "title": "任务标题",
        "description": "任务描述",
        "status": "closed",
        "priority": "high"
    }
```

### 模拟对象

使用 unittest.mock 库模拟外部依赖：

```python
from unittest.mock import patch, MagicMock

def test_analyze_task_with_mock():
    """使用模拟对象测试任务分析"""
    with patch("src.api.client.APIClient.get_task") as mock_get_task:
        # 配置模拟行为
        mock_task = MagicMock()
        mock_task.task_id = "11745664"
        mock_task.title = "任务标题"
        mock_get_task.return_value = mock_task

        # 调用被测试函数
        result = analyze_task("11745664")

        # 验证行为
        assert result.task_id == "11745664"
        mock_get_task.assert_called_once_with("11745664")
```

## 调试技巧

### 1. 启用调试日志

```bash
# 设置环境变量
export LOG_LEVEL=DEBUG

# 或在代码中设置
from loguru import logger
logger.remove()
logger.add(sys.stderr, level="DEBUG")
```

### 2. 使用日志记录调试信息

```python
from loguru import logger

def analyze_task(task_id: str):
    logger.debug(f"开始分析任务: {task_id}")

    try:
        # 分析过程
        logger.debug(f"任务数据获取成功: {task_id}")
    except Exception as e:
        logger.error(f"分析任务失败: {task_id}, 错误: {str(e)}")
        raise
```

### 3. 启用交互式调试

```python
import ipdb

def analyze_task(task_id: str):
    # 在需要调试的地方设置断点
    ipdb.set_trace()

    # 分析过程
    pass
```

### 4. 使用请求拦截器

```python
# 在测试或开发过程中，使用请求拦截器模拟 API 响应
from unittest.mock import patch
import json

def mock_api_response(url, *args, **kwargs):
    if "inter-analysis" in url:
        return MagicMock(
            status_code=200,
            json=lambda: {"data": {"apiDevTaskAnalysis": {"reason": "测试原因"}}}
        )
    return MagicMock(status_code=404)

with patch("httpx.AsyncClient.request", side_effect=mock_api_response):
    # 调用需要测试的函数
    result = get_fault_analysis("11745664")
```

## 常见问题

### Q: 如何处理 API 调用失败？

A:
1. 检查 API 配置是否正确（API_BASE_URL 和 DEVCLOUD_TOKEN）
2. 检查网络连接是否正常
3. 检查 API 服务是否可用
4. 查看日志以获取更多信息

### Q: 如何处理 LLM 服务失败？

A:
1. 检查 LLM 配置是否正确（LLM_PROVIDER、LLM_MODEL、LLM_API_KEY）
2. 检查网络连接是否正常
3. 检查 LLM 服务是否可用
4. 查看日志以获取更多信息

### Q: 如何处理嵌入生成失败？

A:
1. 检查 Embedding 配置是否正确（EMBEDDING_PROVIDER、EMBEDDING_MODEL、EMBEDDING_API_KEY）
2. 检查网络连接是否正常
3. 检查 Embedding 服务是否可用
4. 查看日志以获取更多信息

### Q: 如何处理性能问题？

A:
1. 使用缓存减少重复计算
2. 使用批处理提高效率
3. 优化代码逻辑
4. 使用并行计算
5. 分析性能瓶颈

### Q: 如何处理内存问题？

A:
1. 优化数据处理逻辑
2. 使用流式处理
3. 增加系统内存
4. 优化算法复杂度

---

**最后更新**: 2026-03-31
