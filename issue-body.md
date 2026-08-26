## Bug Description

On Windows (MINGW/MSYS git bash), Node.js cannot read `/dev/stdin`, causing **all lint baseline comparison logic in pre-commit hook to silently fail**. Additionally, Gate M-Python (mutation testing) is always skipped due to incomplete mutmut detection and missing fallback.

## Impact

- **Gate 1 (Code Quality)**: Ruff/ESLint/ShellCheck baseline comparisons silently fail — new lint errors are never caught by pre-commit
- **Gate M-Python (Mutation Testing)**: Always SKIPs on environments where `mutmut` CLI is not in PATH but is installed as a Python module

## Root Cause

### Issue 1: `/dev/stdin` Windows incompatibility
The pre-commit hook uses `readFileSync('/dev/stdin', 'utf8')` in 10 inline Node.js scripts. On Windows git bash (MINGW/MSYS), `/dev/stdin` does not exist as a file that Node.js can open, causing `ENOENT` errors that are silently swallowed by the `$()` subshell.

Affected tools: ESLint, Ruff (Python), Shellcheck — both baseline comparison and no-baseline error display paths.

### Issue 2: `detect_python_mutation_testable` incomplete detection
The function only checks `command -v mutmut` but not `python3 -m mutmut`. When mutmut is pip-installed but its CLI entry point is not in PATH (common in venv/WSL setups), the detection fails.

### Issue 3: Gate M-Python requires `src/mutation/gate-m.ts`
When the TypeScript orchestrator doesn't exist in the target project, Gate M-Python skips entirely instead of falling back to direct `mutmut run`.

## Fix

### Fix 1: Replace `/dev/stdin` with temp file + `process.argv[1]`
Cross-platform approach: write stdin data to a temp file, pass file path via `process.argv[1]` to Node.js.

### Fix 2: Add `python3 -m mutmut` fallback to detection

### Fix 3: Gate M-Python direct mutmut fallback when `gate-m.ts` is absent

## Files Changed

- `githooks/pre-commit` — 10 `/dev/stdin` replacements
- `src/npm-package/hooks/pre-commit` — 10 `/dev/stdin` replacements
- `githooks/adapter-common.sh` + 2 copies — mutmut detection enhancement
- `githooks/pre-push` + 1 copy — Gate M-Python fallback

## Environment

- OS: Windows 11 (MINGW/MSYS via Git Bash)
- Node.js: v26.x, Python: 3.12
