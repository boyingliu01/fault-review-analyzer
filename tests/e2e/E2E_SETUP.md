# E2E 测试准备指南

## 快速检查清单

运行以下命令检查 E2E 测试准备状态：

```bash
# 1. 检查环境变量
python -c "import os; print('DEVCLOUD_TOKEN:', '已设置' if os.getenv('DEVCLOUD_TOKEN') else '未设置')"

# 2. 检查测试数据文件
ls -la data/测试用故障单号列表.xlsx

# 3. 检查 Playwright 浏览器
playwright install --help

# 4. 运行快速 E2E 测试
pytest tests/e2e/cli/test_fetch.py::TestCLIFetch::test_fetch_help -v
```

## 环境要求

### 1. 必需的环境变量

确保 `.env` 文件中包含以下配置：

```bash
# API 配置（研发云平台）
API_BASE_URL=https://dev.iwhalecloud.com
DEVCLOUD_TOKEN=your-devcloud-token-here  # 研发云访问令牌
API_TIMEOUT=30
API_RETRY=3

# LLM 配置（用于分析功能）
LLM_PROVIDER=openai
LLM_MODEL=gpt-4
LLM_API_KEY=your-api-key-here
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=4096
```

**获取 DEVCLOUD_TOKEN：**
1. 登录研发云平台
2. 进入个人设置 → API 令牌
3. 生成新的访问令牌
4. 复制到 `.env` 文件

### 2. 测试数据文件

**文件位置：** `data/测试用故障单号列表.xlsx`

**文件格式：**
| 故障单号 |
|---------|
| 11745664 |
| 11748712 |
| ... |

**创建示例数据：**
```python
import pandas as pd

# 创建示例数据
df = pd.DataFrame({"故障单号": [11745664, 11748712, 11750001, 11750002, 11750003]})
df.to_excel("data/测试用故障单号列表.xlsx", index=False)
```

### 3. Playwright 浏览器安装

```bash
# 安装 Playwright 浏览器（只需运行一次）
playwright install chromium

# 或者安装所有浏览器
playwright install

# 验证安装
playwright show-browsers
```

## E2E 测试结构

```
tests/e2e/
├── conftest.py              # E2E 共享 fixtures
├── fixtures/                # 测试数据 fixtures
│   ├── __init__.py
│   └── test_data.py
├── cli/                     # CLI 命令 E2E 测试
│   ├── __init__.py
│   ├── test_fetch.py        # fetch 命令测试
│   ├── test_analyze.py      # analyze 命令测试
│   └── test_report.py       # report 命令测试
├── pipeline/                # Pipeline E2E 测试
│   ├── __init__.py
│   ├── test_phase1.py       # Phase1: 数据准备
│   └── test_phase2.py       # Phase2: 聚类分析
└── ui/                      # UI E2E 测试
    ├── __init__.py
    ├── conftest.py          # UI 测试配置
    └── test_streamlit.py    # Streamlit 界面测试
```

## 运行 E2E 测试

### 基础命令

```bash
# 运行所有 E2E 测试
pytest tests/e2e/ -v

# 运行特定模块
pytest tests/e2e/cli/ -v              # 仅 CLI 测试
pytest tests/e2e/pipeline/ -v         # 仅 Pipeline 测试
pytest tests/e2e/ui/ -v               # 仅 UI 测试

# 排除 UI 测试（不需要浏览器）
pytest tests/e2e/ -v -m "not ui"

# 仅运行快速测试
pytest tests/e2e/ -v -m "not slow"
```

### 高级选项

```bash
# 生成 HTML 报告
pytest tests/e2e/ -v --html=e2e_report.html --self-contained-html

# 失败时重试
pytest tests/e2e/ -v --reruns 2 --reruns-delay 1

# 并行运行（需要 pytest-xdist）
pytest tests/e2e/ -v -n auto

# UI 测试带界面（非 headless 模式）
pytest tests/e2e/ui/ -v --headed

# UI 测试特定浏览器
pytest tests/e2e/ui/ -v --browser firefox
```

## 测试分类标记

| 标记 | 说明 | 运行命令 |
|-----|------|---------|
| `e2e` | 端到端测试 | `pytest -m e2e` |
| `ui` | UI 测试（需要浏览器） | `pytest -m ui` |
| `slow` | 慢速测试 | `pytest -m "not slow"` |

## 故障排除

### 1. DEVCLOUD_TOKEN 无效

**症状：** 测试跳过或 API 返回 401

**解决：**
```bash
# 验证令牌
curl -H "Authorization: Bearer $DEVCLOUD_TOKEN" \
  https://dev.iwhalecloud.com/portal/ai-gateway/devspace/rpc/v3/work-item/11745664/detail
```

### 2. Playwright 浏览器未安装

**症状：** `Executable doesn't exist` 错误

**解决：**
```bash
playwright install chromium
```

### 3. 测试数据文件不存在

**症状：** `测试数据文件不存在` 跳过信息

**解决：**
```bash
# 检查文件是否存在
ls -la data/测试用故障单号列表.xlsx

# 如果不存在，创建示例数据
python -c "
import pandas as pd
df = pd.DataFrame({'故障单号': [11745664, 11748712]})
df.to_excel('data/测试用故障单号列表.xlsx', index=False)
"
```

### 4. 异步测试失败

**症状：** `RuntimeError: Event loop is closed`

**解决：**
确保 `pytest-asyncio` 已安装：
```bash
pip install pytest-asyncio
```

## 持续集成

### GitHub Actions 示例

```yaml
name: E2E Tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"
          playwright install chromium

      - name: Run E2E tests
        env:
          DEVCLOUD_TOKEN: ${{ secrets.DEVCLOUD_TOKEN }}
        run: |
          pytest tests/e2e/ -v -m "not ui"
```

## 最佳实践

1. **不要提交真实 API 密钥** - 使用 `.env` 文件并在 `.gitignore` 中排除
2. **使用小数据集测试** - E2E 测试使用少量任务 ID（3-5个）以加快测试速度
3. **标记慢速测试** - 耗时超过 10 秒的测试应标记为 `slow`
4. **独立测试** - 每个测试应独立运行，不依赖其他测试状态
5. **清理测试产物** - 测试完成后清理临时文件和数据

## 相关文件

- `tests/e2e/conftest.py` - E2E 测试配置和 fixtures
- `tests/e2e/fixtures/test_data.py` - 测试数据 fixtures
- `playwright.config.py` - Playwright 配置
- `pytest.ini` / `pyproject.toml` - pytest 配置
