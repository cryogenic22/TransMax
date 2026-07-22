"""TMX-DRIFT-NUMERIC-SHA — a declared commit SHA with no hex letters must resolve.

Bug: ``_worksheet_parser.parse_worksheet`` only accepted a declared SHA when it
contained at least one of ``abcdef``::

    if len(sha) >= 7 and any(c in sha for c in "abcdef"):

An abbreviated git SHA is 7-12 hex characters; roughly one in 270 abbreviated
7-char SHAs is all digits (10^7 / 16^7). For those, a worksheet that declares
its commit in the exact documented deploy-stage format is silently treated as
having declared nothing, and the drift auditor reports MISSING-COMMIT — the
"lying backlog" verdict — against a ticket that is correctly documented.

Real instance: commit ``6536939`` (batched judge ensemble + kappa + eval-CI)
produced three false MISSING-COMMIT verdicts (TMX-MQM-ENSEMBLE-RUN,
TMX-MQM-EVAL-CI, TMX-MQM-EVAL-KAPPA) even though each worksheet carried
``- [x] Commit: `6536939``` and the SHA is an ancestor of origin/main.

Why the letter-guard is not needed here: extraction only inspects lines that
already matched ``COMMIT_DECLARATION_RE`` — a structured deploy-stage
declaration anchored on ``Commit:`` / ``Shipped`` / ``Closed``. The structural
anchor, not the character class, is what prevents prose numbers from being read
as SHAs. A false MISSING-COMMIT is strictly worse than a missed prose number:
it accuses a truthful worksheet of lying (A3 — an audit signal must not
fabricate a defect).
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from _worksheet_parser import parse_worksheet  # noqa: E402

_ALL_DIGIT_SHA = "6536939"
_MIXED_SHA = "a23b0eb"


def _write(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def test_all_digit_declared_sha_is_extracted(tmp_path: Path) -> None:
    """The regression: an all-numeric SHA in a structured Commit: line."""
    path = _write(
        tmp_path,
        "TMX-NUMERIC.md",
        "# TMX-NUMERIC - synthetic\n\n"
        "**State**: `[Done]`\n\n"
        "## 8. Deploy\n\n"
        f"- [x] Commit: `{_ALL_DIGIT_SHA}` (batch w/ two sibling tickets)\n",
    )

    ws = parse_worksheet(path)

    assert _ALL_DIGIT_SHA in ws.declared_shas, (
        "an all-digit abbreviated SHA declared in the documented deploy-stage "
        f"format must be extracted; got {ws.declared_shas!r}"
    )


def test_mixed_case_declared_sha_still_extracted(tmp_path: Path) -> None:
    """Guard against fixing the numeric case by breaking the normal one."""
    path = _write(
        tmp_path,
        "TMX-MIXED.md",
        "# TMX-MIXED - synthetic\n\n"
        "**State**: `[Done]`\n\n"
        "## 8. Deploy\n\n"
        f"- [x] Commit: `{_MIXED_SHA}`\n",
    )

    ws = parse_worksheet(path)

    assert _MIXED_SHA in ws.declared_shas


def test_prose_numbers_are_not_read_as_shas(tmp_path: Path) -> None:
    """The structural anchor, not the character class, rejects prose numbers.

    Line counts, dates and issue numbers in narrative text must never be
    harvested as declared SHAs — otherwise the auditor would resolve a ticket
    against an unrelated commit, which is the opposite failure and just as bad.
    """
    path = _write(
        tmp_path,
        "TMX-PROSE.md",
        "# TMX-PROSE - synthetic\n\n"
        "**State**: `[WIP]`\n\n"
        "## 5. Eval / Test\n\n"
        "Suite grew to 1234567 lines and PR 9876543 tracked it; see also\n"
        "TMX-3700 (b043075) for the sibling change.\n",
    )

    ws = parse_worksheet(path)

    assert ws.declared_shas == [], (
        "prose numerics and cross-referenced ticket SHAs must not be treated "
        f"as this worksheet's declared commits; got {ws.declared_shas!r}"
    )
