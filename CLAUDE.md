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
- All data models use **Pydantic v2** (`model_config = ConfigDict(...)` style).
- The CLI uses `asyncio.run()` inside synchronous Typer commands (see `fetch.py`). Do not call these commands from an already-running event loop.

### Configuration

`config.yaml` at repo root is loaded by `ConfigManager`. Environment variable overrides use plain uppercase keys (no project prefix), e.g.:

```
LLM_MODEL=gpt-3.5-turbo
API_BASE_URL=https://...
EMBEDDING_API_KEY=sk-...
```

Full mapping is in `src/config/manager.py:_env_prefix_map`. The `APIConfig.api_key` field holds the external REST API token; set it via `API_API_KEY` or `API_TOKEN` environment variables.

Key config sections:

| Section | Purpose |
|---|---|
| `api.base_url` | External research-management system API endpoint |
| `llm.model` | GPT model for the future reasoning stage |
| `embedding.model` | OpenAI embedding model (`text-embedding-3-small` default) |
| `clustering.min_cluster_size` | HDBSCAN minimum cluster size (default 5) |
| `clustering.metric` | Distance metric, default `cosine` in config but `euclidean` in `ClusterAnalyzer` constructor — pass explicitly |
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

- **`src/embedding/generator.py:71`** — `_embed_batch_internal` still has dead-code silent replacement (`else " "`). Functionally safe because `embed_batch` validates empty texts upstream before calling this method. Minor code-cleanliness issue only.

## Testing

Tests live in `tests/`. Coverage threshold is 80% (`fail_under` in `pyproject.toml`). `tests/conftest.py` provides shared fixtures. All async tests run under `asyncio_mode = "auto"` — no `@pytest.mark.asyncio` needed on individual tests. CLI commands have no test coverage.
