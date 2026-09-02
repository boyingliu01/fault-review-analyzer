import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest


def _clean_git_env() -> dict[str, str]:
    """剔除父进程 GIT_* 变量（pre-commit 等 git hook 环境会设置 GIT_DIR 等），
    避免 tmp repo 的 git 子进程操作被重定向到外层仓库。"""
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def _run_gate(
    tmp_path: Path,
    merged: Any,
    branch: str = "master",
    include_merged: bool = True,
) -> subprocess.CompletedProcess[str]:
    git_bash = Path(os.environ.get("PROGRAMFILES", "")) / "Git" / "bin" / "bash.exe"
    bash = str(git_bash) if git_bash.exists() else shutil.which("bash")
    if bash is None:
        pytest.skip("bash is required for sprint gate tests")

    env = _clean_git_env()

    repo = tmp_path / "repo"
    state_dir = repo / ".sprint-state"
    hooks_dir = repo / "githooks"
    state_dir.mkdir(parents=True)
    hooks_dir.mkdir()

    source_gate = Path(__file__).parents[1] / "githooks" / "sprint-gate.sh"
    gate = hooks_dir / "sprint-gate.sh"
    gate.write_text(source_gate.read_text(encoding="utf-8"), encoding="utf-8")
    isolation: dict[str, Any] = {"branch": branch}
    if include_merged:
        isolation["merged"] = merged

    (state_dir / "sprint-state.json").write_text(
        json.dumps(
            {
                "isolation": isolation,
                "phase": 6,
                "status": "user_acceptance_pending",
                "phase_history": [],
            }
        ),
        encoding="utf-8",
    )

    (repo / ".no-hooks").mkdir()
    setup_commands: list[list[str]] = [
        ["git", "init", "-q"],
        ["git", "checkout", "-q", "-b", "chore/handoff"],
        ["git", "config", "core.hooksPath", ".no-hooks"],
        ["git", "config", "user.email", "test@example.com"],
        ["git", "config", "user.name", "Test"],
        ["git", "add", "."],
        ["git", "commit", "-q", "-m", "test fixture"],
    ]
    for cmd in setup_commands:
        subprocess.run(cmd, cwd=repo, check=True, env=env)

    return subprocess.run(
        [bash, str(gate), "--pre-push"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def test_merged_sprint_does_not_block_new_branch(tmp_path: Path) -> None:
    result = _run_gate(tmp_path, True)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "completed sprint" in result.stdout


@pytest.mark.parametrize("merged", [False, "true", "false", "TRUE", 1, 0, None, [], {}])
def test_non_true_merged_values_do_not_bypass_branch_mismatch(tmp_path: Path, merged: Any) -> None:
    result = _run_gate(tmp_path, merged)

    assert result.returncode != 0
    assert "completed sprint" not in result.stdout


def test_missing_merged_does_not_bypass_branch_mismatch(tmp_path: Path) -> None:
    result = _run_gate(tmp_path, None, include_merged=False)

    assert result.returncode != 0
    assert "completed sprint" not in result.stdout


def test_matching_branch_with_unmerged_sprint_passes(tmp_path: Path) -> None:
    result = _run_gate(tmp_path, False, branch="chore/handoff")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS" in result.stdout


def test_legacy_state_without_merged_passes_on_matching_branch(tmp_path: Path) -> None:
    result = _run_gate(tmp_path, None, branch="chore/handoff", include_merged=False)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS" in result.stdout
