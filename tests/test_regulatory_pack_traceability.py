"""TMX-3500 — Regulatory Pack traceability harness tests.

The harness walks `.context/loops/`, `tests/`, and `git log`, producing a
per-ticket → per-AC → per-test → per-commit matrix. These tests prove the
walker pipes through all three sources and tolerates planning-only worksheets
without crashing.

Per the worksheet's stage-2 spec:
  - AC-3: build_matrix returns a TraceabilityMatrix
  - AC-4: TMX-3045 row exists with non-None test_function and commit_sha
  - AC-5: planning-only worksheet (Stage 5: N/A) does not crash the harness
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_traceability_matrix_picks_up_recent_loops() -> None:
    """TMX-3500 / AC-4 — the traceability harness walks .context/loops/, tests/,
    and git, producing a per-ticket → per-AC → per-test → per-commit matrix.

    For TMX-3045 (just-shipped, well-known shape: 21 tests in
    tests/test_rule_promotion.py, 11 acceptance criteria, commit 7231c7d on
    origin/main), the matrix should contain at least one row with:
      - ticket_id == "TMX-3045"
      - some row has a non-None test_function
      - some row has a non-None commit_sha of length >= 7
    """
    from regulatory_pack.generators.traceability import build_matrix

    matrix = build_matrix(repo_root=REPO_ROOT)

    rows = [r for r in matrix.rows if r.ticket_id == "TMX-3045"]
    assert rows, "TMX-3045 should have at least one traceability row"
    assert any(
        r.test_function for r in rows
    ), "TMX-3045 should have at least one row with a test_function (test discovery)"
    assert any(
        r.commit_sha and len(r.commit_sha) >= 7 for r in rows
    ), "TMX-3045 should have at least one row with a commit_sha (git resolution)"


def test_traceability_matrix_handles_planning_only_worksheet(tmp_path: Path) -> None:
    """TMX-3500 / AC-5 — a worksheet with `Stage 5: N/A` (planning-only ticket)
    must not crash the harness.

    We synthesise a minimal repo layout in tmp_path with:
      - .context/loops/TMX-LOOP-HYGIENE.md (planning-only marker present)
      - tests/ (empty)
      - .git/ — absent; the harness should tolerate this and still emit rows
        for the worksheets it CAN parse, marking the missing-git-context
        rows as UNVERIFIED (or emit zero rows for that ticket; either is
        acceptable per the AC).
    """
    loops_dir = tmp_path / ".context" / "loops"
    loops_dir.mkdir(parents=True)
    (loops_dir / "TMX-LOOP-HYGIENE.md").write_text(
        "# TMX-LOOP-HYGIENE — Backfill worksheets for cleanup commits\n"
        "\n"
        "**State**: `[Done]` no code change; planning only\n"
        "**Owner**: pod-A\n"
        "\n"
        "## 1. Task\n"
        "\n"
        "Planning-only ticket. No code change.\n"
        "\n"
        "## 2. Spec — acceptance criteria\n"
        "\n"
        "- [x] **AC-1**: Worksheets exist for the two cleanup commits.\n"
        "\n"
        "## 5. Eval / Test\n"
        "\n"
        "Stage 5: N/A — planning only, no code shipped.\n",
        encoding="utf-8",
    )
    (tmp_path / "tests").mkdir()

    from regulatory_pack.generators.traceability import build_matrix

    # Should not crash even though there's no .git in tmp_path.
    matrix = build_matrix(repo_root=tmp_path)

    # The harness either emits zero rows for the planning-only ticket OR rows
    # with status="UNVERIFIED". Both are acceptable. The hard requirement is
    # NO EXCEPTION.
    hygiene_rows = [r for r in matrix.rows if r.ticket_id == "TMX-LOOP-HYGIENE"]
    if hygiene_rows:
        # If included, they must be UNVERIFIED (not falsely PASS).
        assert all(
            r.status in {"UNVERIFIED", "PLANNING_ONLY", "NO_COMMIT", "NO_TEST"}
            for r in hygiene_rows
        ), f"planning-only rows should not be marked OK; got {[r.status for r in hygiene_rows]}"


def test_traceability_matrix_has_expected_minimum_size() -> None:
    """TMX-3500 / AC-9 (G3 completion floor) — at least 30 rows total.

    With 50+ worksheets in .context/loops/ and 5+ ACs each (most have 6-11),
    we expect hundreds of rows. 30 is the documented floor.
    """
    from regulatory_pack.generators.traceability import build_matrix

    matrix = build_matrix(repo_root=REPO_ROOT)
    assert len(matrix.rows) >= 30, f"expected at least 30 rows, got {len(matrix.rows)}"


def test_traceability_matrix_row_shape() -> None:
    """TMX-3500 / AC-3 — each row exposes the expected fields and types."""
    from regulatory_pack.generators.traceability import (
        TraceabilityMatrix,
        TraceabilityRow,
        build_matrix,
    )

    matrix = build_matrix(repo_root=REPO_ROOT)

    assert isinstance(matrix, TraceabilityMatrix)
    assert all(isinstance(r, TraceabilityRow) for r in matrix.rows)

    # Pick any row and verify field presence + types.
    sample = matrix.rows[0]
    assert isinstance(sample.ticket_id, str) and sample.ticket_id.startswith("TMX-")
    assert isinstance(sample.ac_id, str)
    # test_function and commit_sha are Optional[str]
    assert sample.test_function is None or isinstance(sample.test_function, str)
    assert sample.commit_sha is None or isinstance(sample.commit_sha, str)
    assert sample.status in {
        "OK",
        "NO_COMMIT",
        "NO_TEST",
        "UNVERIFIED",
        "PLANNING_ONLY",
    }


def test_traceability_renders_to_markdown_table() -> None:
    """TMX-3500 / AC-3 supplemental — the matrix can render itself to a
    GitHub-flavoured markdown table for embedding in pack documents.
    """
    from regulatory_pack.generators.traceability import build_matrix

    matrix = build_matrix(repo_root=REPO_ROOT)

    rendered = matrix.to_markdown_table()
    assert rendered.startswith("|")
    # Header line + separator + at least one data row.
    assert rendered.count("\n") >= 2
    # The columns expected.
    assert "Ticket" in rendered
    assert "AC" in rendered
    assert "Status" in rendered


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
