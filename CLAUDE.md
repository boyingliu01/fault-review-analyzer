# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Fault Review Analyzer (故障复盘分析工具)** — An AI-driven pipeline that clusters similar bugs/incidents and discovers root causes without pre-defined labels. It fetches task data from an external REST API, preprocesses text, generates vector embeddings via OpenAI, and applies HDBSCAN density-based clustering.

## Development Commands

```bash
# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Run all tests with coverage
pytest tests/ -v --cov=src

# Run a single test file
pytest tests/test_clustering.py -v

# Linting and formatting
ruff check src/ tests/
ruff format src/ tests/

# Type checking
mypy src/
```

The CLI entry point after install:
```bash
fault-analyzer --help
```

## Architecture

Data flows through a four-stage pipeline:

1. **Fetch** (`src/api/`, `src/cache/`) — `APIClient` (async context manager) fetches task/bug records from a REST API and persists them in SQLite cache with TTL via `CacheManager`.
2. **Preprocess** (`src/preprocessor/`) — `DataPreprocessor` extracts text segments from all task fields (title, description, commits, logs, stack traces) and combines them into a single string per task (max 8000 chars).
3. **Embed** (`src/embedding/`) — `EmbeddingGenerator` calls OpenAI's `text-embedding-3-small` API in batches, returning 1536-dim vectors.
4. **Cluster** (`src/clustering/`) — `ClusterAnalyzer` runs HDBSCAN on the embedding matrix and emits `ClusterResult` with labels, noise indices, and centroids. Quality metrics (silhouette, Calinski-Harabasz) are computed separately via `compute_cluster_quality()`.

**Stages 5+ (labeling, reasoning, report) are not yet implemented.** The `analyze` and `report` CLI commands are stub functions that print a placeholder message and return immediately.

### Module Layout Notes

- **`src/cli/`** — Typer-based CLI. `fetch single` is the only command with real implementation. `analyze`, `report` are stubs.
- **`src/analyzer/`** — Contains only empty `__init__.py` files. This is the planned home for the `labeling` and `reasoning` stages. Do not confuse with the already-implemented `src/clustering/`, `src/embedding/`, `src/preprocessor/` directories which are separate from `src/analyzer/`.
- **`src/report/`** and **`src/rules/`** — Scaffolded but empty.
- All data models use **Pydantic v2** except `ClusterInfo` and `DimensionReductionResult` in `src/clustering/models.py` which still use the v1 `class Config` inner-class style — this is a known inconsistency.
- The CLI uses `asyncio.run()` inside synchronous Typer commands (see `fetch.py`). Do not call these commands from an already-running event loop.

### Configuration

`config.yaml` at repo root is loaded by `ConfigManager`. Environment variable overrides use plain uppercase keys (no project prefix), e.g.:

```
LLM_MODEL=gpt-3.5-turbo
API_BASE_URL=https://...
EMBEDDING_API_KEY=sk-...
```

Full mapping is in `src/config/manager.py:_env_prefix_map`. The `APIConfig` section has no `api_key` field — the token for the external REST API must be supplied separately (currently the code incorrectly reads `config.llm.api_key` for this; see known issues).

Key config sections:

| Section | Purpose |
|---|---|
| `api.base_url` | External research-management system API endpoint |
| `llm.model` | GPT model for the future reasoning stage |
| `embedding.model` | OpenAI embedding model (`text-embedding-3-small` default) |
| `clustering.min_cluster_size` | HDBSCAN minimum cluster size (default 5) |
| `clustering.metric` | Distance metric, default `cosine` in config but `euclidean` in `ClusterAnalyzer` constructor — pass explicitly |
| `cache.ttl` | SQLite cache TTL in seconds (default 86400) |

## Code Review

A full code review report is at `review/code_review.md`. It covers:
- Completion status of all modules (implemented vs. stub)
- 10 bugs with exact file locations, problem descriptions, and fix instructions (P0–P3)
- Architecture items yet to be built (pipeline orchestration, labeling, reasoning, report generation, rules engine)
- Unused dependencies and test coverage gaps

## Known Issues to Be Aware Of

- **`src/api/client.py:170`** — `_parse_datetime(None)` raises `ValueError`, but `resolve_time` is `Optional[datetime]`. Any task without a `resolveTime` field in the API response (i.e., all open/unresolved bugs) will crash during `get_task()`. Fix: return `None` for empty/None input instead of raising.
- **`src/embedding/generator.py:67`** — `_embed_batch_internal` still silently replaces empty text with `" "` while `embed_text` now raises. Inconsistent; safe in practice because `process_batch` filters empty texts upstream.
- **`tests/conftest.py:63`** — `sample_task_data` commit dict is missing the `time` field; `CommitInfo.time` is required. Safe for current tests but will break if `_parse_commit` is called with this fixture data.
- **`tests/test_preprocessor.py:20`** — `preprocessor` and `sample_task` fixtures are defined both inside `TestDataPreprocessor` and in `conftest.py` (identical content). The class-level versions are redundant and should be removed.

## Testing

Tests live in `tests/`. Coverage threshold is 80% (`fail_under` in `pyproject.toml`). `tests/conftest.py` provides shared fixtures. All async tests run under `asyncio_mode = "auto"` — no `@pytest.mark.asyncio` needed on individual tests. CLI commands have no test coverage.
