# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Fault Review Analyzer (故障复盘分析工具)** — An AI-driven pipeline that clusters similar bugs/incidents and discovers root causes without pre-defined labels. It fetches task data from an external REST API, preprocesses text, generates vector embeddings via OpenAI, and applies HDBSCAN density-based clustering, followed by LLM-based labeling and root cause analysis.

## Development Commands

```bash
# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks (required once after clone)
pre-commit install

# Copy environment template and fill in keys before running against remote services
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

# Run full pre-commit hook suite (before commits)
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

Run the two-phase batch scripts directly (no install required):
```bash
python scripts/phase1_prepare.py   # Fetch + preprocess + embed → stores to ChromaDB
python scripts/phase2_analyze.py   # Cluster + label + root-cause analysis
```

## Architecture

Data flows through a five-stage pipeline orchestrated by `src/analyzer/pipeline.py` (`AnalysisPipeline`):

1. **Fetch** (`src/api/`, `src/cache/`) — `APIClient` (async context manager, httpx) fetches task/bug records from a REST API and persists them in SQLite cache with TTL via `CacheManager`.
2. **Preprocess** (`src/preprocessor/`) — `DataPreprocessor` extracts text segments from all task fields (title, description, commits, logs, stack traces) and combines them into a single string per task (max 8000 chars).
3. **Embed** (`src/embedding/`) — `EmbeddingGenerator` supports multiple providers (OpenAI, Zhipu, Volcengine, local sentence-transformers) in async batches. Default: `text-embedding-3-small` → 1536-dim; local → 1024-dim.
4. **Cluster** (`src/clustering/`) — `ClusterAnalyzer` runs HDBSCAN on the embedding matrix and emits `ClusterResult` with labels, noise indices, and centroids. Falls back to sklearn if HDBSCAN is unavailable. Quality metrics (silhouette, Calinski-Harabasz) are computed separately via `compute_cluster_quality()`.
5. **Analyze** (`src/analyzer/labeling/`, `src/analyzer/reasoning/`, `src/analysis/`) — `LabelGenerator` assigns categories via LLM; `RootCauseAnalyzer` produces structured root cause analysis; `ViolationDetector` applies rule-based checks against the standards knowledge base; `RootCauseValidator` scores actionability.

`AnalysisPipeline` uses lazy initialization — components are created on first use via `_get_*()` methods.

### Module Layout Notes

- **`src/cli/`** — Typer-based CLI. `fetch` commands are fully implemented. `analyze` and `report` commands call `AnalysisPipeline` / `ReportGenerator` but have sparse test coverage.
- **`src/core/models.py`** — **V4 shared models** used across the analysis layer: `StandardRule`, `CodeChange`, `ViolationDetection`, `RootCauseValidation`, `LLMAnalysisResult`, `ClusteringResult`. Distinct from V1 models in `src/api/models.py`.
- **`src/analyzer/`** — Fully implemented: `pipeline.py` (orchestration), `labeling/generator.py`, `reasoning/generator.py`.
- **`src/analysis/`** — V4 violation detection (`ViolationDetector`) and root cause validation (`RootCauseValidator`).
- **`src/knowledge/`** — `StandardsManager`: loads development standards from JSON files (globbing `*_standards.json`), supports search by keyword/level/subcategory. Default data dir: `data/standards/mock/` (4 mock files: Java, DB, C++, ops) — temporary until T1a (PDF spec parsing) is implemented. Tests in `tests/knowledge/`.
- **`src/report/`** and **`src/rules/`** — Scaffolded with skeleton implementations; not production-ready.
- **`src/storage/`** — `ChromaManager`: wraps ChromaDB (`PersistentClient`) for vector storage at `./data/chroma`. Accepts `EmbeddingResult` objects (from `src/core/models.py`); supports `add_embedding`, `add_batch_embeddings`, `query_similar`, and `get_by_task_id`. Default collection: `fault_embeddings`.
- **`src/visualization/`** — `ClusterScatterVisualizer` (`cluster_scatter.py`) renders 2-D cluster scatter plots; `DashboardGenerator` (`charts.py`) builds root-cause distribution bar charts, violation-type charts, and improvement-tracking charts using Plotly.
- **`src/analysis/clustering.py`** — Stand-alone `ClusteringAnalyzer` that wraps HDBSCAN, KMeans, and AgglomerativeClustering. Returns a local `ClusteringResult` dataclass (distinct from `src/core/models.py:ClusteringResult`).
- **`src/analysis/improvement_recommender.py`** — `ImprovementRecommender`: maps high-frequency root causes to templated `ImprovementMeasure` objects with priority, category, and acceptance criteria.
- **`src/analysis/enhanced_llm_analyzer.py`** — `EnhancedLLMAnalyzer`: composes `ViolationDetector`, `CodeChangeAnalyzer`, and `RootCauseValidator` into a single unified analysis step.
- **`src/ui/streamlit_app.py`** — `FaultAnalysisUI`: Streamlit dashboard integrating `ChromaManager`, `ClusteringAnalyzer`, `ImprovementRecommender`, and `DashboardGenerator`. Run with:
  ```bash
  streamlit run src/ui/streamlit_app.py
  ```
- All data models use **Pydantic v2** (`model_config = ConfigDict(...)` style).
- The CLI uses `asyncio.run()` inside synchronous Typer commands (see `fetch.py`). Do not call these commands from an already-running event loop.

### Coding Conventions

- Max line length: **100** (enforced by Ruff formatter).
- Logging: use **`loguru`** (`from loguru import logger`), not stdlib `logging`.
- File paths: prefer **`pathlib.Path`** over `os.path`.
- Keep CLI commands (Typer) thin; business logic lives in `analyzer/` or `api/` service classes to stay testable.
- Commit messages follow **Conventional Commits**: `feat(scope): …`, `fix`, `chore`, `test`, `docs`, etc.

### Configuration

`config/config.yaml` is loaded by `ConfigManager`. Copy `.env.example` to `.env` and set credentials there — the env vars override the YAML. Plain uppercase keys (no project prefix), e.g.:

```
LLM_PROVIDER=volcengine
LLM_MODEL=doubao-seed-1-8-251228
LLM_API_KEY=...
LLM_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
EMBEDDING_PROVIDER=volcengine
EMBEDDING_MODEL=doubao-embedding-vision-251215
API_BASE_URL=https://...
```

The active default provider in `config/config.yaml` is **Volcengine** (Doubao LLM + embedding), not OpenAI. Full env var mapping is in `src/config/manager.py:_env_prefix_map`. The `APIConfig.api_key` field holds the external REST API token; set it via `API_API_KEY` or `API_TOKEN`.

Key config sections:

| Section | Purpose |
|---|---|
| `api.base_url` | External research-management system API endpoint |
| `llm.provider` / `llm.model` | LLM provider and model for the reasoning stage |
| `embedding.provider` / `embedding.model` | Embedding provider and model |
| `clustering.min_cluster_size` | HDBSCAN minimum cluster size (default 2 in config) |
| `clustering.metric` | Distance metric — `cosine` in config; verify it propagates to `ClusterAnalyzer` constructor |
| `cache.ttl` | SQLite cache TTL in seconds (default 86400) |

## Development Workflow (SDD)

New features must follow the Specification-Driven Development (SDD) process:

1. **Specify** — Edit `.speckit/specify.md`: describe WHAT the feature does (not HOW)
2. **Plan** — Edit `.speckit/plan.md`: design the technical approach
3. **Tasks** — Edit `.speckit/tasks.md`: break down into actionable implementation steps
4. **Implement** — Follow TDD: write failing test → implement → refactor
5. **Analyze** — Edit `.speckit/analyze.md`: verify consistency across docs
6. **Review** — Use `code-review-checklist.md` before committing

Quality gate before every commit:
```bash
ruff check src/ tests/     # Linting
ruff format src/ tests/    # Formatting
mypy src/                  # Type checking
pytest tests/ -v --cov=src # Tests (coverage ≥ 80%)
```

## Code Review

A full code review report is at `review/code_review.md` (updated through 4 rounds of review). A general-purpose code review checklist is at `code-review-checklist.md`.

## Known Issues to Be Aware Of

- **`src/embedding/generator.py:71`** — `_embed_batch_internal` has dead-code silent replacement (`else " "`). Functionally safe because `embed_batch` validates empty texts upstream before calling this method.
- **`src/core/models.py` `EmbeddingResult`** — Declared as 2048-dim (multimodal design target) but `EmbeddingGenerator` currently produces 1536-dim (OpenAI) or 1024-dim (local). These are different objects: `EmbeddingResult` is the V4 planned model; `EmbeddingGenerator` returns raw `list[list[float]]` directly.
- **Duplicate `ClusteringResult`** — `src/core/models.py` and `src/analysis/clustering.py` both define a `ClusteringResult` type. They are not interchangeable: the `core` version is the V4 Pydantic model; the `analysis` version is a plain dataclass used by `ClusteringAnalyzer`.

## Testing

Tests live in `tests/`. Coverage threshold is ~80% (`fail_under = 79.9` in `pyproject.toml`). `tests/conftest.py` provides shared fixtures. All async tests run under `asyncio_mode = "auto"` — no `@pytest.mark.asyncio` needed on individual tests. CLI commands are excluded from coverage (`src/cli/*` omitted in config). Mock external calls (HTTPX, LLM APIs) — do not make real network requests in tests.

Sub-directories with their own `conftest.py` and targeted fixtures:

| Directory | What it tests |
|---|---|
| `tests/analysis/` | `ViolationDetector`, `RootCauseValidator`, `CodeChangeAnalyzer`, `EnhancedLLMAnalyzer`, `ImprovementRecommender`, `ClusteringAnalyzer` |
| `tests/storage/` | `ChromaManager` |
| `tests/knowledge/` | `StandardsManager` |
| `tests/visualization/` | `ClusterScatterVisualizer`, `DashboardGenerator` |
| `tests/ui/` | `FaultAnalysisUI` (Streamlit app) |
| `tests/integration/` | Two-phase pipeline integration (`test_phase1_phase2.py`) |
| `tests/clustering/` | Extended `ClusterAnalyzer` tests |
| `tests/embedding/` | Extended `EmbeddingGenerator` tests |
| `tests/api/` | Extended `APIClient` tests |