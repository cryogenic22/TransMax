"""
TMX-3800 — Segmenter contract tests.

Replaces C-11's naive `text.split('.')` with an abbreviation-aware regex
segmenter. These tests guard against:

  - splitting inside pharma abbreviations (Dr., mg., e.g., i.v., b.i.d.)
  - splitting inside decimal numbers (5.5, 0.25)
  - missed sentence boundaries (?, !, end-of-string)
  - empty / whitespace-only input
  - graceful fallback for unknown languages
  - the documented bad baseline (NaiveSplitSegmenter) staying intentionally bad
"""
from __future__ import annotations

import pytest

from app.services.segmenter import (
    NaiveSplitSegmenter,
    RegexSegmenter,
    SegmenterError,
    get_segmenter,
)


# ── Pharma abbreviations ────────────────────────────────────────────────


def test_pharma_titles_not_split() -> None:
    seg = RegexSegmenter()
    out = seg.segment("Dr. Smith prescribed the drug. The patient agreed.")
    assert out == [
        "Dr. Smith prescribed the drug.",
        "The patient agreed.",
    ]


def test_dosing_route_abbreviations_not_split() -> None:
    seg = RegexSegmenter()
    out = seg.segment("Administer i.v. immediately. Then switch to p.o.")
    assert out == [
        "Administer i.v. immediately.",
        "Then switch to p.o.",
    ]


def test_bid_tid_qid_not_split() -> None:
    seg = RegexSegmenter()
    out = seg.segment("Take b.i.d. for 7 days. Then reassess t.i.d. dosing.")
    assert out == [
        "Take b.i.d. for 7 days.",
        "Then reassess t.i.d. dosing.",
    ]


def test_eg_ie_etc_not_split() -> None:
    seg = RegexSegmenter()
    out = seg.segment("Use cautiously, e.g. with food. Avoid stimulants, i.e. caffeine.")
    assert out == [
        "Use cautiously, e.g. with food.",
        "Avoid stimulants, i.e. caffeine.",
    ]


def test_corporate_abbreviations_not_split() -> None:
    seg = RegexSegmenter()
    out = seg.segment("Made by Acme Co. Patient confirmed the brand.")
    assert out == [
        "Made by Acme Co.",
        "Patient confirmed the brand.",
    ]


# ── Decimal numbers ─────────────────────────────────────────────────────


def test_decimal_numbers_not_split() -> None:
    seg = RegexSegmenter()
    out = seg.segment("Administer 5.5 mg per day. Maximum dose is 12.5 mg.")
    assert out == [
        "Administer 5.5 mg per day.",
        "Maximum dose is 12.5 mg.",
    ]


def test_decimal_inside_abbreviation_not_split() -> None:
    seg = RegexSegmenter()
    out = seg.segment("Dr. Lee prescribed 0.25 mg b.i.d. Patient tolerated it.")
    assert out == [
        "Dr. Lee prescribed 0.25 mg b.i.d.",
        "Patient tolerated it.",
    ]


# ── Multiple terminators ────────────────────────────────────────────────


def test_question_mark_terminator() -> None:
    seg = RegexSegmenter()
    out = seg.segment("Did the patient respond? They reported improvement.")
    assert out == [
        "Did the patient respond?",
        "They reported improvement.",
    ]


def test_exclamation_terminator() -> None:
    seg = RegexSegmenter()
    out = seg.segment("Severe reaction! Discontinue immediately.")
    assert out == [
        "Severe reaction!",
        "Discontinue immediately.",
    ]


# ── Edge cases ──────────────────────────────────────────────────────────


def test_empty_string_returns_empty_list() -> None:
    seg = RegexSegmenter()
    assert seg.segment("") == []


def test_whitespace_only_returns_empty_list() -> None:
    seg = RegexSegmenter()
    assert seg.segment("   \n\n   ") == []


def test_single_sentence_no_terminator() -> None:
    seg = RegexSegmenter()
    assert seg.segment("Take this medication") == ["Take this medication"]


def test_single_sentence_with_terminator() -> None:
    seg = RegexSegmenter()
    assert seg.segment("Take this medication.") == ["Take this medication."]


# ── Factory ─────────────────────────────────────────────────────────────


def test_get_segmenter_default_is_regex() -> None:
    seg = get_segmenter()
    assert isinstance(seg, RegexSegmenter)


def test_get_segmenter_unknown_language_falls_back_to_english() -> None:
    seg = get_segmenter("klingon")
    # Falls back to RegexSegmenter (English) — verified by the abbreviation
    # protection still firing on a Klingon-shaped input.
    assert isinstance(seg, RegexSegmenter)
    out = seg.segment("Dr. Smith said hi. Patient agreed.")
    assert out == ["Dr. Smith said hi.", "Patient agreed."]


def test_get_segmenter_bcp47_prefix_match() -> None:
    """`en-US` should resolve to the English segmenter via BCP 47 prefix."""
    seg = get_segmenter("en-US")
    assert isinstance(seg, RegexSegmenter)


# ── NaiveSplitSegmenter — documented bad baseline ──────────────────────


def test_naive_segmenter_stays_intentionally_bad() -> None:
    """
    Regression guard: `NaiveSplitSegmenter` IS the C-11 defect shape preserved
    on purpose so callers can A/B against it. If anyone "improves" it, this
    test fails first — the bad baseline is supposed to be bad.
    """
    naive = NaiveSplitSegmenter()
    # 5.5 mg gets shredded; b.i.d. gets shredded; that's the point.
    out = naive.segment("Take 5.5 mg b.i.d. Patient agreed.")
    # Naive split produces 5+ pieces from 2 sentences.
    assert len(out) >= 4, (
        f"NaiveSplitSegmenter is supposed to be bad — produced too few pieces ({out!r})"
    )


def test_segmenter_error_is_value_error_subclass() -> None:
    """Smoke: SegmenterError is exposed and is the right shape."""
    assert issubclass(SegmenterError, ValueError)
