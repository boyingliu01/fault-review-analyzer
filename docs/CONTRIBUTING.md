# 贡献指南

感谢你对故障复盘分析工具感兴趣！我们欢迎任何形式的贡献，包括但不限于代码贡献、文档改进、问题报告和功能建议。

## 目录

- [代码贡献](#代码贡献)
- [开发环境设置](#开发环境设置)
- [代码规范](#代码规范)
- [提交规范](#提交规范)
- [测试要求](#测试要求)
- [文档贡献](#文档贡献)
- [问题报告](#问题报告)
- [功能建议](#功能建议)
- [行为准则](#行为准则)

## 代码贡献

### 贡献流程

1. **Fork 项目仓库**: 在 GitHub 上 Fork 项目仓库到你的账户
2. **克隆仓库**: 将你的 Fork 克隆到本地
   ```bash
   git clone https://github.com/your-username/fault-review-analyzer.git
   cd fault-review-analyzer
   ```
3. **创建分支**: 从 master 分支创建一个新的功能分支
   ```bash
   git checkout -b feature/your-feature-name
   # 或者
   git checkout -b fix/your-fix-name
   ```
4. **进行修改**: 进行代码修改
5. **运行测试**: 确保所有测试通过
   ```bash
   pytest tests/ -v --cov=src
   ```
6. **提交更改**: 使用有意义的提交信息
   ```bash
   git add .
   git commit -m "feat: add new feature"
   ```
7. **推送到 Fork**: 将你的分支推送到你的 Fork
   ```bash
   git push origin feature/your-feature-name
   ```
8. **创建 Pull Request**: 在 GitHub 上创建一个 Pull Request

### Pull Request 要求

- **清晰的标题**: 使用简明扼要的标题描述你的更改
- **详细的描述**: 在描述中说明更改的目的、实现方式和影响
- **关联 Issue**: 如果更改与某个 Issue 相关，请在描述中引用它
- **代码检查**: 确保代码通过所有代码检查
- **测试覆盖**: 确保你的更改有足够的测试覆盖
- **文档更新**: 如果更改影响了文档，请同时更新文档

## 开发环境设置

### 系统要求

- Python 3.10 或更高版本
- Git
- 虚拟环境工具（推荐：venv 或 conda）

### 安装步骤

1. **克隆仓库**
   ```bash
   git clone https://github.com/your-username/fault-review-analyzer.git
   cd fault-review-analyzer
   ```

2. **创建虚拟环境**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   # 或
   .venv\Scripts\activate  # Windows
   ```

3. **安装依赖**
   ```bash
   pip install -e ".[dev]"
   ```

4. **安装 pre-commit 钩子**
   ```bash
   pre-commit install
   ```

5. **配置环境变量**
   ```bash
   cp .env.example .env
   # 编辑 .env 文件，填入必要的配置
   ```

6. **运行测试**
   ```bash
   pytest tests/ -v --cov=src
   ```

## 代码规范

### 代码风格

我们使用以下工具进行代码风格检查和格式化：

- **Ruff**: 代码检查和格式化
- **mypy**: 类型检查

#### 运行代码检查

```bash
# 代码检查
ruff check src/ tests/

# 代码格式化
ruff format src/ tests/

# 类型检查
mypy src/
```

#### 代码规范

- **行长度**: 最大 100 字符
- **缩进**: 使用 4 个空格
- **引号**: 字符串优先使用双引号
- **导入顺序**: 遵循 isort 导入顺序（由 Ruff 自动处理）
- **类型注解**: 所有函数必须有类型注解
- **文档字符串**: 公共函数和类必须有文档字符串

### 命名规范

- **变量名**: 使用 snake_case（例如：`task_id`, `user_name`）
- **函数名**: 使用 snake_case（例如：`get_task`, `analyze_fault`）
- **类名**: 使用 PascalCase（例如：`APIClient`, `FaultAnalyzer`）
- **常量名**: 使用 UPPER_SNAKE_CASE（例如：`MAX_RETRIES`, `DEFAULT_TIMEOUT`）
- **私有成员**: 使用单下划线前缀（例如：`_internal_method`, `_private_attr`）

### 日志规范

- 使用 `loguru` 进行日志记录
- 日志级别：
  - `DEBUG`: 详细的调试信息
  - `INFO`: 一般信息
  - `WARNING`: 警告信息
  - `ERROR`: 错误信息
  - `CRITICAL`: 严重错误信息

示例：
```python
from loguru import logger

logger.debug("Debug information")
logger.info("General information")
logger.warning("Warning message")
logger.error("Error occurred")
logger.critical("Critical error")
```

## 提交规范

### 提交信息格式

我们使用 Conventional Commits 规范：

```
<type>(<scope>): <subject>

<body>

<footer>
```

### 类型 (type)

- `feat`: 新功能
- `fix`: 修复 bug
- `docs`: 文档更新
- `style`: 代码格式调整（不影响功能）
- `refactor`: 重构（既不新增功能，也不修复 bug）
- `perf`: 性能优化
- `test`: 测试相关
- `chore`: 构建/工具链相关

### 示例

```
feat(clustering): add support for K-Means algorithm

- Add K-Means clustering implementation
- Add configuration options for K-Means
- Add tests for K-Means clustering

Closes #123
```

```
fix(api): handle rate limit errors gracefully

- Add retry mechanism for rate limit errors
- Improve error message for rate limiting
- Add tests for rate limit handling

Fixes #456
```

## 测试要求

### 测试类型

- **单元测试**: 测试单个函数或类
- **集成测试**: 测试多个组件的交互
- **端到端测试**: 测试完整的功能流程

### 运行测试

```bash
# 运行所有测试
pytest tests/ -v --cov=src

# 运行单个测试文件
pytest tests/test_clustering.py -v

# 运行特定测试
pytest tests/test_clustering.py::test_cluster_analysis -v

# 运行端到端测试
pytest tests/e2e/ -v

# 生成覆盖率报告
pytest tests/ -v --cov=src --cov-report=html
```

### 测试覆盖率要求

- 测试覆盖率必须达到 **79.9%** 或更高
- 新功能必须包含相应的测试
- 修复 bug 时，建议添加测试以防止回归

### 测试编写指南

- 使用清晰的测试名称
- 每个测试应该只测试一个功能
- 使用 `arrange-act-assert` 模式
- 为测试添加适当的注释
- 测试应该是独立的，不依赖于其他测试的执行顺序

示例：
```python
import pytest
from src.clustering.analyzer import ClusterAnalyzer

def test_cluster_analysis():
    # Arrange
    analyzer = ClusterAnalyzer(min_cluster_size=3)
    embeddings = [[1.0, 2.0], [1.1, 2.1], [3.0, 4.0], [3.1, 4.1], [1.2, 2.2]]

    # Act
    clusters = analyzer.analyze(embeddings)

    # Assert
    assert len(clusters) == 2
    assert clusters[0].size == 3
    assert clusters[1].size == 2
```

## 文档贡献

### 文档类型

- **API 文档**: 描述 API 接口的使用方法
- **用户文档**: 面向用户的使用指南
- **开发者文档**: 面向开发者的技术文档
- **架构文档**: 描述系统架构和设计决策
- **贡献指南**: 本文档

### 文档格式

- 使用 Markdown 格式
- 使用清晰的标题和子标题
- 添加代码示例
- 添加适当的链接
- 保持中文为主

### 更新文档

如果你的代码更改影响了文档，请同时更新相关文档：

- **API 变更**: 更新 `docs/API.md`
- **架构变更**: 更新 `docs/ARCHITECTURE.md`
- **功能变更**: 更新相关的用户文档或开发者文档

## 问题报告

### 提交 Issue

如果你发现了一个 bug 或有问题，请在 GitHub 上提交 Issue：

1. 搜索现有的 Issues，看是否已经有人报告了相同的问题
2. 如果没有，创建一个新的 Issue
3. 使用清晰的标题描述问题
4. 在描述中包含以下信息：
   - 问题的详细描述
   - 复现步骤
   - 预期行为
   - 实际行为
   - 系统环境（操作系统、Python 版本、依赖版本等）
   - 错误日志（如果有）
   - 截图（如果有帮助）

### Issue 模板

我们提供了 Issue 模板，请在提交 Issue 时使用它。

## 功能建议

我们欢迎功能建议！如果你有一个想法，请：

1. 搜索现有的 Issues 和 Pull Requests，看是否已经有人提出了类似的建议
2. 创建一个新的 Issue
3. 使用清晰的标题描述建议
4. 在描述中包含以下信息：
   - 建议的功能描述
   - 功能的用例
   - 可能的实现方式
   - 替代方案（如果有）

## 行为准则

### 我们的承诺

为了营造开放和友好的环境，我们承诺：

- 尊重不同的观点和经验
- 优雅地接受建设性批评
- 关注对社区最有利的事情
- 对其他社区成员表示同理心

### 不可接受的行为

- 使用性化的语言或图像
- 恶意评论或人身攻击
- 公开或私下骚扰
- 未经许可发布他人的私人信息
- 其他不专业或不恰当的行为

### 责任

项目维护者有责任澄清可接受行为的标准，并对任何不可接受的行为采取适当和公平的纠正措施。

## 获取帮助

如果你在贡献过程中需要帮助：

- 提交 Issue 并使用 "question" 标签
- 在相关的 Pull Request 中评论
- 联系项目维护者

## 感谢

再次感谢你的贡献！我们期待与你一起改进故障复盘分析工具。

---

**最后更新**: 2026-03-31
