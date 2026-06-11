"""
Sentence segmentation for TransMax.

Per plan E5 + addendum A2: deterministic gates depend on segment accuracy.
Naive `text.split('.')` breaks on every period — including those inside
pharma abbreviations (`Dr.`, `mg.`, `e.g.`, `i.v.`) and decimal numbers
(`5.5 mg`). This module replaces that with an abbreviation-aware regex
segmenter; a future loop swaps the backend for NLTK Punkt or spaCy.

Usage:
    from app.services.segmenter import get_segmenter

    segmenter = get_segmenter("en")
    sentences = segmenter.segment("Take 5.5 mg b.i.d. Dr. Smith said e.g. with food.")
    # ['Take 5.5 mg b.i.d.', 'Dr. Smith said e.g. with food.']

See TMX-3800 worksheet; sister tickets:
  - TMX-3801: NLTK / spaCy / pragmatic-segmenter backend integration
  - TMX-3802: CJK segmenters for JA/ZH landed (see CJKSegmenter); KO still
    uses the Latin fallback (modern Korean uses Latin punctuation + spaces).
  - TMX-3803: stable segment IDs (storage-layer changes)
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from typing import List

logger = logging.getLogger(__name__)


class SegmenterError(ValueError):
    """Raised on catastrophic segmenter failure (not on empty input)."""


# Personal titles — almost always followed by a capitalized name. Never
# treated as sentence boundary even when followed by uppercase.
# ("Dr. Smith said hi." -> 1 sentence, not 2.)
_TITLE_ABBREVS: frozenset[str] = frozenset(
    {
        "Dr",
        "Drs",
        "Mr",
        "Mrs",
        "Ms",
        "Prof",
        "St",
        "Sr",
        "Jr",
    }
)

# Academic / professional credentials (TMX-3801). Author bylines in scientific
# manuscripts are dense with these ("Fernando P. Polack, M.D., Stephen J.
# Thomas, M.D., ..."); the trailing dot must not shatter the byline. Stored
# without the trailing dot — `_word_before` returns the token incl. interior
# dots (e.g. "M.D").
_CREDENTIAL_ABBREVS: frozenset[str] = frozenset(
    {
        "M.D",
        "Ph.D",
        "D.M",
        "B.Sc",
        "M.Sc",
        "M.P.H",
        "D.O",
        "R.N",
        "M.S",
        "M.A",
        "B.A",
        "D.D.S",
        "Pharm.D",
        "M.B.A",
        "D.Phil",
    }
)

# Abbreviations whose dot may or may not end a sentence. Heuristic: if the
# next non-whitespace character starts a new sentence (uppercase / digit),
# treat as boundary; otherwise treat as abbreviation continuation. Corporate
# suffixes (Co./Inc./Ltd./Corp.) live here — they CAN end a sentence
# ("Made by Acme Co. Patient agreed.") but only if a new sentence follows.
_CONTEXTUAL_ABBREVS: frozenset[str] = frozenset(
    {
        "e.g",
        "i.e",
        "etc",
        "vs",
        "cf",
        "i.v",
        "i.m",
        "p.o",
        "s.c",
        "b.i.d",
        "t.i.d",
        "q.i.d",
        "q.d",
        "qhs",
        "mg",
        "mcg",
        "kg",
        "mL",
        "ml",
        "L",
        "g",
        "Co",
        "Inc",
        "Ltd",
        "Corp",
        "No",
        "Nr",
        "vol",
        "Vol",
        "ed",
        "Ed",
        "Rd",
        "pp",
        "al",
        "Fig",
        "Eq",
        "Ref",
    }
)

# All abbreviations (case-sensitive) — keys for the WORD-BEFORE lookup.
_ALL_ABBREVS: frozenset[str] = (
    _TITLE_ABBREVS | _CONTEXTUAL_ABBREVS | _CREDENTIAL_ABBREVS
)


# Candidate sentence-boundary regex: terminator(s) followed by whitespace.
# Decimal numbers (e.g. "5.5") are excluded because the . is not followed
# by whitespace, so the candidate regex doesn't even match.
_CANDIDATE_RE = re.compile(r"[.!?]+\s+")

# What we consider "next word starts a new sentence" — uppercase or digit.
_NEXT_STARTS_SENTENCE_RE = re.compile(r"^[A-Z\d]")


def _word_before(text: str, end: int) -> str:
    """
    Return the maximal token ending at index `end` (exclusive of any trailing
    whitespace, exclusive of `end` itself). Tokens are runs of non-whitespace.
    For inputs like 'b.i.d' the returned word includes the interior dots.
    """
    if end <= 0:
        return ""
    start = end
    # Walk backwards over non-whitespace chars.
    while start > 0 and not text[start - 1].isspace():
        start -= 1
    return text[start:end]


def _strip_trailing_terminator(word: str) -> str:
    """`b.i.d` from `b.i.d` (no trailing dot to strip in the matched token)."""
    return word.rstrip(".!?")


# TMX-OMIT-2: cap segment length so an over-long block (e.g. a 1500-char author
# list with no sentence boundaries) is not fed WHOLE to the LLM, which truncates
# it and silently drops content. Generous threshold — normal prose sentences are
# far shorter, so only pathologically-long segments are sub-split.
MAX_SEGMENT_CHARS = 1000
_CLAUSE_RE = re.compile(r"(?<=[;,:])\s+")


def _hard_wrap(text: str, max_chars: int) -> List[str]:
    """Last-resort wrap on whitespace at <= max_chars (no clause boundary left)."""
    out: List[str] = []
    buf = ""
    for w in text.split():
        if buf and len(buf) + 1 + len(w) > max_chars:
            out.append(buf)
            buf = w
        else:
            buf = (buf + " " + w).strip()
    if buf:
        out.append(buf)
    return out or [text]


def _split_long(s: str, max_chars: int) -> List[str]:
    """Split an over-long segment on clause boundaries (`; , :`), then hard-wrap."""
    parts: List[str] = []
    buf = ""
    for chunk in _CLAUSE_RE.split(s):
        if buf and len(buf) + 1 + len(chunk) > max_chars:
            parts.append(buf)
            buf = ""
        if len(chunk) > max_chars:
            if buf:
                parts.append(buf)
                buf = ""
            parts.extend(_hard_wrap(chunk, max_chars))
        else:
            buf = (buf + " " + chunk).strip()
    if buf:
        parts.append(buf)
    return parts


def _cap_length(sentences: List[str], max_chars: int = MAX_SEGMENT_CHARS) -> List[str]:
    """Sub-split any sentence longer than ``max_chars`` (TMX-OMIT-2)."""
    out: List[str] = []
    for s in sentences:
        out.extend([s] if len(s) <= max_chars else _split_long(s, max_chars))
    return out


class BaseSegmenter(ABC):
    """Abstract sentence segmenter."""

    @abstractmethod
    def segment(self, text: str, language: str = "en") -> List[str]: ...


class RegexSegmenter(BaseSegmenter):
    """
    Abbreviation-aware sentence segmenter.

    Algorithm:
      1. Find every `[.!?]+\\s+` candidate boundary in the text.
      2. For each candidate, look at the word ending immediately before
         (no whitespace gap). Strip its trailing terminator.
      3. Decide:
         - In _TITLE_ABBREVS  -> skip (titles are followed by names)
         - In _CONTEXTUAL_ABBREVS -> split iff the next non-whitespace
           character starts a new sentence (uppercase / digit)
         - Otherwise -> split (default sentence boundary)
      4. Slice the text at confirmed split points; strip and filter empties.

    Decimals (`5.5`, `0.25`) are inherently safe because `.` is not
    followed by whitespace, so the candidate regex doesn't match them.
    """

    def segment(self, text: str, language: str = "en") -> List[str]:
        if not text or not text.strip():
            return []

        boundaries: List[int] = []
        for match in _CANDIDATE_RE.finditer(text):
            cand_end = match.start()  # position of first terminator char
            cand_after = match.end()  # position right after the matched whitespace

            word = _word_before(text, cand_end)
            stripped = _strip_trailing_terminator(word)

            # TMX-3801: a single uppercase letter before the dot is a personal
            # INITIAL ("Fernando P. Polack", "401 N. Middletown Rd."), never a
            # sentence boundary — even though the next word is capitalized.
            if len(stripped) == 1 and stripped.isalpha() and stripped.isupper():
                continue

            is_title = stripped in _TITLE_ABBREVS
            is_contextual = (
                stripped in _CONTEXTUAL_ABBREVS or stripped in _CREDENTIAL_ABBREVS
            )

            if is_title:
                # Titles never terminate a sentence even before a capitalized name.
                continue

            if is_contextual:
                tail = text[cand_after : cand_after + 1]
                if not _NEXT_STARTS_SENTENCE_RE.match(tail):
                    # Next word lowercase -> abbreviation continuation.
                    continue
                # Else fall through and treat as sentence boundary.

            boundaries.append(cand_after)

        if not boundaries:
            return _cap_length([text.strip()]) if text.strip() else []

        sentences: List[str] = []
        last = 0
        for b in boundaries:
            piece = text[last:b].strip()
            if piece:
                sentences.append(piece)
            last = b
        tail = text[last:].strip()
        if tail:
            sentences.append(tail)
        # TMX-OMIT-2: sub-split any over-long sentence before it reaches the LLM.
        return _cap_length(sentences)


class NaiveSplitSegmenter(BaseSegmenter):
    """
    Equivalent to `text.split('.')` — preserved as the documented BAD baseline
    so a regression test can prove the regex segmenter improves on it.
    NOT the default. Do not call from production code.
    """

    def segment(self, text: str, language: str = "en") -> List[str]:
        return [s.strip() for s in text.split(".") if s.strip()]


# CJK sentence terminators (TMX-3802). Japanese/Chinese sentences end with the
# ideographic full stop 。(U+3002) or full-width ！？(U+FF01/U+FF1F) and carry
# NO whitespace between sentences, so the Latin RegexSegmenter (which keys off
# `[.!?]+\s+`) never splits them — a whole CJK paragraph collapses into one
# segment, and an over-long block is then silently truncated by the LLM,
# dropping dosing/safety content (A3). ASCII `.` is deliberately NOT a CJK
# terminator: inside CJK text it is almost always a decimal (`5.5 mg`) or a
# Latin abbreviation, never an end-of-sentence marker.
_CJK_TERMINATORS = "。！？"  # 。！？
# A boundary is one-or-more terminators (。 ！？ or ASCII ! ?) plus any trailing
# closing brackets / quotes that belong to the sentence just ended.
_CJK_BOUNDARY_RE = re.compile(r"[" + _CJK_TERMINATORS + r"!?]+[」』）)】〕》”’\"']*")


class CJKSegmenter(BaseSegmenter):
    """
    Sentence segmenter for CJK scripts (Japanese, Chinese).

    Splits after every run of CJK/ASCII sentence terminators (。！？ ! ?),
    keeping the terminator (and any trailing closing quote/bracket) attached to
    the sentence it ends. No whitespace is required between sentences, which is
    the defining difference from the Latin RegexSegmenter. Decimals are safe
    because ASCII `.` is not a terminator here.

    Over-long terminator-free runs are still capped (TMX-OMIT-2) so an
    unpunctuated block cannot reach the LLM whole and be truncated.
    """

    def segment(self, text: str, language: str = "en") -> List[str]:
        if not text or not text.strip():
            return []

        sentences: List[str] = []
        last = 0
        for match in _CJK_BOUNDARY_RE.finditer(text):
            piece = text[last : match.end()].strip()
            if piece:
                sentences.append(piece)
            last = match.end()
        tail = text[last:].strip()
        if tail:
            sentences.append(tail)
        if not sentences:
            return _cap_length([text.strip()]) if text.strip() else []
        return _cap_length(sentences)


_SEGMENTERS_BY_LANG: dict[str, BaseSegmenter] = {
    "en": RegexSegmenter(),
    # CJK boundary rules (TMX-3802) — ideographic terminators, no inter-sentence
    # whitespace. Korean modern text uses Latin punctuation with spaces, so it
    # stays on the RegexSegmenter fallback.
    "ja": CJKSegmenter(),
    "zh": CJKSegmenter(),
    "zh-cn": CJKSegmenter(),
    "zh-tw": CJKSegmenter(),
    # Other languages fall back to the Latin RegexSegmenter, which is a
    # reasonable default for Latin-script languages.
}


def get_segmenter(language: str = "en") -> BaseSegmenter:
    """
    Return a segmenter for `language`. Falls back to the English RegexSegmenter
    with a logged note for unknown languages — the alternative (NaiveSplit) is
    strictly worse, so falling back to RegexSegmenter is the right default.
    """
    code = (language or "en").lower()
    seg = _SEGMENTERS_BY_LANG.get(code)
    if seg is not None:
        return seg
    # Try BCP-47 prefix
    prefix = code.split("-")[0]
    seg = _SEGMENTERS_BY_LANG.get(prefix)
    if seg is not None:
        return seg
    logger.info(
        "No registered segmenter for language=%r, falling back to RegexSegmenter",
        language,
    )
    return _SEGMENTERS_BY_LANG["en"]
