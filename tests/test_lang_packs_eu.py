"""
TMX-LANG-EU1/EU2 — deep language packs for EMA official languages.

These eight languages (nl, sv, da, fi, pl, el, cs, hu) were previously served
by the GenericLanguagePack (universal gates only). They are required across EMA
QRD package leaflets, so each now carries real negation + numeric gates.

Tests prove two things per language:
  1. The factory resolves the BCP-47 code to the dedicated pack (not Generic).
  2. The negation gate fires when the source negates but the target does not,
     and stays silent when the target carries a correct negation marker.
  3. The numeric gate catches a dropped dose and accepts a decimal-comma swap.
"""

from app.services.language_packs.factory import LanguagePackFactory
from app.services.language_packs.factory import GenericLanguagePack

# code -> (expected pack class name, a real target negation marker, a correctly
# translated negated sentence that MUST NOT raise a negation violation)
EU_PACKS = {
    "nl": ("DutchPack", "niet"),
    "sv": ("SwedishPack", "inte"),
    "da": ("DanishPack", "ikke"),
    "fi": ("FinnishPack", "ei"),
    "pl": ("PolishPack", "nie"),
    "el": ("GreekPack", "δεν"),
    "cs": ("CzechPack", "ne"),
    "hu": ("HungarianPack", "nem"),
}


def test_factory_resolves_dedicated_packs_not_generic():
    for code, (cls_name, _marker) in EU_PACKS.items():
        pack = LanguagePackFactory.get_pack(code)
        assert type(pack).__name__ == cls_name, (code, type(pack).__name__)
        assert pack.code == code
        assert not isinstance(pack, GenericLanguagePack), code


def test_negation_fires_when_target_drops_negation():
    # Source negates ("Do not exceed"); target has NO negation marker -> flag.
    for code, (_cls, marker) in EU_PACKS.items():
        pack = LanguagePackFactory.get_pack(code)
        violations = pack.check_negation(
            "Do not exceed the stated dose", "exceed the dose"
        )
        assert violations, f"{code}: expected a negation-flip violation"
        assert any(
            "NEGATION" in v["type"].upper() or "negation" in v["type"].lower()
            for v in violations
        ), (code, violations)


def test_negation_silent_when_target_keeps_marker():
    for code, (_cls, marker) in EU_PACKS.items():
        pack = LanguagePackFactory.get_pack(code)
        # A target carrying the language's negation marker must not be flagged.
        violations = pack.check_negation(
            "Do not exceed the stated dose", f"... {marker} ..."
        )
        assert violations == [], (code, violations)


def test_numbers_catch_dropped_dose():
    for code, (_cls, _marker) in EU_PACKS.items():
        pack = LanguagePackFactory.get_pack(code)
        violations = pack.check_numbers("Take 10 mg twice daily", "Take twice daily")
        assert violations, f"{code}: expected a missing-number violation for dropped 10"


def test_numbers_accept_decimal_comma_swap():
    # EU languages use a decimal comma; "5.5" in source == "5,5" in target.
    for code, (_cls, _marker) in EU_PACKS.items():
        pack = LanguagePackFactory.get_pack(code)
        violations = pack.check_numbers("Dose is 5.5 mg", "Dosis 5,5 mg")
        assert violations == [], (code, violations)
