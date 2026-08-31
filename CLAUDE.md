# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Fault Review Analyzer (故障复盘分析工具)** — An AI-driven pipeline that clusters similar bugs/incidents and discovers root causes without pre-defined labels. It fetches task data from a REST API, preprocesses text, generates vector embeddings via multiple providers (OpenAI, Zhipu, Volcengine, local sentence-transformers), applies HDBSCAN density-based clustering, followed by LLM-based labeling and root cause analysis.

## Development Commands

```bash
# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Copy environment template and fill in keys
cp .env.example .env

# Run all tests with coverage
pytest tests/ -v --cov=src

# Run a single test file
pytest tests/test_clustering.py -v

# Linting and formatting
ruff check src/ tests/
ruff format src/ tests/

# Type checking
mypy src/

# Run full pre-commit hook suite
pre-commit run --all-files
```

The CLI entry point after install:
```bash
fault-analyzer --help
# Common subcommands: fetch --task-id <id>, analyze --task-id <id>, report --task-id <id> --output ./output
```

Run the Streamlit dashboard:
```bash
streamlit run src/ui/streamlit_app.py
```

Run the batch analysis scripts directly (no install required):
```bash
python scripts/run_all_parallel.py all   # Fetch + analyze all tasks (writes output/progress_<urId>.json)
```

## Architecture

Data flows through a five-stage pipeline orchestrated by `src/analyzer/pipeline.py` (`AnalysisPipeline`):

1. **Fetch** (`src/api/`) — `APIClient` (async context manager, httpx) fetches task/bug records and persists them in SQLite cache with TTL via `CacheManager`.
2. **Preprocess** (`src/preprocessor/`) — `DataPreprocessor` extracts text segments and combines them into a single string per task.
3. **Embed** (`src/embedding/`) — `EmbeddingGenerator` supports multiple providers (OpenAI, Zhipu, Volcengine, local) in async batches.
4. **Cluster** (`src/clustering/`) — `ClusterAnalyzer` runs HDBSCAN and emits clustering results.
5. **Analyze** (`src/analyzer/labeling/`, `src/analyzer/reasoning/`) — `LabelGenerator` assigns categories via LLM; `RootCauseAnalyzer` produces structured analysis.

### Module Layout

| Module | Description |
|---------|-------------|
| `src/analyzer/pipeline.py` | Main orchestration, coordinates all components |
| `src/analyzer/labeling/` | LLM-based intelligent label generation |
| `src/analyzer/reasoning/` | LLM-based root cause analysis |
| `src/api/` | REST API client for fetching task data |
| `src/clustering/` | HDBSCAN clustering algorithm implementation |
| `src/embedding/` | Multi-provider embedding generation |
| `src/preprocessor/` | Data cleaning and formatting |
| `src/rules/` | Rule-based violation detection engine |
| `src/report/` | Report generator with Jinja2 templates |
| `src/feedback/` | Feedback collection and recurrence detection |
| `src/visualization/` | Chart generation (Plotly) and scatter plots |
| `src/ui/streamlit_app.py` | Streamlit Web application |
| `src/config/manager.py` | Configuration manager (YAML + env vars) |
| `src/cache/manager.py` | SQLite cache management |
| `src/knowledge/manager.py` | Development standards management |
| `src/core/models.py` | Shared data models across analysis layer |
| `src/analysis/` | Independent analysis modules (violation, root cause, improvement) |
| `src/analysis/root_cause/` | 深度根因分析模块（5层追问机制） |

### Root Cause Analysis Module (`src/analysis/root_cause/`)

**功能**：基于故障单信息 + 现有复盘结论，进行5层深度根因挖掘

**核心组件**：
- `models.py` - 数据模型（FaultAnalysisInput, RootCause, ActionableImprovement）
- `prompts.py` - Prompt模板（5层分析、追问机制）
- `analyzer.py` - 分析服务（DeepRootCauseAnalyzer）

**使用方式**：
```python
from src.analysis.root_cause import DeepRootCauseAnalyzer, FaultAnalysisInput, ExistingFaultAnalysis

analyzer = DeepRootCauseAnalyzer(llm_provider)
result = await analyzer.analyze(fault_input, existing_analysis)
```

**Pipeline集成**：
```python
# 在 pipeline.py 中使用
config = PipelineConfig(analyze_root_cause_deep=True)
result = await pipeline.run(task_no, config)
# result.deep_root_causes 包含深度根因分析结果
```

### Coding Conventions

- Max line length: **100** (enforced by Ruff formatter)
- Logging: use **`loguru`** (`from loguru import logger`)
- File paths: prefer **`pathlib.Path`**
- Commit messages: Conventional Commits (`feat`, `fix`, `chore`, `test`, `docs`)

## Configuration

Configuration is loaded from `config/config.yaml` with environment variable overrides:

```bash
# 研发云平台认证
DEVCLOUD_TOKEN=<devcloud-access-token>

# LLM configuration
LLM_PROVIDER=volcengine
LLM_MODEL=doubao-seed-1-8-251228
LLM_API_KEY=...
LLM_BASE_URL=https://ark.cn-beijing.volces.com/api/v3

# Embedding configuration
EMBEDDING_PROVIDER=volcengine
EMBEDDING_MODEL=doubao-embedding-vision-251215
EMBEDDING_API_KEY=...
EMBEDDING_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
```

Key config sections:
- `api.api_key` — 研发云访问令牌 (DEVCLOUD_TOKEN)
- `llm.provider` / `llm.model` — LLM provider and model
- `embedding.provider` / `embedding.model` — Embedding provider and model
- `clustering.min_cluster_size` — HDBSCAN minimum cluster size (default: 3)
- `clustering.metric` — Distance metric (cosine)
- `cache.ttl` — SQLite cache TTL in seconds (default: 86400)

## Data Storage

- **SQLite Cache**: `./data/cache.db` — API response cache (TTL: 24 hours)
- **Image Evidence**: `./output/cos_images/` — Downloaded fault screenshots + vision-LLM extracted evidence cache
- **Rules**: `src/rules/builtin/` and `data/rules/custom/` — Built-in and custom rules
- **Standards**: `data/standards/` — JSON-formatted development standards
- **Reports**: `./output/` — Analysis reports (configurable)

## Test Data

### Fault/Bug Lists (故障单列表)

| File | Description | Count |
|------|-------------|-------|
| `故障单列表.xlsx` | 完整故障单号列表（仅缺陷单号列） | 1924条 |
| `data/测试用故障单号列表.xlsx` | 测试用故障单号列表 | 336条 |

**故障单号样本（前10条）：**
```
11751534, 11751363, 11750733, 11749289, 11748873, 11748726, 11748712, 11747703, 11746253, 11745664
```

**示例：有代码变更的故障单（isCommitCode=Y）**：
- `11745664` - reconnection复装业务更换卡类型问题
- `11748712` - 创建唯一索引和主键约束

### 开发规范文档

**浩鲸Java编码规范**：`docs/浩鲸在线规范库.pdf`（212页）

**关键规范章节**：
- 2.1 集合处理（J000000-J000013）：hashCode/equals、subList、Map遍历、ConcurrentModificationException等
- 2.2 并发处理（J000014）：单例线程安全
- 3.1 内存管理（J000107-J000113）：对象引用、内存回收、SQL拼装
- 3.2 并发集合（J000114-J000119）：线程安全集合、ArrayList初始化容量
- 3.3 字符串处理（J000120-J000123）：字符串连接、字符遍历
- 3.4 并发编程（J000124-J000127）：正则预编译、synchronized优化
- 3.5 IO处理（J000127）：try-with-resources资源关闭
- 安全篇：输入校验、异常行为、SQL注入防护

### Swagger API Data Source

接口文档：`swagger.txt`（位于项目根目录，OpenAPI 3.1.0格式）

**API调用前缀**：
```
Base URL: https://dev.iwhalecloud.com
Prefix: /portal/ai-gateway/devspace
完整路径示例: POST https://dev.iwhalecloud.com/portal/ai-gateway/devspace/rpc/v3/bug/{taskNo}/detail
```

**研发云文档中心 (docs.iwhalecloud.com)**：
- 独立于研发管理 API 的文档系统
- 需要 Bearer Token 认证（已配置在 `.env` 的 `DEVCLOUD_TOKEN`）
- 返回 HTML 需要 JS 渲染后才能获取实际内容
- 无法通过 API 直接获取文档内容（需模拟浏览器渲染）

**核心查询接口（按taskNo/taskId）：**

| # | 接口名称 | 方法 | 路径 | 备注 |
|---|---------|------|------|------|
| 1 | 任务单详情 | POST | `/rpc/v3/work-item/{taskNo}/detail` | |
| 2 | 需求单详情 | POST | `/rpc/v3/user-story/{taskNo}/detail` | |
| 3 | 缺陷单详情 | POST | `/rpc/v3/bug/{taskNo}/detail` | ✅ 已验证 |
| 4 | 事务单详情 | POST | `/rpc/v3/task/task-no/{taskNo}` | |
| 5 | 操作历史 | POST | `/task/{taskId}/action` | ⚠️ 可能返回404 |
| 6 | 评论列表 | POST | `/task/{taskId}/comment` | ⚠️ 可能返回404 |
| 7 | 验收点 | GET | `/task/{taskId}/review` | ⚠️ 可能返回404 |
| 8 | 影响评估 | GET | `/task/{taskId}/impact` | ⚠️ 可能返回404 |
| 9 | 代码分支 | POST | `/rpc/v3/task-branch/{taskNo}/commit-range` | ⚠️ 可能返回空 |
| 10 | 代码变动 | POST | `/rpc/v3/task-branch/{taskNo}/changes/content` | ⚠️ 可能返回空 |
| 11 | 工时汇总 | GET | `/task/{taskId}/work-hour/summary` | ⚠️ 可能返回404 |
| 12 | 评审纪要 | GET | `/task/audit-summary/{taskAuditSummaryId}` | |
| 13 | 故障复盘结论 | POST | `/rpc/v3/{taskNo}/inter-analysis` | ✅ 已验证 |

**备注**：
- ✅ 已验证 - 接口已测试可用
- ⚠️ 可能返回404 - 测试环境Swagger文档与实际接口可能不一致，需联系研发确认

### 故障复盘数据接口返回字段

**接口**：`POST /rpc/v3/{taskNo}/inter-analysis`

返回结构：
```json
{
  "data": {
    "taskNo": "11745664",
    "apiDevTaskAnalysis": {
      "ownerTeamName": "智启",
      "analysisCatalog": {"name": "研发环节", "nameEn": "Development Phase"},
      "analysisCatalogDetail": {"name": "正常场景遗漏", "nameEn": "Missing normal scenarios"},
      "reason": "详细原因描述...",
      "conclusion": "考虑其他涉及虚拟卡换卡的场景",
      "improveStage": "代码重构+自动化单元测试",
      "improveUserDto": {...},
      "createUserDto": {...},
      "createdTime": "2025-12-25 15:19:54"
    },
    "apiTestTaskAnalysis": {
      "ownerTeamName": "天璇",
      "analysisCatalog": {"name": "测试设计类", "nameEn": "Test Design Category"},
      "analysisCatalogDetail": {"name": "关联场景考虑不全", "nameEn": "Incomplete Consideration of Related Scenarios"},
      "reason": "详细原因描述...",
      "conclusion": "梳理esim相关业务整理专题",
      "improveStage": "模块测试",
      "improveUserDto": {...},
      "createUserDto": {...},
      "createDate": "2025-12-30 10:42:55"
    },
    "apiMgrTaskAnalysis": {
      "testImproveStage": "模块测试",
      "devImproveStage": "代码重构+自动化单元测试",
      "createUserDto": {...},
      "createDate": "2026-01-14 22:30:31"
    }
  }
}
```

## Testing

Test coverage threshold: **≥79.9%** (excludes `src/cli/*` and `src/ui/*`)

### Test Structure

```
tests/
├── test_*.py           # Unit tests for individual modules
├── analysis/           # Analysis module tests
├── api/               # API client tests
├── feedback/          # Recurrence detection tests
├── knowledge/         # Standards manager tests
├── visualization/      # Visualization tests
├── ui/                # Streamlit component tests (mock-based)
├── e2e/               # End-to-end tests (Playwright + real/simulated flows)
│   ├── cli/           # CLI command tests (fetch, analyze, report)
│   ├── pipeline/       # Phase1/Phase2 integration tests
│   ├── ui/            # Streamlit UI tests (requires playwright)
│   └── fixtures/      # Shared test fixtures
└── integration/       # Two-phase pipeline integration tests
```

### Running Tests

```bash
# All tests with coverage
pytest tests/ -v --cov=src

# Single test file
pytest tests/test_clustering.py -v

# E2E tests (excludes UI - requires playwright browser)
pytest tests/e2e/cli/ tests/e2e/pipeline/ -v

# E2E tests including UI (requires: pip install -e ".[e2e]" && playwright install chromium)
pytest tests/e2e/ -v

# Specific E2E category
python tests/e2e/run_e2e_tests.py --cli      # CLI tests only
python tests/e2e/run_e2e_tests.py --pipeline # Pipeline tests only
python tests/e2e/run_e2e_tests.py --ui       # UI tests only (headed mode)
```

### E2E Test Categories

| Category | Path | Description |
|----------|------|-------------|
| CLI | `tests/e2e/cli/` | Tests for `fetch`, `analyze`, `report` commands |
| Pipeline | `tests/e2e/pipeline/` | Phase1 (prepare) and Phase2 (analyze) integration |
| UI | `tests/e2e/ui/` | Streamlit app with real browser (Playwright) |

## Development Workflow

1. **Specification** — Edit `.speckit/specify.md`
2. **Planning** — Edit `.speckit/plan.md`
3. **Tasks** — Edit `.speckit/tasks.md`
4. **Implementation** — Follow TDD: write failing test → implement → refactor
5. **Analysis** — Edit `.speckit/analyze.md`
6. **Review** — Use `code-review-checklist.md` before committing

Quality gate before commits:
```bash
ruff check src/ tests/     # Linting
ruff format src/ tests/    # Formatting
mypy src/                  # Type checking
pytest tests/ -v --cov=src # Tests (coverage ≥ 79.9%)
```

## Known Issues

1. **Duplicate ClusteringResult** — `src/core/models.py` and `src/analysis/clustering.py` both define this type; they are not interchangeable.
2. **E2E Test Dependencies** — UI E2E tests require `pip install -e ".[e2e]"` and `playwright install chromium`.
3. **Pre-commit** — Requires API keys in environment variables for full validation.
4. **test_excel.py** — Requires `SQL缺陷分析结果.xlsx` in working directory; excluded from default test runs.

## Important Notes

- Never commit API keys or tokens to version control
- Use `.env` file for sensitive configuration
- The `APIConfig.api_key` field is set via `DEVCLOUD_TOKEN` environment variable
- Async tests run under `asyncio_mode = "auto"` — no `@pytest.mark.asyncio` needed
