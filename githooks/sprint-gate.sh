#!/usr/bin/env bash
# sprint-gate.sh — Sprint Flow Enforcement Gate
# Validates sprint state consistency before push.
#
# Usage:
#   bash sprint-gate.sh --pre-push
#
# Exit codes:
#   0 — PASS (sprint state is consistent or no sprint active)
#   1 — BLOCK (sprint state inconsistency detected)

set -euo pipefail

PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo ".")"
SPRINT_STATE_FILE="$PROJECT_ROOT/.sprint-state/sprint-state.json"
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"

# Cross-platform Python: actually run --version to detect Windows Store stubs
# `command -v python3` succeeds on Windows but points to a Store stub (exit 49)
PYTHON=""
for candidate in python3 python; do
  if "$candidate" --version >/dev/null 2>&1; then
    PYTHON="$candidate"
    break
  fi
done

if [ -z "$PYTHON" ]; then
  echo "❌ Gate MS: working python/python3 not found in PATH."
  exit 1
fi

# ── Parse arguments ──
MODE=""
for arg in "$@"; do
  case "$arg" in
    --pre-push) MODE="pre-push" ;;
  esac
done

if [ -z "$MODE" ]; then
  echo "Usage: sprint-gate.sh --pre-push"
  exit 1
fi

# ── If no sprint state file, pass (no active sprint) ──
if [ ! -f "$SPRINT_STATE_FILE" ]; then
  echo "✅ Gate MS: No active sprint. PASS."
  exit 0
fi

# ── Validate JSON is parseable ──
if ! "$PYTHON" -c "import json, sys; json.load(open(sys.argv[1]))" "$SPRINT_STATE_FILE" 2>/dev/null; then
  echo "❌ Gate MS: sprint-state.json is invalid JSON."
  exit 1
fi

# ── Extract sprint state fields ──
SPRINT_BRANCH=$("$PYTHON" -c "
import json, sys
d = json.load(open(sys.argv[1]))
print(d.get('isolation', {}).get('branch', ''))
" "$SPRINT_STATE_FILE")

SPRINT_STATUS=$("$PYTHON" -c "
import json, sys
d = json.load(open(sys.argv[1]))
print(d.get('status', ''))
" "$SPRINT_STATE_FILE")

SPRINT_PHASE=$("$PYTHON" -c "
import json, sys
d = json.load(open(sys.argv[1]))
print(d.get('phase', 0))
" "$SPRINT_STATE_FILE")

SPRINT_MERGED=$("$PYTHON" -c "
import json, sys
d = json.load(open(sys.argv[1]))
print(str(d.get('isolation', {}).get('merged', False)).lower())
" "$SPRINT_STATE_FILE")

PHASE_HISTORY_COUNT=$("$PYTHON" -c "
import json, sys
d = json.load(open(sys.argv[1]))
phases = d.get('phase_history', [])
completed = [p for p in phases if p.get('status') == 'completed']
print(len(completed))
" "$SPRINT_STATE_FILE")

# ── Pre-push checks ──
if [ "$MODE" = "pre-push" ]; then
  if [ "$SPRINT_MERGED" = "true" ]; then
    echo "✅ Gate MS: No active sprint; completed sprint is already merged. PASS."
    exit 0
  fi

  ERRORS=0

  # Check 1: Branch must match sprint isolation branch
  if [ -n "$SPRINT_BRANCH" ] && [ "$CURRENT_BRANCH" != "$SPRINT_BRANCH" ]; then
    echo "❌ Gate MS: Branch mismatch."
    echo "   Sprint branch: $SPRINT_BRANCH"
    echo "   Current branch: $CURRENT_BRANCH"
    echo "   Push must be from the sprint's isolation branch."
    ERRORS=$((ERRORS + 1))
  fi

  # Check 2: Sprint must have reached SHIP phase (phase >= 5) before push
  if [ "$SPRINT_PHASE" -lt 5 ] 2>/dev/null; then
    echo "⚠️  Gate MS: Sprint not yet at SHIP phase (current: $SPRINT_PHASE)."
    echo "   Pushing from an incomplete sprint may indicate premature push."
    # Warning only, not a block — the branch might be a hotfix
  fi

  # Check 3: At least BUILD phase (phase 3) must be completed
  if [ "$PHASE_HISTORY_COUNT" -lt 3 ] 2>/dev/null; then
    echo "⚠️  Gate MS: Only $PHASE_HISTORY_COUNT phases completed. Expected >= 3 (PREP+DESIGN+BUILD)."
  fi

  if [ "$ERRORS" -gt 0 ]; then
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "   ❌ GATE MS: SPRINT FLOW — PUSH BLOCKED"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Fix the sprint state issues above before pushing."
    exit 1
  fi

  echo "✅ Gate MS: Sprint Flow Enforcement — PASS (branch=$CURRENT_BRANCH, phase=$SPRINT_PHASE, completed=$PHASE_HISTORY_COUNT)"
  exit 0
fi
