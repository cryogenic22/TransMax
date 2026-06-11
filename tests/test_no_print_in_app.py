"""TMX-PRINT-SWEEP — app/ must use logger, never print().

Regression guard: after converting all app/ prints to logger, this fails fast if
a new print() sneaks into app/ (the CLAUDE.md convention: "no print() in app/").
"""
from __future__ import annotations

import re
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"
# A real print call at statement position — not substrings like fingerprint/blueprint.
PRINT = re.compile(r"(?:^|[^A-Za-z0-9_.])print\(")


def test_no_print_calls_in_app() -> None:
    offenders: list[str] = []
    for py in APP.rglob("*.py"):
        for i, line in enumerate(py.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            if PRINT.search(line):
                offenders.append(f"{py.relative_to(APP.parent)}:{i}")
    assert not offenders, "Use logger, not print(), in app/. Offenders: " + ", ".join(offenders)
