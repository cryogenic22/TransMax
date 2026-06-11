"""
TMX-3802 — CJK sentence segmenter (Japanese / Chinese).

The Latin RegexSegmenter keys off `[.!?]+\\s+` (terminator + whitespace). CJK
text carries NO whitespace between sentences and ends them with 。！？, so the
Latin segmenter never splits a CJK paragraph — it collapses into one giant
segment that the LLM later truncates, dropping dosing/safety content (A3).

These tests prove the CJK segmenter splits on ideographic terminators, keeps
decimals intact, and that the Latin path is unchanged.
"""

from app.services.segmenter import get_segmenter, CJKSegmenter, RegexSegmenter


def test_factory_routes_cjk_codes_to_cjk_segmenter():
    for code in ("ja", "zh", "zh-cn", "zh-tw"):
        assert isinstance(get_segmenter(code), CJKSegmenter), code
    # Korean and English stay on the Latin segmenter.
    assert isinstance(get_segmenter("ko"), RegexSegmenter)
    assert isinstance(get_segmenter("en"), RegexSegmenter)


def test_japanese_splits_on_ideographic_full_stop():
    seg = get_segmenter("ja")
    out = seg.segment("1日2回服用してください。5.5 mgを超えないこと。")
    # Two sentences — the Latin segmenter would have produced ONE.
    assert len(out) == 2, out
    assert out[0].endswith("。")
    # The 5.5 decimal must survive un-split.
    assert "5.5" in out[1]


def test_chinese_splits_on_full_stop_and_exclamation():
    seg = get_segmenter("zh")
    out = seg.segment("每日两次。请勿超过5.5毫克！")
    assert len(out) == 2, out
    assert "5.5" in out[1]


def test_cjk_decimal_not_split():
    seg = get_segmenter("ja")
    # A single sentence containing a decimal dose -> stays one segment.
    out = seg.segment("用量は5.5 mgです。")
    assert len(out) == 1, out


def test_cjk_empty_input():
    seg = get_segmenter("ja")
    assert seg.segment("") == []
    assert seg.segment("   ") == []


def test_latin_segmenter_unaffected():
    seg = get_segmenter("en")
    out = seg.segment("Take 5.5 mg b.i.d. Dr. Smith said hi.")
    assert out == ["Take 5.5 mg b.i.d.", "Dr. Smith said hi."], out
