"""
TMX-3410 — Cross-pack `check_numbers` word-boundary regression guard.

Every language pack must use word-bounded matching (not Python `in` substring
containment) so order-of-magnitude dose tampering can't slip through gates.

Discovered via TMX-3408 / eval `number_001`. The same substring-`in` defect
was present in 7 other packs (German, French, Portuguese, Korean, Chinese,
Japanese, default GenericLanguagePack).

The fix consolidated word-bounded matching into
`BaseLanguagePack._find_missing_numbers`. Each pack's `check_numbers` now
delegates. These tests fail fast if any future pack reintroduces substring
containment, even by accident.
"""
from __future__ import annotations

import pytest

from app.services.language_packs.spanish import SpanishPack
from app.services.language_packs.german import GermanPack
from app.services.language_packs.french import FrenchPack
from app.services.language_packs.portuguese import PortuguesePack
from app.services.language_packs.korean import KoreanPack
from app.services.language_packs.chinese import ChinesePack
from app.services.language_packs.japanese import JapanesePack
from app.services.language_packs.factory import GenericLanguagePack


# (pack_factory, label) — every pack we ship `check_numbers` for. Adding a
# new pack to this list is the developer's signal to also confirm
# `_find_missing_numbers` is wired in.
PACKS = [
    (SpanishPack, "spanish"),
    (GermanPack, "german"),
    (FrenchPack, "french"),
    (PortuguesePack, "portuguese"),
    (KoreanPack, "korean"),
    (ChinesePack, "chinese"),
    (JapanesePack, "japanese"),
    (GenericLanguagePack, "generic"),
]


@pytest.mark.parametrize("pack_cls,label", PACKS)
def test_digit_prefix_tamper_fires_for_every_pack(pack_cls, label) -> None:
    """`50` must NOT be considered preserved when target only contains `250`."""
    pack = pack_cls()
    violations = pack.check_numbers(
        "Maximum dose is 50 mg per day.",
        "Target text 250 mg per day.",
    )
    assert violations, (
        f"[{label}] expected number_mismatch on 50→250 tamper; got {violations!r}. "
        "This means substring-`in` matching has been reintroduced — see TMX-3410."
    )


@pytest.mark.parametrize("pack_cls,label", PACKS)
def test_digit_suffix_tamper_fires_for_every_pack(pack_cls, label) -> None:
    """`5` must NOT be considered preserved when target only contains `15`."""
    pack = pack_cls()
    violations = pack.check_numbers(
        "Take 5 tablets daily.",
        "15 tablets daily.",
    )
    assert violations, f"[{label}] expected violation on 5→15 tamper; got {violations!r}"


@pytest.mark.parametrize("pack_cls,label", PACKS)
def test_canonical_match_does_not_fire_for_every_pack(pack_cls, label) -> None:
    """Identical numbers in source and target must NOT trigger a violation."""
    pack = pack_cls()
    violations = pack.check_numbers(
        "Take 200 mg every 8 hours.",
        "Same 200 mg every 8 hours.",
    )
    assert violations == [], (
        f"[{label}] canonical numbers should not trigger; got {violations!r}"
    )


# Pack-specific tests for special numeric handling.

def test_japanese_full_width_digits_preserved() -> None:
    """Japanese pack must accept full-width zenkaku digits as canonical."""
    pack = JapanesePack()
    violations = pack.check_numbers(
        "Take 200 mg.",
        "２００ mg を服用してください。",
    )
    assert violations == [], (
        f"Japanese full-width digit translation regressed; got {violations!r}"
    )


def test_japanese_full_width_tamper_still_fires() -> None:
    """Tamper must still fire even via full-width digits."""
    pack = JapanesePack()
    violations = pack.check_numbers(
        "Take 200 mg.",
        "２０ mg を服用してください。",  # 200 -> 20 (full-width)
    )
    assert violations, f"Japanese full-width tamper missed; got {violations!r}"


def test_spanish_decimal_comma_canonical() -> None:
    """Spanish 5.5 -> 5,5 must NOT fire."""
    pack = SpanishPack()
    violations = pack.check_numbers(
        "Administer 5.5 ml every 6 hours.",
        "Administrar 5,5 ml cada 6 horas.",
    )
    assert violations == [], f"Spanish decimal-swap regressed; got {violations!r}"


def test_german_decimal_comma_canonical() -> None:
    """German 5.5 -> 5,5 must NOT fire."""
    pack = GermanPack()
    violations = pack.check_numbers(
        "Use 1.5 ml.",
        "1,5 ml verwenden.",
    )
    assert violations == [], f"German decimal-swap regressed; got {violations!r}"


def test_french_decimal_comma_canonical() -> None:
    """French 1.5 -> 1,5 must NOT fire."""
    pack = FrenchPack()
    violations = pack.check_numbers(
        "Use 1.5 ml.",
        "Utiliser 1,5 ml.",
    )
    assert violations == [], f"French decimal-swap regressed; got {violations!r}"


def test_portuguese_decimal_comma_canonical() -> None:
    """Portuguese 1.5 -> 1,5 must NOT fire."""
    pack = PortuguesePack()
    violations = pack.check_numbers(
        "Use 1.5 ml.",
        "Use 1,5 ml.",
    )
    assert violations == [], f"Portuguese decimal-swap regressed; got {violations!r}"


def test_korean_does_not_accept_decimal_swap() -> None:
    """Korean does not have comma-decimal convention — confirm we didn't accidentally enable it."""
    pack = KoreanPack()
    # If we wrongly enabled decimal-swap for Korean, this would pass silently.
    # Korean keeps Western dot-decimal; "1.5" != "1,5".
    violations = pack.check_numbers(
        "Take 1.5 ml.",
        "1,5 ml 복용하십시오.",
    )
    assert violations, (
        "Korean should not accept comma-decimal swap; if this passed, the helper config drifted."
    )


def test_chinese_does_not_accept_decimal_swap() -> None:
    pack = ChinesePack()
    violations = pack.check_numbers(
        "Take 1.5 ml.",
        "1,5 ml.",
    )
    assert violations, (
        "Chinese should not accept comma-decimal swap; if this passed, the helper config drifted."
    )
