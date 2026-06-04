"""Document structural-fidelity comparator (FIDELITY-EVAL / E3).

A translated document must come back with the SAME structure as the source —
tables, figures, headings, and run-level formatting intact. The 2026-06 NEJM
manuscript failure (13 tables → 0, figures dropped, every paragraph flattened
to "Normal") is exactly what this module detects.

`structure_fingerprint(doc)` reduces a python-docx Document to a structural
fingerprint; `compare_structure(src, out)` reports what the output LOST vs the
source + a 0–100 fidelity score. `assert_fidelity` is the fail-loud gate (A3)
that a future export step can call to refuse a job that silently drops
structure. Pure + dependency-light (python-docx only).
"""
from __future__ import annotations

from dataclasses import dataclass, field


def _is_heading(style_name: str | None) -> bool:
    if not style_name:
        return False
    s = style_name.strip().lower()
    return s.startswith("heading") or s in {"title", "subtitle"}


def structure_fingerprint(doc) -> dict:
    """Structural fingerprint of a python-docx ``Document``.

    Counts the structure-bearing elements a faithful translation must preserve.
    """
    headings = 0
    bold_runs = 0
    italic_runs = 0
    nonempty_paras = 0
    for p in doc.paragraphs:
        if p.text.strip():
            nonempty_paras += 1
        if _is_heading(p.style.name if p.style else None):
            headings += 1
        for r in p.runs:
            if r.bold:
                bold_runs += 1
            if r.italic:
                italic_runs += 1
    return {
        "paragraphs": nonempty_paras,
        "tables": len(doc.tables),
        "images": len(doc.inline_shapes),
        "headings": headings,
        "bold_runs": bold_runs,
        "italic_runs": italic_runs,
    }


# Each structural dimension contributes to the score; "down means loss".
_DIMENSIONS = ("tables", "images", "headings", "bold_runs", "italic_runs")
# Losing a whole table or figure is far worse than losing one emphasis run.
_WEIGHTS = {"tables": 4.0, "images": 4.0, "headings": 2.0, "bold_runs": 1.0, "italic_runs": 1.0}


@dataclass
class FidelityReport:
    score: float                      # 0–100; 100 = no structural loss
    ok: bool
    losses: list[str] = field(default_factory=list)
    source: dict = field(default_factory=dict)
    output: dict = field(default_factory=dict)


def compare_structure(source: dict, output: dict) -> FidelityReport:
    """Compare two fingerprints; report losses + a weighted fidelity score.

    Only LOSSES count against the score (an output may legitimately add
    paragraphs, e.g. a translated language that's more verbose). A dropped
    table/figure/heading is a loss.
    """
    losses: list[str] = []
    earned = 0.0
    possible = 0.0
    for dim in _DIMENSIONS:
        s = int(source.get(dim, 0))
        o = int(output.get(dim, 0))
        w = _WEIGHTS[dim]
        possible += w * s
        kept = min(o, s)
        earned += w * kept
        if o < s:
            losses.append(f"{dim}: {s} → {o} (lost {s - o})")

    score = 100.0 if possible == 0 else round(100.0 * earned / possible, 1)
    return FidelityReport(
        score=score,
        ok=not losses,
        losses=losses,
        source=dict(source),
        output=dict(output),
    )


# The structural "skeleton" — dimensions a faithful text-replacement export
# must NEVER lose. (bold/italic run counts can legitimately shift when text is
# redistributed across runs, so they are not gate-failing — only the skeleton.)
_SKELETON_DIMS = ("tables", "images", "headings")


def structural_loss(source: dict, output: dict) -> list[str]:
    """Skeleton dimensions where the output has FEWER than the source.

    Empty list ⇒ no structural loss. Used by the export fail-loud gate; ignores
    bold/italic counts (which a correct translation may shift)."""
    return [
        f"{d}: {source.get(d, 0)} → {output.get(d, 0)}"
        for d in _SKELETON_DIMS
        if int(output.get(d, 0)) < int(source.get(d, 0))
    ]


class FidelityError(RuntimeError):
    """Raised by the fail-loud gate when an export lost source structure."""


def assert_fidelity(source_doc, output_doc, *, min_score: float = 100.0):
    """Fail loud (A3) if the output dropped source structure below ``min_score``.

    Intended to wrap the export step so a job that silently drops tables/figures
    (the NEJM failure) is rejected rather than shipped. Returns the report when OK.
    """
    report = compare_structure(
        structure_fingerprint(source_doc), structure_fingerprint(output_doc)
    )
    if report.score < min_score or report.losses:
        raise FidelityError(
            f"Export lost source structure (score={report.score}): "
            f"{'; '.join(report.losses)}. Refusing to ship a structurally "
            f"degraded document (E3 fidelity gate)."
        )
    return report
