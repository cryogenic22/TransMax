"""TMX-OMIT-2 — over-long segments are sub-split before the LLM (no truncation).

Root cause of the dropped NEJM author list: the whole ~1500-char byline was one
segment fed to the LLM, which truncated it. The cap splits such blocks so the
model sees digestible pieces; normal prose is untouched; no content is lost.
"""
from __future__ import annotations

from app.services.segmenter import MAX_SEGMENT_CHARS, get_segmenter

SEG = get_segmenter("en")


def _author_block(n: int) -> str:
    # A long comma-separated author list with no sentence boundaries.
    return ", ".join(f"Author Name{i}, M.D." for i in range(n))


def test_overlong_segment_is_split():
    block = _author_block(120)  # well over MAX_SEGMENT_CHARS
    assert len(block) > MAX_SEGMENT_CHARS
    out = SEG.segment(block)
    assert len(out) > 1, "an over-long block must be sub-split"
    assert all(len(s) <= MAX_SEGMENT_CHARS for s in out), [len(s) for s in out]


def test_split_loses_no_content():
    block = _author_block(120)
    out = SEG.segment(block)
    # Rejoining covers every author — nothing dropped (the whole point vs the
    # LLM truncation that dropped ~90%).
    joined = " ".join(out)
    for i in range(120):
        assert f"Name{i}" in joined


def test_normal_sentence_not_split():
    s = "Safe and effective vaccines are urgently needed to control the pandemic."
    assert SEG.segment(s) == [s]


def test_short_byline_stays_whole():
    # Regression guard for TMX-3801: a short byline (< cap) is still one segment.
    byline = "Fernando P. Polack, M.D., Stephen J. Thomas, M.D., Nicholas Kitchin, M.D."
    assert len(byline) < MAX_SEGMENT_CHARS
    assert SEG.segment(byline) == [byline]


def test_hard_wrap_when_no_clause_boundary():
    # A single very long clause with no ; , : still gets wrapped (not one giant seg).
    s = "word " * 400  # ~2000 chars, no clause punctuation
    out = SEG.segment(s.strip())
    assert all(len(x) <= MAX_SEGMENT_CHARS for x in out)
    assert len(out) > 1
