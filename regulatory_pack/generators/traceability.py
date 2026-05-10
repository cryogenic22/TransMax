"""Regulatory-pack traceability harness (TMX-3500).

Walks `.context/loops/`, `tests/`, and `git log` to produce a matrix of
`(ticket_id, ac_id, test_function, test_file, commit_sha, status)` rows.

The harness has ONE responsibility: read evidence, build matrix. It does NOT
format markdown for the documents (that's `pack_builder.py`), does NOT
verify test passes/fails (that's OQ test-results, sourced from pytest
output by the pack builder).

Status values:
  OK              - test_function and commit_sha both populated
  NO_TEST         - commit_sha populated, no test_function found
  NO_COMMIT       - test_function populated, no commit_sha found
  PLANNING_ONLY   - worksheet declared "no code change" / "Stage 5: N/A"
  UNVERIFIED      - missing context (e.g. no git, malformed worksheet)

This module is stdlib-only. No third-party dependencies.
"""

from __future__ import annotations

import logging
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

# Reach the shared worksheet parser. `scripts/` is a sibling of
# `regulatory_pack/`; we add it to sys.path defensively in case the package
# is invoked from outside the repo root.
_REPO_ROOT_CANDIDATE = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT_CANDIDATE / "scripts"
if _SCRIPTS_DIR.is_dir() and str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from _worksheet_parser import (  # noqa: E402  (after sys.path manipulation)
    Worksheet,
    extract_acceptance_criteria,
    iter_worksheets,
)

logger = logging.getLogger(__name__)

Status = Literal["OK", "NO_TEST", "NO_COMMIT", "PLANNING_ONLY", "UNVERIFIED"]

# Match a ticket id at the start of a docstring or comment within a test
# file. Captures TMX-3045, TMX-3702-a11y, TMX-LOOP-HYGIENE etc.
TICKET_ID_IN_TEST_RE = re.compile(
    r"\b(TMX-[A-Z0-9-]+?[A-Z0-9])\b",
    re.IGNORECASE,
)

# Match a `def test_<name>` definition; captures the test name.
TEST_DEF_RE = re.compile(r"^\s*def\s+(test_[A-Za-z0-9_]+)\s*\(", re.MULTILINE)


@dataclass(frozen=True)
class TraceabilityRow:
    """One row of the per-ticket / per-AC traceability matrix."""

    ticket_id: str
    ac_id: str  # "AC-1" / "AC-2" / "AC-N/A" if no AC declared
    test_function: Optional[str]  # function name; None if no match
    test_file: Optional[str]  # path relative to repo root
    commit_sha: Optional[str]  # 7-12 char hex
    status: Status
    note: str = ""  # short human reason, particularly for UNVERIFIED


@dataclass
class TraceabilityMatrix:
    """A collection of TraceabilityRow plus rendering helpers."""

    rows: list[TraceabilityRow] = field(default_factory=list)
    repo_root: Path = field(default_factory=Path)
    generated_at: str = ""  # UTC ISO timestamp; set by builder

    def to_markdown_table(self) -> str:
        """Render the matrix as a GitHub-flavoured markdown table."""
        header = "| Ticket | AC | Test | Commit | Status | Note |"
        sep = "|---|---|---|---|---|---|"
        lines = [header, sep]
        for row in self.rows:
            test_cell = (
                f"`{row.test_function}` (`{row.test_file}`)"
                if row.test_function
                else "-"
            )
            commit_cell = f"`{row.commit_sha[:10]}`" if row.commit_sha else "-"
            note_cell = row.note if row.note else ""
            lines.append(
                f"| `{row.ticket_id}` | {row.ac_id} | {test_cell} | "
                f"{commit_cell} | **{row.status}** | {note_cell} |"
            )
        return "\n".join(lines)

    def summary(self) -> dict[str, int]:
        """Count rows per status."""
        out: dict[str, int] = {}
        for row in self.rows:
            out[row.status] = out.get(row.status, 0) + 1
        out["TOTAL"] = len(self.rows)
        return out


def _run_git(args: list[str], cwd: Path) -> tuple[int, str]:
    """Run a git subcommand and return (exit_code, stdout)."""
    try:
        proc = subprocess.run(  # noqa: S603 - args are a static list
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except (OSError, FileNotFoundError) as exc:  # pragma: no cover
        logger.debug("git invocation failed: %s", exc)
        return 1, ""
    return proc.returncode, proc.stdout


def _find_commit_for_ticket(
    ticket_id: str,
    repo_root: Path,
    declared_shas: list[str],
) -> Optional[str]:
    """Find an oldest-first commit on any ref whose subject starts with
    ticket_id. Honour worksheet-declared SHAs first.

    Mirrors the resolution logic in `scripts/audit_worksheet_drift.py` so
    the matrix and the drift audit agree on which commit a ticket maps to.
    """
    code, out = _run_git(
        ["log", "--all", "--reverse", "--pretty=format:%H %s"],
        repo_root,
    )
    if code != 0 or not out.strip():
        return None

    sha_lines = [line.partition(" ") for line in out.splitlines()]

    # 1. Honour any worksheet-declared SHAs.
    for declared in declared_shas:
        for sha, _, _subject in sha_lines:
            if sha.lower().startswith(declared.lower()):
                return sha

    # 2. Anchor to subject start.
    pattern = re.compile(rf"^{re.escape(ticket_id)}[:\s]")
    for sha, _, subject in sha_lines:
        if pattern.match(subject):
            return sha

    # 3. Variant suffix.
    pattern = re.compile(rf"^{re.escape(ticket_id)}-v\d+[:\s]")
    for sha, _, subject in sha_lines:
        if pattern.match(subject):
            return sha

    # 4. Prefix degradation for compound ids ("TMX-3200-3201" -> "TMX-3200").
    parts = ticket_id.split("-")
    while len(parts) > 2:
        parts = parts[:-1]
        prefix = "-".join(parts)
        pattern = re.compile(rf"^{re.escape(prefix)}[:\s]")
        for sha, _, subject in sha_lines:
            if pattern.match(subject):
                return sha

    return None


def _index_tests_by_ticket(tests_root: Path) -> dict[str, list[tuple[str, str]]]:
    """Walk `tests/` and return {ticket_id: [(test_function, file_rel), ...]}.

    A test file maps to a ticket if:
      (a) the file's docstring or any comment line in the first 30 lines
          mentions the ticket id, OR
      (b) the file's stem heuristically matches the ticket (e.g.
          `tests/test_rule_promotion.py` for TMX-3045 - we don't enforce
          this; (a) is the canonical signal).

    The test functions returned for a ticket are ALL `test_*` defs in the
    matched file. (Per-AC mapping requires more granular metadata than
    today's worksheets carry; capturing the test FILE per ticket is the
    pragmatic minimum and matches GAMP 5's "tests for FS-Req-N" granularity.)
    """
    if not tests_root.is_dir():
        return {}

    out: dict[str, list[tuple[str, str]]] = {}
    for path in sorted(tests_root.rglob("test_*.py")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:  # pragma: no cover
            continue

        # Look in the first 30 non-empty lines (docstring + module-level
        # comments) for ticket-id references. Avoids false positives from
        # ticket ids deep in tests that just mention spawned follow-ups.
        head = "\n".join(text.splitlines()[:30])
        ticket_ids = {m.group(1).upper() for m in TICKET_ID_IN_TEST_RE.finditer(head)}
        if not ticket_ids:
            continue

        test_funcs = TEST_DEF_RE.findall(text)
        rel = str(path.relative_to(tests_root.parent)).replace("\\", "/")
        for tid in ticket_ids:
            for fn in test_funcs:
                out.setdefault(tid, []).append((fn, rel))
    return out


def _classify_row(
    test_function: Optional[str],
    commit_sha: Optional[str],
    is_planning_only: bool,
) -> Status:
    """Return the row status given the available evidence."""
    if is_planning_only:
        return "PLANNING_ONLY"
    if test_function and commit_sha:
        return "OK"
    if commit_sha and not test_function:
        return "NO_TEST"
    if test_function and not commit_sha:
        return "NO_COMMIT"
    return "UNVERIFIED"


def _build_rows_for_worksheet(
    ws: Worksheet,
    test_index: dict[str, list[tuple[str, str]]],
    repo_root: Path,
) -> list[TraceabilityRow]:
    """Produce one or more TraceabilityRow per worksheet.

    Strategy:
      - one row per declared AC (extracted from the worksheet body).
      - if no ACs declared, emit a single "AC-N/A" row so the ticket still
        appears.
      - test_function / test_file: pulled from the test_index by ticket id.
        For per-AC granularity, all tests for a ticket are attributed to
        every AC (today's worksheets do not carry test->AC mapping; FS-level
        granularity is the documented limit).
      - commit_sha: resolved via _find_commit_for_ticket; on failure, None.
    """
    ac_ids = extract_acceptance_criteria(ws.raw_text)
    if not ac_ids:
        ac_ids = ["AC-N/A"]

    test_pairs = test_index.get(ws.ticket_id.upper(), [])
    # Pick a stable representative test for each AC. If we have N tests and
    # M ACs, distribute round-robin (or just attribute the FIRST test to
    # every AC if N < M - the matrix is FS-level, not AC-level granularity).
    if test_pairs:
        rep_fn, rep_file = test_pairs[0]
    else:
        rep_fn, rep_file = None, None

    sha = _find_commit_for_ticket(ws.ticket_id, repo_root, ws.declared_shas)

    note = ""
    if ws.planning_only:
        note = "planning-only worksheet (Stage 5: N/A)"
    elif sha is None and rep_fn is None:
        note = "no commit subject matched ticket id; no test found"
    elif sha is None:
        note = "no commit subject matched ticket id"
    elif rep_fn is None:
        note = "no test file references ticket id in head comments"

    rows: list[TraceabilityRow] = []
    for ac_id in ac_ids:
        status = _classify_row(rep_fn, sha, ws.planning_only)
        rows.append(
            TraceabilityRow(
                ticket_id=ws.ticket_id,
                ac_id=ac_id,
                test_function=rep_fn,
                test_file=rep_file,
                commit_sha=sha,
                status=status,
                note=note,
            )
        )
    return rows


def build_matrix(repo_root: Path | str = ".") -> TraceabilityMatrix:
    """Build a TraceabilityMatrix from the repo on disk.

    Args:
        repo_root: path to the repository root. Defaults to ".".

    Returns:
        A TraceabilityMatrix with rows sorted by (ticket_id, ac_id).
        Tolerant of:
          - missing `.git/` (commit_sha will be None on every row)
          - missing `tests/` (test_function will be None on every row)
          - planning-only worksheets (PLANNING_ONLY status, no exception)
    """
    repo = Path(repo_root).resolve()
    loops_dir = repo / ".context" / "loops"
    tests_dir = repo / "tests"

    worksheets = iter_worksheets(loops_dir)
    test_index = _index_tests_by_ticket(tests_dir)

    rows: list[TraceabilityRow] = []
    for ws in worksheets:
        rows.extend(_build_rows_for_worksheet(ws, test_index, repo))

    # Stable ordering: ticket id, then AC id (numeric where possible).
    def _ac_sort_key(ac: str) -> tuple[int, str]:
        match = re.match(r"AC-(\d+)", ac)
        if match:
            return (int(match.group(1)), ac)
        return (10**9, ac)  # AC-N/A and weird ones go last

    rows.sort(key=lambda r: (r.ticket_id, _ac_sort_key(r.ac_id)))

    return TraceabilityMatrix(
        rows=rows,
        repo_root=repo,
    )
