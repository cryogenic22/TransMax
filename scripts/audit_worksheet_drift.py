#!/usr/bin/env python3
"""Audit drift between .context/loops/ worksheets and the actual git history.

For each worksheet under .context/loops/ matching `TMX-*.md`, this script:

  1. Parses the `**State**:` header to detect claimed loop state and any
     "pending commit" / "pending push" / "(local; awaiting push)" markers.
  2. Searches `git log --all` for a commit whose subject begins with the
     worksheet's ticket id.
  3. Verifies the matched commit is reachable from `origin/main` via
     `git merge-base --is-ancestor`.

Prints a Markdown-style table:

    | worksheet | claimed state | actual state | verdict |

Exits 0 if no drift, 1 otherwise. Read-only against git + filesystem.

Verdicts:

  OK              Done + commit on origin/main
  LOCAL-ONLY      Done + commit exists locally but is NOT on origin/main
  MISSING-COMMIT  Done + no matching commit anywhere (lying-backlog suspect)
  IN-FLIGHT       Spec / Design / WIP / Verify / Fix / Blocked — non-terminal
  IGNORE          Template / README / handoff doc / planning-only worksheet
  DONE_STALE_QUALIFIER  (--check-ids only) State header matches `[Done` plus a
                  trailing qualifier ("[Done, pending push]", "[Done — X]") —
                  header vocabulary needs normalising to `[Done]`. Advisory
                  bucket; does not affect the exit code.

Ticket-ID integrity lint (TMX-DRIFT-IDLINT; opt-in via --check-ids so the
advisory pre-commit hook's flag-less semantics are unchanged):

  - duplicate board-row IDs: the same TMX-id introduced as the first-cell ID
    of two different rows in ticket-introduction tables (header first cell
    `Ticket`) inside `.context/active_tasks.md` -> listed, exit non-zero.
  - orphan IDs: TMX-ids matched anywhere in the board (prose or another row's
    Notes cell) that are the first-cell ID of NO table row -> advisory list,
    never affects the exit code (triage belongs to the board-hygiene sweep).

Why `merge-base --is-ancestor` and not `git cat-file -e`:
  cat-file -e only verifies a SHA exists in the object database. We need to
  verify the SHA is reachable from origin/main, otherwise a local-only commit
  on a feature branch would be reported as "OK" — defeating the audit.

Usage:
  python scripts/audit_worksheet_drift.py
  python scripts/audit_worksheet_drift.py --root /path/to/repo
  python scripts/audit_worksheet_drift.py --remote-ref origin/main
  python scripts/audit_worksheet_drift.py --check-ids

CI / pre-commit gate:
  exit 0 = no drift, 1 = drift found.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Worksheet parsing primitives are shared with regulatory_pack/generators/
# traceability.py via _worksheet_parser. Keep this script's behaviour
# unchanged - the import is a refactor, not a feature change.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:  # pragma: no cover - script-style runtime
    sys.path.insert(0, str(_HERE))

from _worksheet_parser import (  # noqa: E402  (after sys.path manipulation)
    NON_TERMINAL_STATES,
    TERMINAL_STATES,
    Worksheet,
    parse_worksheet,
)


# ---------------------------------------------------------------------------
# Ticket-ID integrity lint (TMX-DRIFT-IDLINT; active only under --check-ids)
# ---------------------------------------------------------------------------

# A ticket id: `TMX-` then alphanumeric, optionally continuing with
# alphanumerics/hyphens but always ENDING on an alphanumeric — so prose like
# "TMX-3604-*" yields "TMX-3604" and brace expansions cannot capture a
# trailing hyphen.
TICKET_ID_RE = re.compile(r"TMX-[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?")

# `[Done` + word boundary + at least one more char before `]` — matches
# "[Done, pending push]" / "[Done — X]" but neither "[Done]" (tokenisable,
# never reaches the unparseable fallback) nor "[DoneX]" / "[PARKED — ...]".
DONE_QUALIFIER_RE = re.compile(r"\[Done\b[^\]]+\]")

# Header first-cell that marks a ticket-INTRODUCTION table on the board.
# Session-recap tables use `Loop` and are rows-but-not-introductions.
_INTRO_HEADER_CELL = "ticket"


@dataclass
class BoardIdScan:
    """Mechanical ID facts scanned from `.context/active_tasks.md`.

    The lint reports facts only; whether two introduction rows are "the same
    ticket re-listed" or "two unrelated tickets colliding" is the
    board-hygiene sweep's triage, deliberately not guessed here (A3).
    """

    intro_rows: dict[str, list[int]]  # id -> line numbers of introduction rows
    any_row_ids: set[str]  # first-cell ids of ANY table row (intro or recap)
    occurrences: dict[str, list[int]]  # id -> line numbers of every mention

    @property
    def duplicate_ids(self) -> dict[str, list[int]]:
        """Ids introduced by two or more board table rows."""
        return {t: rows for t, rows in self.intro_rows.items() if len(rows) >= 2}

    @property
    def orphan_ids(self) -> dict[str, list[int]]:
        """Ids mentioned anywhere but the first-cell ID of no table row."""
        return {
            t: lines
            for t, lines in self.occurrences.items()
            if t not in self.any_row_ids
        }


def _is_separator_cell(cell: str) -> bool:
    """True for markdown table separator cells like `---` / `:---:`."""
    return bool(cell) and set(cell) <= {"-", ":", " "} and "-" in cell


def scan_board_ids(text: str) -> BoardIdScan:
    """Scan the board file for table-row ids vs prose-only ids. Pure function.

    Table-kind tracking: a contiguous block of `|`-prefixed lines is one
    table; its header's first cell decides whether id-bearing rows count as
    ticket INTRODUCTIONS (`Ticket`) or mere rows (anything else, e.g. `Loop`).
    A non-pipe line ends the table.
    """
    intro_rows: dict[str, list[int]] = {}
    any_row_ids: set[str] = set()
    occurrences: dict[str, list[int]] = {}
    current_kind: Optional[str] = None  # "intro" | "other" | None

    for lineno, line in enumerate(text.splitlines(), start=1):
        for match in TICKET_ID_RE.finditer(line):
            occurrences.setdefault(match.group(0), []).append(lineno)

        stripped = line.strip()
        if not stripped.startswith("|"):
            current_kind = None
            continue

        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if not cells or not cells[0]:
            continue
        first = cells[0]
        if _is_separator_cell(first):
            continue
        if first.strip("*`_ ").lower() == _INTRO_HEADER_CELL:
            current_kind = "intro"
            continue

        id_match = TICKET_ID_RE.search(first)
        if id_match is None:
            # Either the header row of a non-introduction table (`Loop` etc.)
            # opening a new pipe block, or an id-less data row mid-table
            # (which must NOT flip the current table's kind).
            if current_kind is None:
                current_kind = "other"
            continue

        ticket_id = id_match.group(0)
        any_row_ids.add(ticket_id)
        if current_kind == "intro":
            intro_rows.setdefault(ticket_id, []).append(lineno)

    return BoardIdScan(
        intro_rows=intro_rows,
        any_row_ids=any_row_ids,
        occurrences=occurrences,
    )


# ---------------------------------------------------------------------------
# Git resolution
# ---------------------------------------------------------------------------


def _run_git(args: list[str], cwd: Path) -> tuple[int, str]:
    """Run a git subcommand. Returns (exit_code, stdout). stderr is suppressed."""
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return proc.returncode, proc.stdout


def find_commit_for_ticket(
    ticket_id: str,
    repo_root: Path,
    declared_shas: Optional[list[str]] = None,
) -> Optional[str]:
    """Find the OLDEST commit on any ref whose subject starts with ticket_id.

    Resolution order:
      1. If the worksheet body explicitly declares a SHA in a STRUCTURED
         deploy-stage line ('Commit: <sha>', 'Shipped <sha>', etc.), honour
         it. We deliberately ignore prose mentions of OTHER tickets' SHAs.
      2. Anchored prefix search by subject (re-anchored because git's
         '--grep' matches anywhere in the message).
      3. Variant-suffix search ('<id>-v1:' / '<id>-v2:' patterns).
      4. Prefix degradation for compound ids ('TMX-3200-3201' -> 'TMX-3200').

    Oldest-first because original commits are what we audit; backfill /
    fix commits should not occlude a true MISSING-COMMIT verdict.
    """
    declared_shas = declared_shas or []

    code, out = _run_git(
        ["log", "--all", "--reverse", "--pretty=format:%H %s"],
        repo_root,
    )
    if code != 0:
        return None

    sha_lines = [line.partition(" ") for line in out.splitlines()]

    # 1. Honour any worksheet-declared SHAs.
    for declared in declared_shas:
        for sha, _, _subject in sha_lines:
            if sha.lower().startswith(declared.lower()):
                return sha

    # 2. Anchor to subject start. Allow `:` or whitespace after id.
    pattern = re.compile(rf"^{re.escape(ticket_id)}[:\s]")
    for sha, _, subject in sha_lines:
        if pattern.match(subject):
            return sha

    # 3. Variant suffix (-v1, -v2, etc.).
    pattern = re.compile(rf"^{re.escape(ticket_id)}-v\d+[:\s]")
    for sha, _, subject in sha_lines:
        if pattern.match(subject):
            return sha

    # 4. Prefix degradation for compound ids.
    parts = ticket_id.split("-")
    while len(parts) > 2:
        parts = parts[:-1]
        prefix = "-".join(parts)
        pattern = re.compile(rf"^{re.escape(prefix)}[:\s]")
        for sha, _, subject in sha_lines:
            if pattern.match(subject):
                return sha

    return None


def is_on_remote(sha: str, remote_ref: str, repo_root: Path) -> bool:
    """Return True iff sha is reachable from remote_ref."""
    code, _ = _run_git(
        ["merge-base", "--is-ancestor", sha, remote_ref],
        repo_root,
    )
    return code == 0


# ---------------------------------------------------------------------------
# Verdict classification
# ---------------------------------------------------------------------------


def classify(
    ws: Worksheet,
    sha: Optional[str],
    on_remote: bool,
    tolerate_done_qualifiers: bool = False,
) -> tuple[str, str]:
    """Return (verdict, actual_state_summary).

    With ``tolerate_done_qualifiers`` (--check-ids), un-tokenisable State
    headers of the form `[Done` + qualifier + `]` get their own advisory
    DONE_STALE_QUALIFIER bucket instead of drowning in IN-FLIGHT noise.
    Default False keeps the flag-less report byte-identical.
    """
    if ws.state_token in NON_TERMINAL_STATES:
        if sha is not None:
            # Header lies: code shipped but worksheet still says Spec/WIP/etc.
            note = f"{ws.state_token} header but commit {sha[:7]} shipped"
            if not on_remote:
                note += " (local-only)"
            return "STALE-STATE", note
        return "IN-FLIGHT", f"{ws.state_token} — no commit expected yet"

    if ws.state_token in TERMINAL_STATES:
        if ws.planning_only and sha is None:
            return "IGNORE", "planning-only Done; no code change expected"
        if sha is None:
            return "MISSING-COMMIT", "no commit subject matches ticket id"
        if on_remote:
            return "OK", f"commit {sha[:7]} on origin/main"
        return "LOCAL-ONLY", f"commit {sha[:7]} exists, NOT on origin/main"

    # Unknown / un-parseable state. Under --check-ids, `[Done, pending push]`
    # style headers become a distinct, mechanically sweepable bucket.
    if tolerate_done_qualifiers and DONE_QUALIFIER_RE.search(ws.raw_state_line):
        if sha is None:
            note = "Done-qualifier header; no commit subject matches ticket id"
        elif on_remote:
            note = (
                f"Done-qualifier header; commit {sha[:7]} on remote — "
                "normalise header to [Done]"
            )
        else:
            note = f"Done-qualifier header; commit {sha[:7]} local-only"
        return "DONE_STALE_QUALIFIER", note

    # Treat as IN-FLIGHT to avoid false alarm, but flag in the summary so a
    # human can curate.
    return "IN-FLIGHT", f"unparseable state: {ws.raw_state_line[:60]!r}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _reconfigure_stdout_utf8() -> None:
    """Make stdout/stderr tolerate non-ASCII even on cp1252 Windows consoles."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name)
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            # Older Python or non-TextIOWrapper; best-effort only.
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass


def main() -> int:
    _reconfigure_stdout_utf8()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Repository root (default: parent of scripts/).",
    )
    parser.add_argument(
        "--remote-ref",
        default="origin/main",
        help="Remote ref to check ancestry against (default: origin/main).",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable terminal colour (default: auto).",
    )
    parser.add_argument(
        "--check-ids",
        action="store_true",
        help=(
            "Ticket-ID integrity lint on .context/active_tasks.md: duplicate"
            " board-row ids FAIL, orphan ids are listed advisory, and"
            " `[Done, <qualifier>]` worksheet headers get their own"
            " DONE_STALE_QUALIFIER bucket. Default behaviour (and the"
            " advisory pre-commit hook) is unchanged without this flag."
        ),
    )
    args = parser.parse_args()

    loops_dir = args.root / ".context" / "loops"
    if not loops_dir.is_dir():
        print(f"error: {loops_dir} does not exist", file=sys.stderr)
        return 2

    board_path = args.root / ".context" / "active_tasks.md"
    board_scan: Optional[BoardIdScan] = None
    if args.check_ids:
        # Fail loud, never silently pass on a missing board (A3).
        if not board_path.is_file():
            print(
                f"error: --check-ids requires {board_path}, which does not exist",
                file=sys.stderr,
            )
            return 2
        board_scan = scan_board_ids(
            board_path.read_text(encoding="utf-8", errors="replace")
        )

    # Verify origin/main resolves; if not, treat all "Done with SHA" as
    # LOCAL-ONLY would be wrong, so error out instead of silently passing.
    code, _ = _run_git(["rev-parse", "--verify", args.remote_ref], args.root)
    if code != 0:
        print(
            f"error: {args.remote_ref} does not resolve. Run `git fetch` first.",
            file=sys.stderr,
        )
        return 2

    rows: list[tuple[Worksheet, str, str]] = []
    drift_count = 0
    missing_count = 0
    stale_count = 0
    ok_count = 0
    inflight_count = 0
    ignore_count = 0
    done_qualifier_count = 0

    for path in sorted(loops_dir.iterdir()):
        if not path.is_file():
            continue
        ws = parse_worksheet(path)
        if ws is None:
            continue

        # Always look up: a non-terminal state header may be stale (the loop
        # shipped but the worksheet never had its State bumped). Classifier
        # will distinguish.
        sha = find_commit_for_ticket(
            ws.ticket_id,
            args.root,
            declared_shas=ws.declared_shas,
        )
        on_remote = is_on_remote(sha, args.remote_ref, args.root) if sha else False

        verdict, summary = classify(
            ws, sha, on_remote, tolerate_done_qualifiers=args.check_ids
        )
        rows.append((ws, verdict, summary))

        if verdict == "OK":
            ok_count += 1
        elif verdict == "LOCAL-ONLY":
            drift_count += 1
        elif verdict == "MISSING-COMMIT":
            missing_count += 1
        elif verdict == "STALE-STATE":
            stale_count += 1
        elif verdict == "IN-FLIGHT":
            inflight_count += 1
        elif verdict == "IGNORE":
            ignore_count += 1
        elif verdict == "DONE_STALE_QUALIFIER":
            done_qualifier_count += 1

    # ---- Render Markdown table ------------------------------------------
    print("# Worksheet drift audit")
    print(f"_remote ref:_ `{args.remote_ref}`")
    print()
    print("| Worksheet | Claimed state | Actual state | Verdict |")
    print("|---|---|---|---|")
    for ws, verdict, summary in rows:
        claimed = ws.raw_state_line[:50] if ws.raw_state_line else "(unparsed)"
        if ws.pending and "pending" not in claimed.lower():
            claimed += " (pending marker)"
        print(f"| `{ws.ticket_id}` | {claimed} | {summary} | **{verdict}** |")
    print()
    print("## Summary")
    print(f"- OK: {ok_count}")
    print(f"- LOCAL-ONLY (drift): {drift_count}")
    print(f"- MISSING-COMMIT (lying-backlog suspect): {missing_count}")
    print(
        f"- STALE-STATE (worksheet header out of sync with shipped code): {stale_count}"
    )
    print(f"- IN-FLIGHT: {inflight_count}")
    print(f"- IGNORE: {ignore_count}")
    if args.check_ids:
        print(
            "- DONE_STALE_QUALIFIER (Done-with-qualifier header — normalise"
            f" to [Done]; advisory): {done_qualifier_count}"
        )

    # ---- Ticket-ID integrity section (--check-ids only) ------------------
    duplicate_ids: dict[str, list[int]] = {}
    if board_scan is not None:
        duplicate_ids = board_scan.duplicate_ids
        orphan_ids = board_scan.orphan_ids
        print()
        print("## Ticket-ID integrity (--check-ids)")
        print(f"_board:_ `{board_path}`")
        print()
        print("### Duplicate board-row IDs (2+ introduction rows -> FAIL)")
        if duplicate_ids:
            for ticket_id in sorted(duplicate_ids):
                lines_str = ", ".join(str(n) for n in duplicate_ids[ticket_id])
                print(f"- `{ticket_id}`: lines {lines_str}")
        else:
            print("- none")
        print()
        print("### Orphan IDs (prose/Notes mention, no table row) — advisory")
        if orphan_ids:
            print(f"{len(orphan_ids)} orphan id(s):")
            for ticket_id in sorted(orphan_ids):
                first_line = orphan_ids[ticket_id][0]
                print(f"- `{ticket_id}` (first mention: line {first_line})")
        else:
            print("- none")

    failure_count = drift_count + missing_count + stale_count + len(duplicate_ids)
    if failure_count == 0:
        print()
        print("All Done worksheets resolved to commits on origin/main. No drift.")
        return 0

    print()
    if drift_count + missing_count + stale_count:
        print(
            f"DRIFT DETECTED: {drift_count} local-only, {missing_count} missing-commit, "
            f"{stale_count} stale-state."
        )
        print("  - LOCAL-ONLY: push the commit to origin/main, then re-run.")
        print(
            "  - MISSING-COMMIT: investigate. Either (a) the worksheet's commit"
            " subject does not start with the ticket id (record explicit"
            " `Commit: <sha>` in the worksheet's deploy stage), or (b) the"
            " worksheet claims Done for code that was never committed"
            " (lying-backlog — spawn a follow-up ticket)."
        )
        print(
            "  - STALE-STATE: the worksheet header still says Spec/WIP/Verify"
            " but a commit shipped. Bump the State header to `[Done]` and add"
            " the SHA to the deploy stage."
        )
    if duplicate_ids:
        print(
            f"DUPLICATE-ID DETECTED: {len(duplicate_ids)} ticket id(s) introduced"
            " by 2+ board table rows (--check-ids). Rename or merge the rows;"
            " triage belongs to the board-hygiene sweep."
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
