"""Shared worksheet parser for `.context/loops/TMX-*.md` files.

Originally extracted from `scripts/audit_worksheet_drift.py` (TMX-3060) to
avoid duplication when TMX-3500 (Regulatory Pack scaffold) added a second
consumer that walks the same worksheets.

Both consumers need:
  - the parsed `Worksheet` dataclass (state token, planning-only flag,
    declared SHAs, raw header line).
  - the regexes that recognise structured commit declarations (so prose
    mentions of OTHER tickets' SHAs do not yield false positives).
  - the constants for IGNORE basenames / prefixes / planning markers.

This module is deliberately stdlib-only. No third-party dependencies.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Header parsing constants
# ---------------------------------------------------------------------------

# `**State**: \`[Done]\` pending push` or `**State**: \`[Verify]\` -> \`[Done]\`...`
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
# Kept identical to the pre-extraction `audit_worksheet_drift.py` constants
# so the drift audit's behaviour is unchanged by the refactor (TMX-3500 AC-8).
# A "Stage 5: N/A" worksheet without an additional explicit marker will
# therefore NOT be treated as planning-only by either consumer; that's
# deliberate - the explicit "no code change" / "planning only" wording is
# the documented signal.
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
# `Loop fire 16 (\`a48c2b6\`) shipped...`.
COMMIT_DECLARATION_RE = re.compile(
    r"^\s*(?:- \[[x ]\]\s+)?(?:Commit|Code|Shipped|Closed)\b"
    r"(?:\s+at|\s+via|:\s+|\s+)`?[0-9a-f]{7,12}`?",
    re.IGNORECASE | re.MULTILINE,
)

# Acceptance-criterion line patterns. Worksheets use BOTH:
#   - [ ] **AC-1**: <statement>
#   - [x] **AC-3** (label): <statement>
#   - **AC-2**: <statement>     (no checkbox; rarer)
# The harness needs to extract the AC id and a short label.
AC_RE = re.compile(
    r"^\s*(?:- \[[x ]\]\s+)?\*\*(AC-\d+[a-z]?)\*\*",
    re.MULTILINE | re.IGNORECASE,
)


@dataclass
class Worksheet:
    """Parsed worksheet header + body, suitable for downstream consumers."""

    path: Path
    ticket_id: str  # filename stem, e.g. "TMX-3050" or "TMX-3702-a11y"
    raw_state_line: str
    state_token: Optional[str]  # Spec / Design / WIP / Verify / Fix / Done / Blocked
    pending: bool
    planning_only: bool
    declared_shas: list[str]  # any explicit SHAs the worksheet body claims
    raw_text: str  # full file body, for downstream AC extraction etc.


def normalise(text: str) -> str:
    """Lowercase and normalise newlines for marker-string matching."""
    return text.lower().replace("\r\n", "\n").replace("\r", "\n")


def parse_worksheet(path: Path) -> Optional[Worksheet]:
    """Parse a single worksheet file. Returns None if it should be ignored.

    Ignored:
      - `_template.md`, `README.md`
      - filenames starting with `HANDOFF`
      - filenames not starting with `TMX-`
    """
    if path.name in IGNORE_BASENAMES:
        return None
    if any(path.name.startswith(prefix) for prefix in IGNORE_PREFIXES):
        return None
    if not path.name.startswith("TMX-"):
        return None

    try:
        # Universal-newline translation handles CRLF on Windows.
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:  # pragma: no cover - fs error path
        print(f"# error reading {path}: {exc}", file=sys.stderr)
        return None

    norm = normalise(text)

    state_match = STATE_RE.search(text)
    raw_state_line = state_match.group(1).strip() if state_match else ""

    state_token: Optional[str] = None
    if state_match:
        # Multiple state tokens may appear on a single line (e.g.
        # `[Verify]` -> `[Done]` pending commit). Take the LAST one as the
        # current state.
        tokens = STATE_TOKEN_RE.findall(state_match.group(0))
        if tokens:
            state_token = tokens[-1]

    raw_state_norm = normalise(raw_state_line)
    pending = any(marker in raw_state_norm for marker in PENDING_MARKERS)

    # Planning-only override: the worksheet must EXPLICITLY say so in its
    # deploy / status-log section. Defaults to False so missing commits stay
    # loud.
    planning_only = any(marker in norm for marker in PLANNING_ONLY_MARKERS)

    # Declared SHAs - pulled only from STRUCTURED declarations. We do NOT
    # parse free prose because that picks up cross-references to OTHER
    # tickets' commits and would yield false-positive resolutions.
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
        raw_text=text,
    )


def extract_acceptance_criteria(text: str) -> list[str]:
    """Return the AC ids declared in a worksheet body, in source order.

    Examples of lines that match:
      - [ ] **AC-1**: ...
      - [x] **AC-2** (some label): ...
      **AC-3**: ...

    Ids are returned uppercased ("AC-1", "AC-2"). De-duplicated, preserving
    first-seen order.
    """
    seen: set[str] = set()
    out: list[str] = []
    for match in AC_RE.finditer(text):
        ac_id = match.group(1).upper()
        if ac_id not in seen:
            seen.add(ac_id)
            out.append(ac_id)
    return out


def iter_worksheets(loops_dir: Path) -> list[Worksheet]:
    """Walk `loops_dir`, yielding parsed worksheets in filename-sorted order.

    Skips ignored basenames / prefixes / non-TMX files. Returns a list rather
    than an iterator so callers can len() / index without re-walking.
    """
    if not loops_dir.is_dir():
        return []
    out: list[Worksheet] = []
    for path in sorted(loops_dir.iterdir()):
        if not path.is_file():
            continue
        ws = parse_worksheet(path)
        if ws is None:
            continue
        out.append(ws)
    return out
