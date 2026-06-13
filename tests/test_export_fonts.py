"""TMX-EXPORT-1 — font resolution + charset honesty.

These assert the *family mapping* and the *coverage-honesty contract*. When a
Unicode TTF (DejaVu) is locatable (dev: via matplotlib), French typography
(œ, em-dash, guillemets) is covered; scripts DejaVu lacks (CJK) are flagged, not
silently mangled. When no TTF is found, base-14 Latin-1 coverage applies.
"""
from app.services.export.fonts import resolve


def test_serif_source_maps_to_serif_family():
    fc = resolve("OTNEJMQuadraat", "Bonjour")
    assert fc.fontname.lower().endswith("serif") or fc.fontname == "tiro"


def test_sans_source_maps_to_sans_family():
    fc = resolve("OTNEJMScalaSansLF", "Bonjour")
    assert "sans" in fc.fontname.lower() or fc.fontname == "helv"


def test_mono_source_maps_to_mono_family():
    fc = resolve("CourierNewPSMT", "code()")
    assert "mono" in fc.fontname.lower() or fc.fontname == "cour"


def test_source_face_is_always_substituted():
    # we never reuse the (subsetted) embedded source face
    assert resolve("OTNEJMQuadraat", "x").substituted is True


def test_french_typography_is_covered():
    # œdème, em-dash, guillemets — outside Latin-1; must be covered (DejaVu) or,
    # if no TTF is present, at least honestly reported.
    fc = resolve("Times", "Réduction — œdème « cœur » à 50 mg")
    if fc.fontfile:               # Unicode TTF located (dev/prod-bundled)
        assert fc.charset_ok is True
    else:                         # base-14 fallback cannot cover it -> flagged
        assert fc.charset_ok is False
        assert "flagged" in fc.reason


def test_unsupported_script_is_flagged_not_mangled():
    fc = resolve("Times", "用法用量 每日一次")   # CJK: DejaVu lacks these glyphs
    assert fc.charset_ok is False
    assert "flag" in fc.reason.lower()
