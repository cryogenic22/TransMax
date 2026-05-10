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

Why `merge-base --is-ancestor` and not `git cat-file -e`:
  cat-file -e only verifies a SHA exists in the object database. We need to
  verify the SHA is reachable from origin/main, otherwise a local-only commit
  on a feature branch would be reported as "OK" — defeating the audit.

Usage:
  python scripts/audit_worksheet_drift.py
  python scripts/audit_worksheet_drift.py --root /path/to/repo
  python scripts/audit_worksheet_drift.py --remote-ref origin/main

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

# ---------------------------------------------------------------------------
# Worksheet parsing
# ---------------------------------------------------------------------------

# Header line, e.g. `**State**: \`[Done]\` pending push` or
# `**State**: \`[Verify]\` → \`[Done]\` pending commit`
STATE_RE = re.compile(r"^\*\*State\*\*:\s*(.+)$", re.MULTILINE)

# Bracketed states the README defines.
STATE_TOKEN_RE = re.compile(r"\[(Spec|Design|WIP|Verify|Fix|Done|Blocked)\]")

# Pending-push markers, normalised lowercase.
PENDING_MARKERS = (
    "pending commit + push",
    "pending commit+push",
    "pending push",
    "pending commit",
    "(local; awaiting push)",
    "local; awaiting push",
    "(awaiting push)",
    "awaiting push",
)

# Planning-only marker (Done with explicit "no code change" disclaimer).
PLANNING_ONLY_MARKERS = (
    "no code change",
    "planning only",
    "planning-only",
)

TERMINAL_STATES = {"Done"}
NON_TERMINAL_STATES = {"Spec", "Design", "WIP", "Verify", "Fix", "Blocked"}

IGNORE_BASENAMES = {"_template.md", "README.md"}
IGNORE_PREFIXES = ("HANDOFF",)

# Match a 7-12 char hex SHA preceded by a non-hex word boundary. Used to
# pick up explicit `Commit: \`abc1234\`` claims in worksheet bodies.
SHA_RE = re.compile(r"(?:^|[^0-9a-f])([0-9a-f]{7,12})(?:[^0-9a-f]|$)", re.IGNORECASE)

# Lines in the worksheet that look like a STRUCTURED commit-SHA declaration
# (deploy-stage checkbox or status-log SHA cell). Excludes prose mentions of
# OTHER tickets' commits like `(see TMX-3700 b043075)` or
# `Loop fire 16 (\`a48c2b6\`) shipped …`.
COMMIT_DECLARATION_RE = re.compile(
    r"^\s*(?:- \[[x ]\]\s+)?(?:Commit|Code|Shipped|Closed)\b"
    r"(?:\s+at|\s+via|:\s+|\s+)`?[0-9a-f]{7,12}`?",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass
class Worksheet:
    """Parsed worksheet header."""

    path: Path
    ticket_id: str  # filename stem, e.g. "TMX-3050" or "TMX-3702-a11y"
    raw_state_line: str
    state_token: Optional[str]  # Spec / Design / WIP / Verify / Fix / Done / Blocked
    pending: bool
    planning_only: bool
    declared_shas: list[str]  # any explicit SHAs the worksheet body claims


def _normalise(text: str) -> str:
    return text.lower().replace("\r\n", "\n").replace("\r", "\n")


def parse_worksheet(path: Path) -> Optional[Worksheet]:
    """Parse a single worksheet file. Returns None if it should be ignored."""
    if path.name in IGNORE_BASENAMES:
        return None
    if any(path.name.startswith(prefix) for prefix in IGNORE_PREFIXES):
        return None
    if not path.name.startswith("TMX-"):
        return None

    try:
        # Universal-newline translation handles CRLF on Windows.
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:  # pragma: no cover — fs error path
        print(f"# error reading {path}: {exc}", file=sys.stderr)
        return None

    norm = _normalise(text)

    state_match = STATE_RE.search(text)
    raw_state_line = state_match.group(1).strip() if state_match else ""

    state_token: Optional[str] = None
    if state_match:
        # Multiple state tokens may appear on a single line (e.g.
        # `[Verify]` → `[Done]` pending commit). Take the LAST one as the
        # current state.
        tokens = STATE_TOKEN_RE.findall(state_match.group(0))
        if tokens:
            state_token = tokens[-1]

    raw_state_norm = _normalise(raw_state_line)
    pending = any(marker in raw_state_norm for marker in PENDING_MARKERS)

    # Planning-only override: the worksheet must EXPLICITLY say so in its
    # deploy / status-log section. Defaults to False so missing commits stay
    # loud.
    planning_only = any(marker in norm for marker in PLANNING_ONLY_MARKERS)

    # Declared SHAs — pulled only from STRUCTURED declarations. We do NOT
    # parse free prose because that picks up cross-references to OTHER
    # tickets' commits (e.g. `Loop fire 16 (\`a48c2b6\`) shipped …`) and
    # would yield false-positive resolutions.
    declared_shas: list[str] = []
    for line in text.splitlines():
        if not COMMIT_DECLARATION_RE.match(line):
            continue
        for match in SHA_RE.finditer(line):
            sha = match.group(1).lower()
            if len(sha) >= 7 and any(c in sha for c in "abcdef"):
                if sha not in declared_shas:
                    declared_shas.append(sha)

    return Worksheet(
        path=path,
        ticket_id=path.stem,
        raw_state_line=raw_state_line,
        state_token=state_token,
        pending=pending,
        planning_only=planning_only,
        declared_shas=declared_shas,
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


def classify(ws: Worksheet, sha: Optional[str], on_remote: bool) -> tuple[str, str]:
    """Return (verdict, actual_state_summary)."""
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

    # Unknown / un-parseable state: treat as IN-FLIGHT to avoid false alarm,
    # but flag in the summary so a human can curate.
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
    args = parser.parse_args()

    loops_dir = args.root / ".context" / "loops"
    if not loops_dir.is_dir():
        print(f"error: {loops_dir} does not exist", file=sys.stderr)
        return 2

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

        verdict, summary = classify(ws, sha, on_remote)
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
        print(
            f"| `{ws.ticket_id}` | {claimed} | {summary} | **{verdict}** |"
        )
    print()
    print("## Summary")
    print(f"- OK: {ok_count}")
    print(f"- LOCAL-ONLY (drift): {drift_count}")
    print(f"- MISSING-COMMIT (lying-backlog suspect): {missing_count}")
    print(f"- STALE-STATE (worksheet header out of sync with shipped code): {stale_count}")
    print(f"- IN-FLIGHT: {inflight_count}")
    print(f"- IGNORE: {ignore_count}")

    failure_count = drift_count + missing_count + stale_count
    if failure_count == 0:
        print()
        print("All Done worksheets resolved to commits on origin/main. No drift.")
        return 0

    print()
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
    return 1


if __name__ == "__main__":
    sys.exit(main())
