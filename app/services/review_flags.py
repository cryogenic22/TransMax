"""Translation review-flag summarizer (TMX-CONF-1).

Turns deterministic-gate violations + a confidence score into a concrete,
user-facing list of *where the issues are* — so the surface stops reporting a
bland "all OK". Previously a 90+ score showed no recommendations and read as
perfect even with real defects; this lowers the bar: ANY violation, or a
confidence below the review threshold, surfaces a specific issue and sets
``needs_review``. When nothing is flagged we still say human sign-off is
required (A3 — never imply a regulated translation is "perfect/done").
"""
from __future__ import annotations

# Below this confidence (0–100) a segment is flagged for review even with no
# hard violation. Pharma policy already routes high-confidence work to review;
# this makes the *low* end explicit + visible.
LOW_CONFIDENCE_THRESHOLD = 85.0

_GxP_NOTE = "No automated issues found — human sign-off still required (GxP policy)."


def summarize_issues(
    violations,
    confidence_score: float | None = None,
    band: str | None = None,
    threshold: float = LOW_CONFIDENCE_THRESHOLD,
) -> dict:
    """Summarize a translation's reviewable issues.

    Args:
        violations: list of serialized defect dicts (category/severity/message,
            optionally segment_id) from the quality gate.
        confidence_score: 0–100 confidence, if available.
        band: confidence band label (e.g. "Very High"), if available.

    Returns a dict: ``needs_review`` (bool), ``issue_count`` (int),
    ``issues`` (list of {category, severity, message, segment_id}), and a
    human-readable ``note``.
    """
    issues: list[dict] = []
    for v in violations or []:
        issues.append({
            "category": v.get("category"),
            "severity": v.get("severity"),
            "message": v.get("message"),
            "segment_id": v.get("segment_id"),
        })

    if confidence_score is not None and confidence_score < threshold:
        issues.append({
            "category": "LOW_CONFIDENCE",
            "severity": "MAJOR",
            "message": (
                f"Confidence {confidence_score:.0f} is below the review "
                f"threshold {threshold:.0f}"
                + (f" (band: {band})" if band else "")
                + " — verify this translation."
            ),
            "segment_id": None,
        })

    needs_review = bool(issues)
    return {
        "needs_review": needs_review,
        "issue_count": len(issues),
        "issues": issues,
        "note": "" if needs_review else _GxP_NOTE,
    }


def needs_review_segment_ids(units, threshold: float = LOW_CONFIDENCE_THRESHOLD) -> list[str]:
    """Segment ids that warrant review: any with a gate violation OR a
    confidence below ``threshold``. Used to point reviewers at exact segments
    in a document translation."""
    flagged: list[str] = []
    for u in units:
        gr = getattr(u, "gate_results", {}) or {}
        low_conf = (getattr(u, "confidence_score", None) or 0.0) and u.confidence_score < threshold
        if gr.get("violations") or low_conf:
            flagged.append(u.segment_id)
    return flagged
