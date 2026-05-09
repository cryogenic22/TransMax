"""
TMX-3411 — Cross-language frequency-pattern coverage.

`QualityGateService.check_frequency`'s FREQ_PATTERNS dict was extended
in TMX-3409 (Spanish) and TMX-3411 (German, Italian, Portuguese, Korean,
Chinese, Japanese, Arabic). These tests guard against:

  - false-positive FREQUENCY_MISMATCH on canonical translations
  - regressions on EN/FR/ES patterns landed earlier
  - tamper detection still working in two of the new languages
"""
from __future__ import annotations

from app.services.quality_gate import QualityGateService
from app.core.defect_taxonomy import Defect


def _categories(defects: list[Defect]) -> set[str]:
    return {d.category.value for d in defects}


# ── Canonical translations — must NOT fire ─────────────────────────────


def test_german_canonical_twice_daily_does_not_fire() -> None:
    qg = QualityGateService()
    defects = qg.check_frequency(
        source_text="Take twice daily.",
        target_text="Zweimal täglich einnehmen.",
    )
    assert defects == [], f"Expected no defects for German canonical; got {defects!r}"


def test_italian_canonical_twice_daily_does_not_fire() -> None:
    qg = QualityGateService()
    defects = qg.check_frequency(
        source_text="Take twice daily.",
        target_text="Assumere due volte al giorno.",
    )
    assert defects == [], f"Expected no defects for Italian canonical; got {defects!r}"


def test_portuguese_canonical_three_times_daily_does_not_fire() -> None:
    qg = QualityGateService()
    defects = qg.check_frequency(
        source_text="Take three times daily.",
        target_text="Tomar três vezes ao dia.",
    )
    assert defects == [], f"Expected no defects for Portuguese canonical; got {defects!r}"


def test_portuguese_alt_phrasing_does_not_fire() -> None:
    """`uma vez por dia` should match alongside `uma vez ao dia`."""
    qg = QualityGateService()
    defects = qg.check_frequency(
        source_text="Take once daily.",
        target_text="Tomar uma vez por dia.",
    )
    assert defects == [], f"Expected no defects for Portuguese alt-phrasing; got {defects!r}"


def test_korean_canonical_twice_daily_does_not_fire() -> None:
    qg = QualityGateService()
    defects = qg.check_frequency(
        source_text="Take twice daily.",
        target_text="1일 2회 복용하십시오.",
    )
    assert defects == [], f"Expected no defects for Korean canonical; got {defects!r}"


def test_korean_native_ordinal_does_not_fire() -> None:
    qg = QualityGateService()
    defects = qg.check_frequency(
        source_text="Take three times daily.",
        target_text="하루 세 번 복용하십시오.",
    )
    assert defects == [], f"Expected no defects for Korean ordinal; got {defects!r}"


def test_chinese_simplified_canonical_does_not_fire() -> None:
    qg = QualityGateService()
    defects = qg.check_frequency(
        source_text="Take twice daily.",
        target_text="每日两次服用。",
    )
    assert defects == [], f"Expected no defects for Chinese (simplified) canonical; got {defects!r}"


def test_chinese_alt_phrasing_does_not_fire() -> None:
    qg = QualityGateService()
    defects = qg.check_frequency(
        source_text="Take three times daily.",
        target_text="一天三次。",
    )
    assert defects == [], f"Expected no defects for Chinese alt-phrasing; got {defects!r}"


def test_japanese_canonical_kanji_does_not_fire() -> None:
    qg = QualityGateService()
    defects = qg.check_frequency(
        source_text="Take twice daily.",
        target_text="一日二回服用してください。",
    )
    assert defects == [], f"Expected no defects for Japanese kanji canonical; got {defects!r}"


def test_japanese_canonical_digit_does_not_fire() -> None:
    qg = QualityGateService()
    defects = qg.check_frequency(
        source_text="Take twice daily.",
        target_text="1日2回服用してください。",
    )
    assert defects == [], f"Expected no defects for Japanese digit canonical; got {defects!r}"


def test_arabic_canonical_twice_daily_does_not_fire() -> None:
    qg = QualityGateService()
    defects = qg.check_frequency(
        source_text="Take twice daily.",
        target_text="مرتين في اليوم.",
    )
    assert defects == [], f"Expected no defects for Arabic canonical; got {defects!r}"


def test_arabic_alt_phrasing_does_not_fire() -> None:
    qg = QualityGateService()
    defects = qg.check_frequency(
        source_text="Take twice daily.",
        target_text="مرتين يوميا.",
    )
    assert defects == [], f"Expected no defects for Arabic alt-phrasing; got {defects!r}"


# ── Tamper detection still works ───────────────────────────────────────


def test_german_frequency_tamper_fires() -> None:
    """twice daily -> einmal täglich (1×/d) must fire."""
    qg = QualityGateService()
    defects = qg.check_frequency(
        source_text="Take twice daily.",
        target_text="Einmal täglich einnehmen.",
    )
    assert "FREQUENCY_MISMATCH" in _categories(defects), (
        f"Expected FREQUENCY_MISMATCH on German tamper; got {defects!r}"
    )


def test_japanese_frequency_tamper_fires() -> None:
    """three times daily -> 1日1回 (1×/d) must fire."""
    qg = QualityGateService()
    defects = qg.check_frequency(
        source_text="Take three times daily.",
        target_text="1日1回服用してください。",
    )
    assert "FREQUENCY_MISMATCH" in _categories(defects), (
        f"Expected FREQUENCY_MISMATCH on Japanese tamper; got {defects!r}"
    )


# ── Existing EN/FR/ES patterns must NOT regress ────────────────────────


def test_english_canonical_still_passes() -> None:
    qg = QualityGateService()
    defects = qg.check_frequency(
        source_text="Take twice daily.",
        target_text="Take twice daily.",
    )
    assert defects == [], f"English no-regression check failed; got {defects!r}"


def test_french_canonical_still_passes() -> None:
    qg = QualityGateService()
    defects = qg.check_frequency(
        source_text="Take twice daily.",
        target_text="Prendre deux fois par jour.",
    )
    assert defects == [], f"French no-regression check failed; got {defects!r}"


def test_spanish_canonical_still_passes() -> None:
    qg = QualityGateService()
    defects = qg.check_frequency(
        source_text="Take twice daily.",
        target_text="Tomar dos veces al día.",
    )
    assert defects == [], f"Spanish no-regression check failed; got {defects!r}"
