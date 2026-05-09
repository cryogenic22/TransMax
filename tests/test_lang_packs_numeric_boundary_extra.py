r"""
TMX-3410-fix — boundary cases the original TMX-3410 sweep missed.

The first cut used `\b\d+\b`. Python 3 `\b` only fires between `\w` and
non-`\w`, and CJK ideographs / ASCII letters are both `\w`. So `\b\d+\b`
silently dropped:
  - canonical numbers next to CJK chars (e.g. 服用500毫克)
  - letter-glued source numbers (e.g. 10mg never extracted at all)

The fix uses digit-only boundary `(?<!\d)X(?!\d)`. These tests lock in
the corrected semantics.
"""
from __future__ import annotations

import pytest

from app.services.language_packs.chinese import ChinesePack
from app.services.language_packs.japanese import JapanesePack
from app.services.language_packs.korean import KoreanPack
from app.services.language_packs.spanish import SpanishPack
from app.services.language_packs.factory import GenericLanguagePack


# ── CJK adjacency: number-present canonical match must NOT fire ─────────


def test_chinese_canonical_number_adjacent_to_ideograph_does_not_fire() -> None:
    """Source 500 mg, target 服用500毫克. Number IS present; must not flag."""
    violations = ChinesePack().check_numbers(
        "Take 500 mg.", "服用500毫克。"
    )
    assert violations == [], f"got false-positive: {violations!r}"


def test_japanese_canonical_number_adjacent_to_ideograph_does_not_fire() -> None:
    """Source 200 mg, target 200を服用. Number IS present (Western glued to JP)."""
    violations = JapanesePack().check_numbers(
        "Take 200 mg.", "200を服用してください。"
    )
    assert violations == [], f"got false-positive: {violations!r}"


def test_korean_canonical_number_adjacent_to_hangul_does_not_fire() -> None:
    """Source 10 mg, target 10mg을 복용. Hangul-adjacent digits."""
    violations = KoreanPack().check_numbers(
        "Take 10 mg.", "10mg을 복용하십시오."
    )
    assert violations == [], f"got false-positive: {violations!r}"


# ── CJK adjacency: tamper must still fire ───────────────────────────────


def test_chinese_tamper_500_to_50_still_fires() -> None:
    violations = ChinesePack().check_numbers(
        "Take 500 mg.", "服用50毫克。"
    )
    assert violations, "tamper missed: 500→50 inside Chinese should flag"


def test_japanese_tamper_200_to_20_still_fires() -> None:
    violations = JapanesePack().check_numbers(
        "Take 200 mg.", "20mgを服用してください。"
    )
    assert violations, "tamper missed: 200→20 inside Japanese should flag"


# ── Letter-glued digits: source-side extraction must still see the digit ─


def test_letter_glued_digit_extracted_from_source_japanese() -> None:
    """`10mg` source → `100mg` target must flag (10 is missing in 100mg)."""
    violations = JapanesePack().check_numbers(
        "Take 10mg.", "100mgを服用。"
    )
    assert violations, "letter-glued tamper missed: 10mg→100mg in Japanese"


def test_letter_glued_digit_extracted_from_source_generic() -> None:
    violations = GenericLanguagePack("nl").check_numbers(
        "Take 10mg.", "100mg innemen."
    )
    assert violations, "letter-glued tamper missed: 10mg→100mg generic"


def test_letter_glued_canonical_does_not_fire() -> None:
    """`10mg` source → `10mg` target must NOT flag."""
    violations = GenericLanguagePack("nl").check_numbers(
        "Take 10mg.", "10mg innemen."
    )
    assert violations == [], f"got false-positive: {violations!r}"


# ── Mixed: letter-glued + CJK ──────────────────────────────────────────


def test_letter_glued_digit_in_cjk_target_canonical() -> None:
    violations = ChinesePack().check_numbers(
        "Take 10mg.", "服用10mg药物。"
    )
    assert violations == [], f"got false-positive: {violations!r}"


def test_letter_glued_digit_in_cjk_target_tamper() -> None:
    violations = ChinesePack().check_numbers(
        "Take 10mg.", "服用100mg药物。"
    )
    assert violations, "tamper missed: 10mg→100mg in Chinese"


# ── Decimal-comma still works on letter-glued case (Spanish) ────────────


def test_spanish_decimal_comma_letter_glued_canonical() -> None:
    """Spanish 1.5ml source → 1,5ml target (no space)."""
    violations = SpanishPack().check_numbers(
        "Use 1.5ml.", "Usar 1,5ml."
    )
    assert violations == [], f"got false-positive: {violations!r}"
