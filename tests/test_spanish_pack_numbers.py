"""
TMX-3408 — Spanish numeric gate must use word-boundary matching.

Regression guards for `SpanishPack.check_numbers`. The pre-fix implementation
used Python's `in` operator (substring containment), which silently passes
order-of-magnitude tampering like 10 mg -> 100 mg because "10" is a substring
of "100". This test set fails fast if anyone reintroduces substring matching.

Cross-reference: tests/evals/data/en_es/critical_safety.jsonl case `number_001`.
"""
from __future__ import annotations

from app.services.language_packs.spanish import SpanishPack


def _categories(violations: list[dict[str, str]]) -> set[str]:
    return {v["type"] for v in violations}


def test_digit_prefix_tamper_fires_number_mismatch() -> None:
    # 10 mg -> 100 mg: "10" is a substring of "100" but not a word-bounded match.
    pack = SpanishPack()
    violations = pack.check_numbers(
        source="Take 10 mg twice daily.",
        target="Tome 100 mg dos veces al dia.",
    )
    assert "number_mismatch" in _categories(violations), (
        f"Expected number_mismatch; got {violations!r}"
    )


def test_digit_suffix_tamper_fires_number_mismatch() -> None:
    # 50 mg -> 250 mg: "50" is a suffix of "250" — substring `in` would pass.
    pack = SpanishPack()
    violations = pack.check_numbers(
        source="Maximum daily dose is 50 mg.",
        target="La dosis maxima diaria es 250 mg.",
    )
    assert "number_mismatch" in _categories(violations)


def test_dot_to_comma_decimal_translation_passes() -> None:
    # Spanish convention: 5.5 -> 5,5. Should NOT flag.
    pack = SpanishPack()
    violations = pack.check_numbers(
        source="Administer 5.5 ml every 6 hours.",
        target="Administrar 5,5 ml cada 6 horas.",
    )
    assert violations == [], f"Expected no violations; got {violations!r}"


def test_comma_to_dot_decimal_translation_passes() -> None:
    # Reverse direction: source already comma-formatted, target with dot.
    pack = SpanishPack()
    violations = pack.check_numbers(
        source="Volumen: 2,5 ml",
        target="Volume: 2.5 ml",
    )
    assert violations == [], f"Expected no violations; got {violations!r}"


def test_missing_number_fires() -> None:
    pack = SpanishPack()
    violations = pack.check_numbers(
        source="Take 10 mg every 8 hours.",
        target="Tome el medicamento cada 8 horas.",  # 10 missing entirely
    )
    assert "number_mismatch" in _categories(violations)


def test_exact_match_passes() -> None:
    pack = SpanishPack()
    violations = pack.check_numbers(
        source="Maximum daily dose is 200 mg.",
        target="La dosis diaria maxima es de 200 mg.",
    )
    assert violations == [], f"Expected no violations; got {violations!r}"


def test_multiple_numbers_partial_match_fires_only_for_missing() -> None:
    # 10 mg every 6 hours -> 10 mg every 4 hours. "10" preserved, "6" missing.
    pack = SpanishPack()
    violations = pack.check_numbers(
        source="Take 10 mg every 6 hours.",
        target="Tome 10 mg cada 4 horas.",
    )
    messages = [v["message"] for v in violations]
    assert any("6" in m for m in messages), f"Expected violation for '6'; got {messages!r}"
    assert not any("10" in m for m in messages), (
        f"Did not expect violation for '10' (it's preserved); got {messages!r}"
    )
