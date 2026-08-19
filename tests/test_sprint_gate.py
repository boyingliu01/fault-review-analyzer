import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


def test_merged_sprint_does_not_block_new_branch(tmp_path: Path) -> None:
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
    (state_dir / "sprint-state.json").write_text(
        json.dumps(
            {
                "isolation": {"branch": "master", "merged": True},
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

    result = subprocess.run(
        [bash, str(gate), "--pre-push"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "completed sprint" in result.stdout
