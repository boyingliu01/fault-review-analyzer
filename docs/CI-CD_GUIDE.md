# CI/CD 使用指南

本文档介绍故障复盘分析工具的 CI/CD 流程和开发工具使用方法。

## 目录

- [GitHub Actions 工作流](#github-actions-工作流)
- [预提交钩子](#预提交钩子)
- [开发脚本](#开发脚本)
- [快速开始](#快速开始)

---

## GitHub Actions 工作流

项目使用 GitHub Actions 实现持续集成和持续部署。

### 工作流文件

位置：`.github/workflows/ci.yml`

### 触发条件

- **Push 事件**：向 `main`、`master`、`develop` 分支推送代码时
- **Pull Request 事件**：向 `main`、`master` 分支提交 PR 时

### 工作流 Jobs

#### 1. Test Job (测试任务)

在 Python 3.10、3.11、3.12 三个版本上运行：

| 步骤 | 描述 |
|------|------|
| 安装依赖 | `pip install -e ".[dev]"` |
| 代码检查 | `ruff check` + `ruff format --check` |
| 类型检查 | `mypy src/` |
| 运行测试 | `pytest` + 覆盖率报告 |
| 上传覆盖率 | 到 Codecov (可选) |

#### 2. Build Job (构建任务)

仅在向 `main`/`master` 分支 push 时运行：

| 步骤 | 描述 |
|------|------|
| 构建 | `python -m build` |
| 检查 | `twine check dist/*` |
| 上传 | 构建产物作为 artifacts |

---

## 预提交钩子

项目使用 `pre-commit` 框架在提交代码前自动运行检查。

### 安装钩子

```bash
pre-commit install
```

### 钩子列表

| 钩子 | 描述 |
|------|------|
| `trailing-whitespace` | 移除行尾空格 |
| `end-of-file-fixer` | 确保文件以换行结尾 |
| `check-yaml` | 检查 YAML 格式 |
| `check-added-large-files` | 检查大文件 (>1MB) |
| `check-merge-conflict` | 检查合并冲突标记 |
| `debug-statements` | 检查调试语句 |
| `check-json` | 检查 JSON 格式 |
| `detect-secrets` | 检测密钥泄露 |
| `ruff` | 代码 lint + 自动修复 |
| `ruff-format` | 代码格式化 |
| `mypy` | 类型检查 |
| `pytest-check` | 运行快速测试 |

### 手动运行所有钩子

```bash
pre-commit run --all-files
```

### 跳过钩子提交（不推荐）

```bash
git commit --no-verify -m "..."
```

---

## 开发脚本

### 1. `scripts/setup_dev.sh` - 开发环境初始化

一键配置完整开发环境。

**功能：**
- 检查 Python 版本 (≥3.10)
- 创建虚拟环境 `.venv/`
- 安装所有开发依赖
- 安装 pre-commit 钩子
- 创建 `.env` 配置文件
- 创建必要的数据目录

**使用：**
```bash
./scripts/setup_dev.sh
source .venv/bin/activate  # Linux/Mac
# 或
.venv\Scripts\activate     # Windows
```

---

### 2. `scripts/run_tests.sh` - 测试运行器

灵活的测试执行脚本。

**用法：**
```bash
./scripts/run_tests.sh [选项]
```

**常用选项：**

| 选项 | 描述 |
|------|------|
| `-a, --all` | 运行所有检查 (lint + type-check + test + coverage) |
| `-c, --coverage` | 生成覆盖率报告 |
| `-v, --verbose` | 详细输出 |
| `-t, --type-check` | 仅运行类型检查 |
| `-l, --lint` | 仅运行代码检查 |
| `-f <path>` | 运行指定文件/目录的测试 |

**示例：**

```bash
# 运行所有测试
./scripts/run_tests.sh

# 运行测试并生成覆盖率报告
./scripts/run_tests.sh -c

# 运行所有检查（lint + type + test）
./scripts/run_tests.sh -a

# 只运行 API 相关测试
./scripts/run_tests.sh -f tests/api/
```

---

### 3. `scripts/lint.sh` - 代码检查工具

快速运行代码 lint 和格式化。

**用法：**
```bash
./scripts/lint.sh [选项]
```

**常用选项：**

| 选项 | 描述 |
|------|------|
| `-a, --all` | 运行所有检查 (lint + format + type-check) |
| `-f, --fix` | 自动修复可修复的问题 |
| `-t, --type-check` | 运行类型检查 |
| `-F, --format` | 运行代码格式化 |

**示例：**

```bash
# 仅检查，不修改
./scripts/lint.sh

# 检查并自动修复
./scripts/lint.sh -f

# 运行所有检查 + 自动修复
./scripts/lint.sh -a -f
```

---

## 快速开始

### 新开发者环境配置

```bash
# 1. 克隆代码
git clone <repo-url>
cd Bug聚类分析

# 2. 初始化开发环境
./scripts/setup_dev.sh

# 3. 激活虚拟环境
source .venv/bin/activate  # Linux/Mac
# 或
.venv\Scripts\activate     # Windows

# 4. 编辑 .env 文件，填写 API 密钥等配置

# 5. 验证安装
./scripts/run_tests.sh -a
```

### 日常开发工作流

```bash
# 1. 创建功能分支
git checkout -b feature/my-feature

# 2. 编写代码...

# 3. 提交前运行检查
./scripts/lint.sh -a -f
./scripts/run_tests.sh -c

# 4. 提交代码 (pre-commit 钩子会自动运行)
git add .
git commit -m "feat: 添加我的功能"

# 5. 推送到远程并创建 PR
git push origin feature/my-feature
```

### 常见问题

**Q: pre-commit 钩子失败怎么办？**

A: 大多数问题会自动修复。如果没有：
```bash
# 查看具体错误
pre-commit run --all-files

# 手动修复后重新提交
git add .
git commit -m "..."
```

**Q: 如何跳过某个 hook？**

A: 在 `.pre-commit-config.yaml` 中临时注释掉，或使用 `SKIP` 环境变量：
```bash
SKIP=pytest-check git commit -m "..."
```

**Q: CI 在 GitHub 上失败但本地通过？**

A: 可能是 Python 版本差异。建议用 tox 或在本地多个版本测试：
```bash
# 查看 CI 失败日志，确定问题
# 本地对应版本测试
python3.10 -m pytest tests/
```
