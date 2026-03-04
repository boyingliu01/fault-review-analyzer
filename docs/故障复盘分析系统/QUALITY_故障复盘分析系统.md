# 故障复盘分析系统 - 开发规范与质量标准

## 一、开发方法论：TDD (测试驱动开发)

### 1.1 TDD流程

```
┌─────────────────────────────────────────────────────────────┐
│                     TDD 开发循环                             │
│                                                              │
│    ┌──────────┐      ┌──────────┐      ┌──────────┐        │
│    │  RED     │ ──→  │  GREEN   │ ──→  │ REFACTOR │        │
│    │ 编写测试  │      │ 编写代码  │      │  重构    │        │
│    │ (失败)   │      │ (通过)   │      │ (优化)   │        │
│    └──────────┘      └──────────┘      └──────────┘        │
│         ↑                                     │              │
│         └─────────────────────────────────────┘              │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 每个任务的执行步骤

1. **编写测试用例** (RED)
   - 根据任务验收标准编写测试用例
   - 运行测试，确认测试失败
   
2. **编写实现代码** (GREEN)
   - 编写最少代码使测试通过
   - 不追求完美，只求通过
   
3. **重构优化** (REFACTOR)
   - 优化代码结构
   - 提取公共逻辑
   - 改善命名和注释
   - 确保测试仍然通过

4. **提交前检查**
   - 运行完整测试套件
   - 运行静态代码检查
   - 确认覆盖率达标

---

## 二、工具链配置

### 2.1 测试工具

| 工具 | 用途 | 配置 |
|-----|------|------|
| pytest | 测试框架 | pytest.ini |
| pytest-cov | 覆盖率 | --cov=src --cov-report=html |
| pytest-asyncio | 异步测试 | asyncio_mode = auto |
| pytest-mock | Mock工具 | - |
| faker | 测试数据生成 | - |

### 2.2 代码质量工具

| 工具 | 用途 | 配置 |
|-----|------|------|
| ruff | 代码检查+格式化 | ruff.toml (替代flake8, black, isort) |
| mypy | 类型检查 | mypy.ini |
| pre-commit | Git钩子 | .pre-commit-config.yaml |

### 2.3 为什么选择 Ruff？

Ruff 是目前 Python 生态中最快的代码检查和格式化工具：
- **速度**：比 Pylint 快 10-100 倍
- **功能**：替代 Flake8 + Black + isort + pydocstyle
- **兼容**：完全兼容现有工具链
- **活跃**：由 Astral 维护（Ruff 的开发者）

---

## 三、配置文件

### 3.1 pyproject.toml

```toml
[project]
name = "fault-review-analyzer"
version = "0.1.0"
description = "AI驱动的故障复盘分析工具"
requires-python = ">=3.10"
dependencies = [
    "typer>=0.9.0",
    "pydantic>=2.0.0",
    "pyyaml>=6.0.0",
    "httpx>=0.25.0",
    "openai>=1.0.0",
    "langchain>=0.1.0",
    "sentence-transformers>=2.2.0",
    "hdbscan>=0.8.0",
    "umap-learn>=0.5.0",
    "pandas>=2.0.0",
    "numpy>=1.24.0",
    "jinja2>=3.1.0",
    "loguru>=0.7.0",
    "rich>=13.0.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
    "pytest-asyncio>=0.21.0",
    "pytest-mock>=3.10.0",
    "faker>=18.0.0",
    "ruff>=0.1.0",
    "mypy>=1.0.0",
    "pre-commit>=3.0.0",
]

[project.scripts]
fault-analyzer = "src.cli.main:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = "-v --tb=short"

[tool.coverage.run]
source = ["src"]
branch = true
omit = ["tests/*", "*/__pycache__/*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
]
fail_under = 80

[tool.ruff]
line-length = 100
target-version = "py310"
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # pyflakes
    "I",      # isort
    "B",      # flake8-bugbear
    "C4",     # flake8-comprehensions
    "UP",     # pyupgrade
    "ARG",    # flake8-unused-arguments
    "SIM",    # flake8-simplify
]
ignore = [
    "E501",   # line too long (handled by formatter)
    "B008",   # do not perform function calls in argument defaults
]

[tool.ruff.per-file-ignores]
"tests/*" = ["ARG001", "S101"]

[tool.mypy]
python_version = "3.10"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
strict_optional = true

[[tool.mypy.overrides]]
module = ["hdbscan.*", "umap.*", "sentence_transformers.*"]
ignore_missing_imports = true
```

### 3.2 .pre-commit-config.yaml

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.6
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.7.0
    hooks:
      - id: mypy
        additional_dependencies:
          - pydantic>=2.0.0
          - types-PyYAML

  - repo: local
    hooks:
      - id: pytest-check
        name: pytest-check
        entry: pytest tests/ -x --tb=short
        language: system
        pass_filenames: false
        always_run: true
```

---

## 四、质量标准

### 4.1 测试覆盖率要求

| 指标 | 要求 |
|-----|------|
| 总体覆盖率 | ≥ 80% |
| 核心模块覆盖率 | ≥ 90% |
| 新增代码覆盖率 | 100% |

### 4.2 代码质量门禁

提交前必须通过以下检查：

```bash
# 1. 运行测试
pytest tests/ -v --cov=src --cov-report=term-missing

# 2. 代码检查
ruff check src/ tests/

# 3. 代码格式化
ruff format src/ tests/ --check

# 4. 类型检查
mypy src/
```

### 4.3 CI/CD 检查项

```yaml
# .github/workflows/ci.yml
jobs:
  test:
    steps:
      - name: Run tests
        run: pytest tests/ -v --cov=src --cov-fail-under=80
      
      - name: Ruff check
        run: ruff check src/ tests/
      
      - name: Ruff format check
        run: ruff format src/ tests/ --check
      
      - name: MyPy check
        run: mypy src/
```

---

## 五、规范扩展接口

### 5.1 规范加载器接口

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from pathlib import Path

class IRuleLoader(ABC):
    """规范加载器接口 - 预留公司定制规范扩展"""
    
    @abstractmethod
    def load(self, source: Path | str) -> List[Dict[str, Any]]:
        """
        从指定源加载规范
        
        Args:
            source: 规范文件路径或数据源标识
        
        Returns:
            规范列表，每个规范包含 id, name, category, patterns 等
        """
        pass
    
    @abstractmethod
    def validate(self, rule: Dict[str, Any]) -> bool:
        """验证规范格式是否正确"""
        pass


class BuiltinRuleLoader(IRuleLoader):
    """内置规范加载器"""
    pass


class CustomRuleLoader(IRuleLoader):
    """自定义规范加载器 - 用于加载公司定制规范"""
    
    def __init__(self, schema_path: Path | None = None):
        """
        Args:
            schema_path: 公司规范Schema定义文件路径
        """
        self.schema_path = schema_path
```

### 5.2 规范文件格式

```yaml
rule:
  id: "CUSTOM-001"
  name: "公司定制规范示例"
  category: "custom"
  description: "这是公司定制规范的示例格式"
  
  patterns:
    - type: "code"
      language: "java"
      regex: "Pattern.compile.*"
      message: "检测到正则表达式编译"
    
    - type: "log"
      regex: "ERROR.*timeout"
      message: "检测到超时错误日志"
  
  severity: "medium"
  
  suggestions:
    - "建议使用预编译的正则表达式"
    - "考虑增加超时重试机制"
  
  metadata:
    department: "研发中心"
    owner: "质量团队"
    version: "1.0.0"
    effective_date: "2024-01-01"
```

### 5.3 规范配置

```yaml
rules:
  builtin_enabled: true
  
  custom:
    enabled: true
    paths:
      - "./data/rules/company/"      # 公司定制规范目录
      - "./data/rules/project/"      # 项目特定规范目录
    
    schema: "./data/rules/schema.json"  # 规范Schema定义
```

---

## 六、开发工作流

### 6.1 开发前准备

```bash
# 1. 克隆项目
git clone <repo-url>
cd fault-review-analyzer

# 2. 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 3. 安装开发依赖
pip install -e ".[dev]"

# 4. 安装 pre-commit 钩子
pre-commit install
```

### 6.2 开发流程

```bash
# 1. 创建功能分支
git checkout -b feature/TASK-XXX

# 2. 编写测试用例 (RED)
# 编辑 tests/test_xxx.py
pytest tests/test_xxx.py -v  # 确认测试失败

# 3. 编写实现代码 (GREEN)
# 编辑 src/xxx.py
pytest tests/test_xxx.py -v  # 确认测试通过

# 4. 重构优化 (REFACTOR)
# 优化代码结构
pytest tests/test_xxx.py -v  # 确保测试仍然通过

# 5. 提交代码
git add .
git commit -m "feat: implement TASK-XXX"
# pre-commit 会自动运行检查

# 6. 推送并创建PR
git push origin feature/TASK-XXX
```

---

## 七、下一步

更新任务文档，将TDD流程纳入每个任务的执行步骤。
