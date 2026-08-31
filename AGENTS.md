# AGENTS.md

This file provides guidance to Qoder (qoder.com) when working with code in this repository.

## Project Overview
**Fault Review Analyzer** - AI驱动的故障复盘分析工具，使用HDBSCAN聚类自动发现故障模式，通过LLM提取技术标签并识别规范冲突。

## Project Structure
```
src/
├── cli/              # Typer CLI入口 (fault-analyzer命令)
├── api/              # REST API客户端 (HTTPX异步)
├── analyzer/         # 分析流程编排与聚类
│   ├── labeling/     # LLM智能标签生成
│   └── reasoning/    # 根因分析推理
├── analysis/         # 独立分析模块
├── clustering/       # HDBSCAN聚类实现
├── embedding/        # Embedding生成
├── preprocessor/     # 数据清洗与格式化
├── cache/            # SQLite缓存管理
├── feedback/         # 反馈采集与复发检测
├── config/           # Pydantic配置管理
├── rules/            # 规范规则引擎
├── report/           # Jinja2报告生成
├── ui/               # Streamlit Web界面
└── utils/            # 工具函数

tests/                # pytest测试 (镜像src结构)
data/                 # 缓存数据与规则定义
output/               # 生成报告 (可安全清理)
```

## Setup & Environment
- Python >=3.10 (支持3.10/3.11/3.12)
- 安装: `pip install -e ".[dev]"`
- 配置: 复制 `.env.example` → `.env`，填写 API keys
- Pre-commit: `pre-commit install`

## Build, Test, and Development Commands

### CLI Commands
```bash
fault-analyzer --help                     # 查看所有命令
fault-analyzer fetch --task-id <id>       # 获取故障数据
fault-analyzer analyze --task-id <id>     # 分析故障
fault-analyzer report --task-id <id>      # 生成报告
```

### Testing (Important for Single Test)
```bash
# 运行所有测试
pytest -v --cov=src

# 运行单个测试文件
pytest tests/test_pipeline.py -v

# 运行单个测试类
pytest tests/test_pipeline.py::TestAnalysisPipeline -v

# 运行单个测试方法
pytest tests/test_pipeline.py::TestAnalysisPipeline::test_pipeline_init -v

# 按标记运行
pytest -m "not e2e" -v                    # 排除e2e测试
pytest -m "e2e" -v                        # 仅e2e测试

# 覆盖率检查 (阈值80%)
pytest -v --cov=src --cov-report=term-missing
```

### Linting & Formatting
```bash
ruff check src/ tests/                    # 静态检查
ruff check src/ tests/ --fix              # 自动修复
ruff format src/ tests/                   # 格式化
mypy src/                                 # 类型检查
pre-commit run --all-files                # 全部钩子
```

## Code Style Guidelines

### Indentation & Line Length
- **4空格缩进** (非tab)
- **最大行长度100** (Ruff强制执行)
- Python 3.10+语法特性

### Naming Conventions
| 类型 | 规范 | 示例 |
|------|------|------|
| 模块/文件 | snake_case | `pipeline.py`, `root_cause_analyzer.py` |
| 类 | PascalCase | `AnalysisPipeline`, `PipelineConfig` |
| 函数/变量 | snake_case | `run_single()`, `task_data` |
| 常量 | UPPER_SNAKE | `DEFAULT_TIMEOUT`, `MAX_RETRIES` |
| 私有方法 | _前缀 | `_fetch_task()`, `_get_api_client()` |

### Import Style
```python
# 标准库
import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# 第三方库
import httpx
import numpy as np
import typer

# 内部模块 (src作为first-party)
from src.analyzer.pipeline import AnalysisPipeline
from src.api.client import APIClient
```

**Import规则:**
- 按标准库 → 第三方 → 内部模块分组
- 每组之间空一行
- 使用 `from src.xxx import xxx` 绝对导入
- 避免相对导入

### Type Hints (Mypy强制)
```python
# 必须添加类型注解
async def run_single(self, task_id: int) -> PipelineResult:
    ...

# 可选/Union类型
result: PipelineResult | None = None
data: dict[str, Any] = {}

# 列表/字典泛型
labels: list[dict] = []
task_ids: list[int] = []
```

**Mypy配置:**
- `disallow_untyped_defs = true` - 所有函数必须有类型
- `disallow_incomplete_defs = true` - 参数和返回值都必须注解
- `strict_optional = true` - 严格可选类型

### Error Handling
```python
# 自定义异常层次结构
from src.api.exceptions import (
    APIConnectionError,
    APIError,
    AuthenticationError,
    NotFoundError,
)

# 使用try-except处理预期异常
async def _request(self, method: str, endpoint: str) -> dict[str, Any]:
    for attempt in range(self.retry):
        try:
            response = await self._client.request(method, endpoint)
            ...
        except httpx.ConnectError as e:
            last_error = APIConnectionError(str(e))
            if attempt < self.retry - 1:
                await asyncio.sleep(2 ** attempt)
        except (AuthenticationError, NotFoundError):
            raise
```

### Dataclasses & Models
```python
@dataclass
class PipelineConfig:
    """Configuration for analysis pipeline."""

    use_cache: bool = True
    use_llm: bool = False
    output_path: Path = field(default_factory=lambda: Path("./output"))
```

### Path Handling
```python
# 使用pathlib代替os.path
from pathlib import Path

output_path = Path("./output") / f"report_{task_id}.md"
output_path.mkdir(parents=True, exist_ok=True)
```

### Logging
```python
from loguru import logger

logger.info(f"Processing task {task_id}")
logger.error(f"Failed to fetch task: {e}")
```

## Testing Guidelines

### Test Structure
```python
class TestAnalysisPipeline:
    """Test suite for AnalysisPipeline."""

    @pytest.fixture
    def mock_config(self):
        return MagicMock()

    def test_pipeline_init(self, mock_config):
        pipeline = AnalysisPipeline(config=mock_config)
        assert pipeline._config == mock_config

    @pytest.mark.asyncio
    async def test_run_single(self, mock_config):
        ...
```

### Async Testing
```python
import pytest

@pytest.mark.asyncio
async def test_async_operation():
    result = await async_function()
    assert result is not None
```

### Mocking
```python
from unittest.mock import AsyncMock, MagicMock, patch

with patch.object(pipeline, "_fetch_task", new_callable=AsyncMock) as mock_fetch:
    mock_fetch.return_value = mock_task
    result = await pipeline.run_single(12345)
```

### Coverage Requirements
- 单元测试覆盖率 >= 80%
- 排除: `src/cli/*`, `src/ui/*`, `tests/*`
- 使用 `pytest -v --cov=src` 验证

## Commit & PR Guidelines

### Conventional Commits
```
feat(api): add retry backoff for failed requests
fix(analyzer): handle missing task data gracefully
test(clustering): add edge cases for HDBSCAN
chore(deps): update pandas to 2.2.0
docs(readme): update installation instructions
```

### PR Requirements
- 描述意图和主要变更
- 引用相关task/issue ID
- 附测试证据 (`pytest`输出或覆盖率变化)
- UI/报告变更需附截图或示例

## Security & Data Handling
- **禁止提交真实API密钥** - 使用 `.env` 文件管理
- **禁止提交生产故障数据** - 使用 `data/` 目录中的脱敏fixtures
- **清理输出** - `output/` 目录内容分享前需脱敏
- Secrets检测: pre-commit hook自动运行 `detect-secrets`

## Ruff Lint Rules
- **E, W**: pycodestyle错误/警告
- **F**: Pyflakes
- **I**: isort导入排序
- **B**: flake8-bugbear
- **UP**: pyupgrade
- **PTH**: 使用pathlib

**忽略规则:** `E501`(行长度由formatter处理), `B008`(默认参数函数调用), `ARG001`(未使用函数参数)
