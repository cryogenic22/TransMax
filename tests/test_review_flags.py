"""TMX-CONF-1 — review-flag summarizer: surface issues, stop saying 'all OK'."""
from __future__ import annotations

from types import SimpleNamespace

from app.services.review_flags import (
    LOW_CONFIDENCE_THRESHOLD,
    needs_review_segment_ids,
    summarize_issues,
)


def test_clean_translation_still_requires_signoff():
    """No violations + high confidence ⇒ not flagged, but NOT 'perfect'."""
    s = summarize_issues([], confidence_score=98.0, band="Very High")
    assert s["needs_review"] is False
    assert s["issues"] == []
    assert "human sign-off" in s["note"]  # never imply done/perfect (A3)


def test_violations_become_concrete_issues():
    violations = [
        {"category": "NUMERIC_MISMATCH", "severity": "CRITICAL", "message": "10mg -> 100mg", "segment_id": "3"},
        {"category": "TERMINOLOGY", "severity": "MAJOR", "message": "glossary term missing", "segment_id": "7"},
    ]
    s = summarize_issues(violations, confidence_score=99.0, band="Very High")
    assert s["needs_review"] is True
    assert s["issue_count"] == 2
    cats = {i["category"] for i in s["issues"]}
    assert cats == {"NUMERIC_MISMATCH", "TERMINOLOGY"}
    assert s["issues"][0]["segment_id"] == "3"


def test_low_confidence_is_flagged_even_without_violations():
    s = summarize_issues([], confidence_score=70.0, band="Medium")
    assert s["needs_review"] is True
    assert any(i["category"] == "LOW_CONFIDENCE" for i in s["issues"])


def test_at_threshold_not_flagged():
    s = summarize_issues([], confidence_score=LOW_CONFIDENCE_THRESHOLD, band="High")
    assert s["needs_review"] is False


def test_needs_review_segment_ids_flags_violations_and_low_confidence():
    units = [
        SimpleNamespace(segment_id="1", gate_results={"violations": []}, confidence_score=99.0),  # clean
        SimpleNamespace(segment_id="2", gate_results={"violations": [{"category": "X"}]}, confidence_score=99.0),  # violation
        SimpleNamespace(segment_id="3", gate_results={"violations": []}, confidence_score=60.0),  # low conf
    ]
    flagged = needs_review_segment_ids(units)
    assert flagged == ["2", "3"]
