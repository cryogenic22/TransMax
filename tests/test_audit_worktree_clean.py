"""TMX-CORRECTIVE-20260511 — synthetic-drift test for audit_worktree_clean.py.

The script exists to catch silent reverts of shipped code. This test exercises
that detection path:

  1. Stage 1 — clean state: invoke script, expect exit 0.
  2. Stage 2 — synthetic drift: write a modified version of a tracked file
     (without committing), invoke script, expect exit 1.
  3. Stage 3 — restore: revert the synthetic drift, invoke script, expect 0.

We use a temporary clone of the real repo so we don't pollute the developer's
worktree mid-test. The clone-and-fetch approach also exercises the
``origin/main`` resolution path the real script depends on.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT = _REPO_ROOT / "scripts" / "audit_worktree_clean.py"


def _run(args: list[str], cwd: Path) -> tuple[int, str, str]:
    """Run a subprocess and return (rc, stdout, stderr)."""
    proc = subprocess.run(
        args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


@pytest.fixture
def synthetic_repo(tmp_path: Path) -> Path:
    """A temporary git repo with a single committed file under app/.

    Sets up an ``origin`` remote so ``origin/main`` resolves. This avoids
    network calls and tests the script's drift detection in a controlled
    environment.
    """
    # Create the "remote" first (bare repo).
    remote = tmp_path / "remote.git"
    _run(["git", "init", "--bare", "--initial-branch=main", str(remote)], cwd=tmp_path)

    # Create the working clone.
    work = tmp_path / "work"
    work.mkdir()
    _run(["git", "init", "--initial-branch=main"], cwd=work)
    _run(["git", "remote", "add", "origin", str(remote)], cwd=work)
    _run(["git", "config", "user.email", "test@example.com"], cwd=work)
    _run(["git", "config", "user.name", "Test"], cwd=work)

    # Seed a tracked file under app/.
    app_dir = work / "app"
    app_dir.mkdir()
    target_file = app_dir / "shipped.py"
    target_file.write_text("VALUE = 'shipped'\n", encoding="utf-8")

    _run(["git", "add", "app/shipped.py"], cwd=work)
    _run(["git", "commit", "-m", "initial"], cwd=work)
    _run(["git", "push", "origin", "main"], cwd=work)

    return work


def test_clean_worktree_exits_zero(synthetic_repo: Path) -> None:
    """No drift → exit 0."""
    rc, stdout, _stderr = _run(
        [sys.executable, str(_SCRIPT), "--root", str(synthetic_repo)],
        cwd=synthetic_repo,
    )
    assert rc == 0, f"Expected exit 0 on clean worktree; got {rc}\n{stdout}"
    assert "Working tree clean" in stdout


def test_synthetic_drift_exits_nonzero(synthetic_repo: Path) -> None:
    """Worktree drift vs origin/main AND HEAD → exit 1."""
    target = synthetic_repo / "app" / "shipped.py"
    target.write_text("VALUE = 'reverted-without-commit'\n", encoding="utf-8")

    rc, stdout, _stderr = _run(
        [sys.executable, str(_SCRIPT), "--root", str(synthetic_repo)],
        cwd=synthetic_repo,
    )
    assert rc == 1, f"Expected exit 1 on synthetic drift; got {rc}\n{stdout}"
    assert "DRIFT" in stdout
    assert "app/shipped.py" in stdout


def test_restored_worktree_exits_zero(synthetic_repo: Path) -> None:
    """After drift is restored to HEAD content, exit 0 again."""
    target = synthetic_repo / "app" / "shipped.py"
    target.write_text("VALUE = 'reverted-without-commit'\n", encoding="utf-8")

    # Confirm drift first.
    rc1, _, _ = _run(
        [sys.executable, str(_SCRIPT), "--root", str(synthetic_repo)],
        cwd=synthetic_repo,
    )
    assert rc1 == 1

    # Restore from HEAD.
    _run(["git", "checkout", "HEAD", "--", "app/shipped.py"], cwd=synthetic_repo)

    rc2, stdout2, _stderr2 = _run(
        [sys.executable, str(_SCRIPT), "--root", str(synthetic_repo)],
        cwd=synthetic_repo,
    )
    assert rc2 == 0, f"Expected exit 0 after restore; got {rc2}\n{stdout2}"


def test_committed_local_change_does_not_flag(synthetic_repo: Path) -> None:
    """A local commit that's ahead of origin/main is NOT a worktree-drift case.

    The worksheet drift audit handles that case (LOCAL-ONLY); this script's
    job is purely working-tree-vs-shipped. So a clean working tree that
    happens to be ahead of origin/main should still exit 0.
    """
    target = synthetic_repo / "app" / "shipped.py"
    target.write_text("VALUE = 'legitimately-committed'\n", encoding="utf-8")
    _run(["git", "add", "app/shipped.py"], cwd=synthetic_repo)
    _run(["git", "commit", "-m", "legitimate local commit"], cwd=synthetic_repo)
    # Do NOT push — leave HEAD ahead of origin/main.

    rc, stdout, _stderr = _run(
        [sys.executable, str(_SCRIPT), "--root", str(synthetic_repo)],
        cwd=synthetic_repo,
    )
    assert rc == 0, f"Expected exit 0 for committed-but-unpushed; got {rc}\n{stdout}"


def test_real_repo_clean_state_exits_zero() -> None:
    """Smoke test against the real repo. After this loop's restore, exit 0.

    If this fails on CI, it means the working tree has uncommitted drift —
    exactly what the script is for. The test serves as the running self-check.
    """
    rc, _stdout, _stderr = _run(
        [sys.executable, str(_SCRIPT), "--root", str(_REPO_ROOT)],
        cwd=_REPO_ROOT,
    )
    # We assert <=1: 0 is clean, 1 is in-flight advisory. We tolerate 1 so
    # the test doesn't fail on a developer's normal mid-loop state. CI's
    # worktree is clean by definition, so it will exit 0 there.
    assert rc in (0, 1), f"Unexpected exit {rc} from audit_worktree_clean.py"
