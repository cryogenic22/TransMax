"""
TMX-3409 — `check_frequency` must recognise Spanish frequency patterns,
accent-folded, so canonical translations don't trip a false-positive
FREQUENCY_MISMATCH.

Cross-reference: tests/evals/data/en_es/critical_safety.jsonl case `good_001`.
"""
from __future__ import annotations

from app.services.quality_gate import QualityGateService
from app.core.defect_taxonomy import Defect


def _categories(defects: list[Defect]) -> set[str]:
    # check_frequency returns Defect objects directly; serialisation to dict
    # happens later in check_segment.
    return {d.category.value for d in defects}


def test_canonical_spanish_twice_daily_does_not_fire() -> None:
    qg = QualityGateService()
    defects = qg.check_frequency(
        source_text="Take one tablet by mouth twice daily with food.",
        target_text="Tome un comprimido por via oral dos veces al dia con alimentos.",
    )
    assert defects == [], f"Expected no defects; got {defects!r}"


def test_canonical_spanish_with_accents_does_not_fire() -> None:
    # Real Spanish uses "día" with accent; fold should match against unaccented
    # pattern "dos veces al dia".
    qg = QualityGateService()
    defects = qg.check_frequency(
        source_text="Take this twice daily.",
        target_text="Tome esto dos veces al día.",
    )
    assert defects == [], f"Expected no defects; got {defects!r}"


def test_spanish_frequency_tamper_fires() -> None:
    # twice daily -> once daily ("una vez al día") in Spanish must fire.
    qg = QualityGateService()
    defects = qg.check_frequency(
        source_text="Take one tablet twice daily.",
        target_text="Tome un comprimido una vez al día.",
    )
    assert "FREQUENCY_MISMATCH" in _categories(defects), (
        f"Expected FREQUENCY_MISMATCH; got {defects!r}"
    )


def test_spanish_three_times_daily_canonical() -> None:
    qg = QualityGateService()
    defects = qg.check_frequency(
        source_text="Take three times daily.",
        target_text="Tome tres veces al día.",
    )
    assert defects == [], f"Expected no defects; got {defects!r}"


def test_spanish_four_times_daily_canonical() -> None:
    qg = QualityGateService()
    defects = qg.check_frequency(
        source_text="Administer four times daily.",
        target_text="Administrar cuatro veces al día.",
    )
    assert defects == [], f"Expected no defects; got {defects!r}"


def test_french_canonical_still_passes_no_regression() -> None:
    # Make sure adding Spanish + accent-fold didn't break French.
    qg = QualityGateService()
    defects = qg.check_frequency(
        source_text="Take twice daily.",
        target_text="Prendre deux fois par jour.",
    )
    assert defects == [], f"Expected no defects; got {defects!r}"


def test_english_abbreviation_bid_still_matches_no_regression() -> None:
    qg = QualityGateService()
    defects = qg.check_frequency(
        source_text="Take BID.",
        target_text="Tome BID.",
    )
    assert defects == [], f"Expected no defects (bid abbreviation match); got {defects!r}"
