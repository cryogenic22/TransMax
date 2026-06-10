"""Engine hardening loops — TMX-3211 (force_finalize) + TMX-QG-ESCAPE.

TMX-3211: a safety regression during refinement used to set the magic
`iteration_count = 999` to break the loop. Replaced by an explicit
`force_finalize` flag read by `decide_next_step`.

TMX-QG-ESCAPE: `quality_gate.py` raised a SyntaxWarning (invalid escape `\\[`
in a non-raw docstring). The docstring is now raw.
"""
from __future__ import annotations

import warnings
from pathlib import Path

from app.agents.graph import decide_next_step

_GRAPH = Path(__file__).resolve().parent.parent / "app" / "agents" / "graph.py"
_QG = Path(__file__).resolve().parent.parent / "app" / "services" / "quality_gate.py"


# ── TMX-3211 ─────────────────────────────────────────────────────────────


def test_force_finalize_short_circuits_to_finalize() -> None:
    # Even with REVIEW_REQUIRED and iterations < 3 (which would normally refine),
    # force_finalize routes straight to finalize.
    state = {
        "force_finalize": True,
        "quality_report": {"status": "REVIEW_REQUIRED"},
        "iteration_count": 0,
    }
    assert decide_next_step(state) == "finalize"


def test_without_force_finalize_review_still_refines() -> None:
    state = {"quality_report": {"status": "REVIEW_REQUIRED"}, "iteration_count": 0}
    assert decide_next_step(state) == "refine"


def test_no_999_sentinel_assignment_remains() -> None:
    # Ignore comment lines (which mention the retired sentinel for context).
    code = "\n".join(
        ln for ln in _GRAPH.read_text(encoding="utf-8").splitlines()
        if not ln.lstrip().startswith("#")
    )
    assert "= 999" not in code, "the iteration_count=999 sentinel assignment must be gone"


# ── TMX-QG-ESCAPE ────────────────────────────────────────────────────────


def test_quality_gate_compiles_without_syntax_warning() -> None:
    import py_compile

    with warnings.catch_warnings():
        warnings.simplefilter("error", SyntaxWarning)
        # doraise turns a compile SyntaxError/Warning into an exception
        py_compile.compile(str(_QG), doraise=True)
