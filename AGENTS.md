# Repository Guidelines

## Project Structure & Modules
- `src/`: core code. Key packages: `cli/` (Typer entrypoint `fault-analyzer`), `api/` (remote fetch), `analyzer/` (HDBSCAN/UMAP clustering), `report/` (Jinja2/Rich output), `rules/` (policy engine), `config/` (Pydantic settings), `utils/` helpers.
- `tests/`: pytest suites mirroring `src` packages; async tests enabled.
- `data/`: cached datasets and rule definitions; keep raw inputs out of git when possible.
- `output/`: generated reports; safe to clean.
- `docs/` & `review/`: reference material, analyses, and reports.

## Setup & Environment
- Python >=3.10. Create venv, then `pip install -e ".[dev]"`.
- Copy `.env.example` to `.env`; set `API_BASE_URL`, `LLM_PROVIDER`, `LLM_API_KEY`, `EMBEDDING_PROVIDER` before hitting remote services.

## Build, Test, and Development Commands
- `fault-analyzer --help` — list CLI actions; common: `fetch --task-id <id>`, `analyze --task-id <id>`, `report --task-id <id> --output ./output`.
- `pytest -v --cov=src` — run unit tests with coverage (threshold 80% via config).
- `ruff check src/ tests/` — static lint; `ruff format src/ tests/` for formatting.
- `mypy src/` — type checks against `pyproject.toml` settings.
- `pre-commit run --all-files` — run full hook suite before commits.

## Coding Style & Naming Conventions
- 4-space indentation, max line length 100 (enforced by Ruff formatter).
- Modules/files use `snake_case.py`; classes `PascalCase`; functions/vars `snake_case`; constants `UPPER_SNAKE`.
- Prefer `pathlib.Path` over `os.path`; log via `loguru`.
- Keep CLI commands in Typer apps; pure logic in services under `analyzer/` or `api/` to stay testable.

## Testing Guidelines
- Place tests under `tests/<package>/` mirroring source; name files `test_*.py` and functions `test_*`.
- For async flows, rely on `pytest-asyncio`; avoid real network—mock HTTPX and LLM calls.
- Maintain coverage >=80%; add focused fixtures for sample task payloads in `tests/data` if new cases appear.

## Commit & Pull Request Guidelines
- Use Conventional Commit prefixes (`feat`, `fix`, `chore`, `test`, `docs`, etc.); include concise scope when helpful (e.g., `feat(api): add retry backoff`).
- Keep commits small and reviewable; ensure hooks pass before push.
- PRs should describe intent, list major changes, reference task/issue IDs, and include test evidence (`pytest` output or coverage delta). Attach screenshots or sample report snippets when UI/report output changes.

## Security & Data Handling
- Never commit real API keys or production incident data; use sanitized fixtures in `data/`.
- Scrub generated `output/` before sharing externally; prefer redacted examples.
