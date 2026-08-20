import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest


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

    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "checkout", "-q", "-b", "chore/handoff"], cwd=repo, check=True)
    (repo / ".no-hooks").mkdir()
    subprocess.run(["git", "config", "core.hooksPath", ".no-hooks"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "test fixture"], cwd=repo, check=True)

    return subprocess.run(
        [bash, str(gate), "--pre-push"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
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
