"""TMX-TERMLOCK-WB + TMX-3400-lite.

TMX-TERMLOCK-WB: forbidden-term detection must be word-boundary aware — a
forbidden term must not false-fire inside a larger word (e.g. "ace" in
"surface") while still catching the standalone term and punctuated phrases.

TMX-3400-lite: semantic_drift was extracted to its own module; the function is
importable directly and still returns None when uncomputable.
"""
from __future__ import annotations

from app.services.quality_gate import QualityGateService


def _forbidden_fired(defects) -> bool:
    return any("Forbidden term" in str(d) for d in defects)


def test_forbidden_term_does_not_match_subword() -> None:
    qg = QualityGateService()
    c = {"forbidden_terms": [{"term": "ace"}]}
    defects = qg.check_segment("source", "the surface is smooth", c, "en")
    assert not _forbidden_fired(defects), "'ace' must not fire inside 'surface'"


def test_forbidden_term_matches_standalone_word() -> None:
    qg = QualityGateService()
    c = {"forbidden_terms": [{"term": "ace"}]}
    defects = qg.check_segment("source", "the ace of spades", c, "en")
    assert _forbidden_fired(defects), "standalone 'ace' must fire"


def test_forbidden_term_case_insensitive() -> None:
    qg = QualityGateService()
    c = {"forbidden_terms": [{"term": "Placebo"}]}
    defects = qg.check_segment("source", "given a PLACEBO daily", c, "en")
    assert _forbidden_fired(defects)


def test_semantic_drift_module_importable_and_none_without_key(monkeypatch) -> None:
    from app.core import config
    from app.services.semantic_drift import calculate_semantic_drift

    monkeypatch.setattr(config.settings, "openai_api_key", "")
    assert calculate_semantic_drift("hola", "hello") is None
