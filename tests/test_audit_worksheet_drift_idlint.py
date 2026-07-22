"""TMX-DRIFT-IDLINT — ticket-ID integrity lint in `audit_worksheet_drift.py`.

Synthetic-fixture pattern per TMX-3060 / TMX-CORRECTIVE-20260511 (see
``tests/test_audit_worktree_clean.py``): build a temporary git repo with an
``origin/main`` remote, a `.context/loops/` directory and a synthetic
`.context/active_tasks.md` board, then invoke the real script as a subprocess.

Behaviours under test (all opt-in via ``--check-ids``):

  1. Duplicate-ID detection — the same TMX-id introduced as the first-cell ID
     of two different ticket-introduction table rows (header first cell
     ``Ticket``) is listed and makes the exit code non-zero.
  2. Recap tables (header first cell ``Loop``) are NOT introductions — a
     re-mention there is neither a duplicate nor an orphan.
  3. Orphan-ID listing — ids matched in prose / Notes cells with no table row
     anywhere in the file are listed ADVISORY ONLY (never affect exit code).
  4. Worksheet State headers matching ``[Done`` + qualifier + ``]`` (e.g.
     ``[Done, pending push]``, ``[Done — X]``) classify as a distinct
     DONE_STALE_QUALIFIER bucket instead of IN-FLIGHT noise.
  5. Default (flag-less) behaviour is unchanged — the advisory pre-commit
     hook's semantics are preserved.
  6. ``--check-ids`` with a missing board fails loud (exit 2), never silently
     passes (A3).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT = _REPO_ROOT / "scripts" / "audit_worksheet_drift.py"

# ---------------------------------------------------------------------------
# Synthetic fixtures
# ---------------------------------------------------------------------------

_BOARD_WITH_DUPLICATE = """# Synthetic board

## Epic one

| Ticket | Title | Owner | Status | Notes |
|---|---|---|---|---|
| TMX-9001 | File upload validation | Frontend | **[READY]** | first introduction |
| TMX-9002 | Segmenter skeleton | Pipeline | **[READY]** | spawned TMX-9100 for follow-up |

## Epic two

| Ticket | Title | Owner | Status | Notes |
|---|---|---|---|---|
| TMX-9001 | Playwright visual snapshot | Frontend | **[READY]** | UNRELATED ticket reusing the id |

Prose paragraph mentioning TMX-9100 again with no row of its own.
"""

_BOARD_WITH_RECAP = """# Synthetic board

| Ticket | Title | Owner | Status | Notes |
|---|---|---|---|---|
| TMX-9001 | File upload validation | Frontend | **[READY]** | the only introduction |

### Session recap

| Loop | Status | One-line |
|---|---|---|
| TMX-9001 | **[Done]** | recap re-mention, not an introduction |
"""

_WS_DONE_QUALIFIER = """# TMX-9200 — synthetic qualifier worksheet

**State**: `[Done, pending push]`
**Owner**: Platform
"""

_WS_DONE_EMDASH_QUALIFIER = """# TMX-9201 — synthetic em-dash qualifier worksheet

**State**: `[Done — built behind flag]`
**Owner**: Platform
"""

_WS_PARKED = """# TMX-9202 — synthetic parked worksheet

**State**: `[PARKED — needs schema migration]`
**Owner**: Platform
"""

_WS_WIP = """# TMX-9300 — synthetic in-flight worksheet

**State**: `[WIP]`
**Owner**: Platform
"""


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


def _make_repo(tmp_path: Path, board: str | None, worksheets: dict[str, str]) -> Path:
    """A temp git repo with origin/main, `.context/loops/`, and a board file.

    Commit subjects never start with a synthetic ticket id, so no worksheet
    resolves to a commit — default runs classify everything IN-FLIGHT and
    exit 0, isolating the --check-ids exit-code semantics under test.
    """
    remote = tmp_path / "remote.git"
    _run(["git", "init", "--bare", "--initial-branch=main", str(remote)], cwd=tmp_path)

    work = tmp_path / "work"
    work.mkdir()
    _run(["git", "init", "--initial-branch=main"], cwd=work)
    _run(["git", "remote", "add", "origin", str(remote)], cwd=work)
    _run(["git", "config", "user.email", "test@example.com"], cwd=work)
    _run(["git", "config", "user.name", "Test"], cwd=work)

    loops = work / ".context" / "loops"
    loops.mkdir(parents=True)
    for name, body in worksheets.items():
        (loops / name).write_text(body, encoding="utf-8")
    if board is not None:
        (work / ".context" / "active_tasks.md").write_text(board, encoding="utf-8")

    _run(["git", "add", ".context"], cwd=work)
    _run(["git", "commit", "-m", "synthetic board fixture"], cwd=work)
    _run(["git", "push", "origin", "main"], cwd=work)
    return work


@pytest.fixture
def duplicate_board_repo(tmp_path: Path) -> Path:
    return _make_repo(
        tmp_path,
        board=_BOARD_WITH_DUPLICATE,
        worksheets={"TMX-9300.md": _WS_WIP},
    )


@pytest.fixture
def recap_board_repo(tmp_path: Path) -> Path:
    return _make_repo(
        tmp_path,
        board=_BOARD_WITH_RECAP,
        worksheets={"TMX-9300.md": _WS_WIP},
    )


@pytest.fixture
def qualifier_repo(tmp_path: Path) -> Path:
    return _make_repo(
        tmp_path,
        board=_BOARD_WITH_RECAP,
        worksheets={
            "TMX-9200.md": _WS_DONE_QUALIFIER,
            "TMX-9201.md": _WS_DONE_EMDASH_QUALIFIER,
            "TMX-9202.md": _WS_PARKED,
            "TMX-9300.md": _WS_WIP,
        },
    )


# ---------------------------------------------------------------------------
# 1. Duplicate detection (fails under --check-ids)
# ---------------------------------------------------------------------------


def test_check_ids_flags_duplicate_intro_rows(duplicate_board_repo: Path) -> None:
    """Same id as two introduction-table rows -> listed + exit non-zero."""
    rc, stdout, stderr = _run(
        [
            sys.executable,
            str(_SCRIPT),
            "--root",
            str(duplicate_board_repo),
            "--check-ids",
        ],
        cwd=duplicate_board_repo,
    )
    assert rc == 1, (
        f"Expected exit 1 with duplicate listed; got rc={rc}\n"
        f"stdout: {stdout}\nstderr: {stderr}"
    )
    assert "Ticket-ID integrity" in stdout
    assert "TMX-9001" in stdout, f"duplicate id not listed:\n{stdout}"
    # Both introducing rows' 1-indexed line numbers must be reported.
    assert "lines 7, 14" in stdout, f"row line numbers missing:\n{stdout}"


def test_recap_table_row_is_not_a_duplicate(recap_board_repo: Path) -> None:
    """One Ticket-table row + one Loop-recap row -> NOT a duplicate; exit 0."""
    rc, stdout, stderr = _run(
        [sys.executable, str(_SCRIPT), "--root", str(recap_board_repo), "--check-ids"],
        cwd=recap_board_repo,
    )
    assert rc == 0, (
        f"Expected exit 0 (recap re-mention is not an introduction); got rc={rc}\n"
        f"stdout: {stdout}\nstderr: {stderr}"
    )
    assert "Ticket-ID integrity" in stdout
    # TMX-9001 must appear neither as duplicate nor as orphan.
    lint_section = stdout.split("Ticket-ID integrity", 1)[1]
    assert "TMX-9001" not in lint_section, f"false positive on recap row:\n{stdout}"


# ---------------------------------------------------------------------------
# 2. Orphans (advisory — never fail)
# ---------------------------------------------------------------------------


def test_check_ids_lists_orphans_advisory(recap_board_repo: Path) -> None:
    """Prose/Notes-only ids are listed but do not affect the exit code."""
    board = recap_board_repo / ".context" / "active_tasks.md"
    text = board.read_text(encoding="utf-8")
    text += "\nProse mention of TMX-9100 (spawned, never given a row).\n"
    board.write_text(text, encoding="utf-8")

    rc, stdout, stderr = _run(
        [sys.executable, str(_SCRIPT), "--root", str(recap_board_repo), "--check-ids"],
        cwd=recap_board_repo,
    )
    assert rc == 0, (
        f"Expected exit 0 (orphans are advisory); got rc={rc}\n"
        f"stdout: {stdout}\nstderr: {stderr}"
    )
    assert "TMX-9100" in stdout, f"orphan id not listed:\n{stdout}"


def test_orphan_in_notes_cell_of_another_row(duplicate_board_repo: Path) -> None:
    """An id mentioned only inside another ticket's Notes cell is an orphan."""
    rc, stdout, _stderr = _run(
        [
            sys.executable,
            str(_SCRIPT),
            "--root",
            str(duplicate_board_repo),
            "--check-ids",
        ],
        cwd=duplicate_board_repo,
    )
    # TMX-9100 appears in TMX-9002's Notes cell and in prose — no row of its own.
    assert "TMX-9100" in stdout, f"Notes-cell orphan not listed:\n{stdout}"
    # The duplicate (TMX-9001) fails the run, but the orphan section is present.
    assert rc == 1


# ---------------------------------------------------------------------------
# 3. DONE_STALE_QUALIFIER bucket
# ---------------------------------------------------------------------------


def test_check_ids_done_qualifier_bucket(qualifier_repo: Path) -> None:
    """`[Done, pending push]` / `[Done — X]` -> DONE_STALE_QUALIFIER, not IN-FLIGHT.

    `[PARKED — ...]` must stay OUT of the bucket, and the bucket must not
    affect the exit code (recap board has no duplicates -> exit 0).
    """
    rc, stdout, stderr = _run(
        [sys.executable, str(_SCRIPT), "--root", str(qualifier_repo), "--check-ids"],
        cwd=qualifier_repo,
    )
    assert rc == 0, (
        f"Expected exit 0 (qualifier bucket is advisory); got rc={rc}\n"
        f"stdout: {stdout}\nstderr: {stderr}"
    )
    assert "DONE_STALE_QUALIFIER" in stdout, (
        f"Expected DONE_STALE_QUALIFIER verdict under --check-ids; got rc={rc}\n"
        f"stdout: {stdout}"
    )
    lines = stdout.splitlines()
    ws_9200 = next(line for line in lines if "TMX-9200" in line)
    ws_9201 = next(line for line in lines if "TMX-9201" in line)
    ws_9202 = next(line for line in lines if "TMX-9202" in line)
    assert "DONE_STALE_QUALIFIER" in ws_9200, f"comma qualifier missed: {ws_9200}"
    assert "DONE_STALE_QUALIFIER" in ws_9201, f"em-dash qualifier missed: {ws_9201}"
    assert "DONE_STALE_QUALIFIER" not in ws_9202, f"PARKED wrongly bucketed: {ws_9202}"
    assert "IN-FLIGHT" in ws_9202, f"PARKED must stay IN-FLIGHT: {ws_9202}"


# ---------------------------------------------------------------------------
# 4. Default behaviour unchanged (the advisory hook's contract)
# ---------------------------------------------------------------------------


def test_default_run_has_no_id_section(qualifier_repo: Path) -> None:
    """Flag-less run: no lint section, no new verdict, qualifier -> IN-FLIGHT."""
    rc, stdout, stderr = _run(
        [sys.executable, str(_SCRIPT), "--root", str(qualifier_repo)],
        cwd=qualifier_repo,
    )
    assert rc == 0, f"Expected exit 0 on default run; got rc={rc}\n{stdout}\n{stderr}"
    assert "Ticket-ID integrity" not in stdout
    assert "DONE_STALE_QUALIFIER" not in stdout
    ws_9200 = next(line for line in stdout.splitlines() if "TMX-9200" in line)
    assert "IN-FLIGHT" in ws_9200, f"pre-existing classification changed: {ws_9200}"


# ---------------------------------------------------------------------------
# 5. Fail loud on a missing board (A3)
# ---------------------------------------------------------------------------


def test_check_ids_missing_board_fails_loud(tmp_path: Path) -> None:
    """--check-ids without .context/active_tasks.md -> exit 2 + explicit error."""
    repo = _make_repo(tmp_path, board=None, worksheets={"TMX-9300.md": _WS_WIP})
    rc, stdout, stderr = _run(
        [sys.executable, str(_SCRIPT), "--root", str(repo), "--check-ids"],
        cwd=repo,
    )
    assert rc == 2, f"Expected exit 2 on missing board; got rc={rc}\n{stdout}\n{stderr}"
    assert "active_tasks.md" in stderr, (
        f"Expected explicit missing-board error on stderr; got:\nstdout: {stdout}\n"
        f"stderr: {stderr}"
    )
