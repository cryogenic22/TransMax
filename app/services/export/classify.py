"""
TMX-EXPORT-1 — translatability classifier (ADR-0006 AC-4).

The whole point: decide what to translate vs preserve WITHOUT hard-coding to a
source type. Every signal here is generic and document-derived:

  * cross-page repetition  — running heads, mastheads, folios, footers repeat at
    a stable position on multiple pages. This catches "The New England Journal of
    Medicine" or "n engl j med 383;27" on ANY publication, not by name.
  * geometry               — a display-size block in the top band is page identity;
    a 1-2 char block far larger than body text is a drop-cap initial.
  * shape                  — identifier-like strings (DOIs, URLs, folios, dates)
    are not prose.
  * an optional do-not-translate glossary (config) for trademarks/proper nouns.

A single source-type branch (``if journal == "NEJM"``) is exactly what this
module exists to avoid.
"""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field

from app.services.export.base import LayoutBlock, Translatability

_DIGIT_RE = re.compile(r"\d")
_WS_RE = re.compile(r"\s+")
_IDENTIFIER_RE = re.compile(
    r"^(?:https?://|www\.|doi:|10\.\d{4,}/|issn|isbn)|"      # urls / dois / issn
    r"^[\W\d]+$|"                                            # only digits/punct
    r"\b\d+\s*[;:]\s*\d+\b|"                                 # vol;page folio
    r"\bpage\s+\d+\b",
    re.IGNORECASE,
)


def _normalize(text: str, *, drop_digits: bool = True) -> str:
    t = _WS_RE.sub(" ", text.strip().lower())
    if drop_digits:
        t = _DIGIT_RE.sub("#", t)
    return t


@dataclass
class DocumentProfile:
    """Document-wide statistics the per-block classifier reads."""

    body_size: float
    # normalized texts that appear on >= 2 distinct pages (chrome/running content)
    repeated_norms: frozenset = field(default_factory=frozenset)
    page_count: int = 1


def build_profile(blocks: list[LayoutBlock]) -> DocumentProfile:
    """Derive document-wide signals from all blocks in one pass."""
    if not blocks:
        return DocumentProfile(body_size=10.0)

    # Body size = median size of paragraph-ish blocks (long text), else all blocks.
    para_sizes = [b.size for b in blocks if len(b.text) > 40]
    body_size = statistics.median(para_sizes) if para_sizes else statistics.median(
        [b.size for b in blocks]
    )

    # Repetition: a SHORT normalized text seen on >= 2 distinct pages is chrome
    # (running head / masthead / folio / footer). The length cap matters: long
    # body paragraphs that merely look alike after digit-normalisation must NOT be
    # mistaken for chrome — chrome is short.
    pages_by_norm: dict[str, set[int]] = {}
    for b in blocks:
        norm = _normalize(b.text)
        if not (2 <= len(norm) <= 80):
            continue
        pages_by_norm.setdefault(norm, set()).add(b.page_index)
    repeated = frozenset(n for n, pages in pages_by_norm.items() if len(pages) >= 2)

    page_count = len({b.page_index for b in blocks})
    return DocumentProfile(body_size=body_size, repeated_norms=repeated,
                           page_count=page_count)


def _looks_identifier(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if _IDENTIFIER_RE.search(stripped):
        return True
    # Mostly non-alphabetic (folios, codes): >60% of chars are digit/punct/space.
    non_alpha = sum(1 for c in stripped if not c.isalpha())
    return non_alpha / len(stripped) > 0.6


def classify(
    block: LayoutBlock,
    profile: DocumentProfile,
    *,
    glossary: frozenset = frozenset(),
    top_band_frac: float = 0.12,
    bottom_band_frac: float = 0.92,
) -> Translatability:
    """Classify one block. Order matters: most specific signal wins."""
    text = block.text.strip()
    if not text:
        return Translatability.PRESERVE

    body = profile.body_size or 10.0
    y0 = block.bbox[1]
    in_top_band = y0 < top_band_frac * block.page_height
    in_bottom_band = y0 > bottom_band_frac * block.page_height

    # 1) Drop-cap: a tiny block far larger than body text.
    if len(text) <= 2 and block.size >= 1.8 * body:
        return Translatability.DROP_CAP

    # 2) Explicit do-not-translate glossary (config — trademarks/proper nouns).
    if _normalize(text, drop_digits=False) in glossary:
        return Translatability.PRESERVE

    # 3) Chrome by repetition: same text (digit-insensitive) on multiple pages.
    if _normalize(text) in profile.repeated_norms:
        return Translatability.PRESERVE

    # 4) Identifiers / folios / DOIs / URLs are not prose.
    if _looks_identifier(text):
        return Translatability.PRESERVE

    # 5) Single-page fallback for mastheads/running heads (no repetition signal):
    #    display-size short text pinned to the top or bottom band = page identity.
    if (in_top_band or in_bottom_band) and block.size >= 1.5 * body and len(text) < 70:
        return Translatability.PRESERVE

    # 6) Default: it's content.
    return Translatability.CONTENT


# --- IR-level classification (Tier-2 pdf_render) ---------------------------
# The canonical IR (ADR-0005) lacks per-span font size, so the geometry/size
# signals above don't all apply. We use what the IR DOES carry: the element type
# (Docling already tags page_header/page_footer), cross-page repetition of short
# strings (running heads/folios), identifier shape, and an optional glossary.

_IR_CHROME_TYPES = frozenset({"page_header", "page_footer"})


def build_ir_repeats(blocks: list[dict]) -> frozenset:
    """Normalized SHORT texts that repeat on >= 2 pages of an IR block list."""
    pages_by_norm: dict[str, set] = {}
    for b in blocks:
        norm = _normalize(b.get("text", ""))
        if not (2 <= len(norm) <= 80):
            continue
        pages_by_norm.setdefault(norm, set()).add(b.get("page_no"))
    return frozenset(n for n, pages in pages_by_norm.items() if len(pages) >= 2)


def ir_disposition(block: dict, repeats: frozenset, *,
                   glossary: frozenset = frozenset()) -> str:
    """Decide how a Tier-2 re-render should treat an IR block:

      "translate" — prose content → send to the translator
      "verbatim"  — brand/identifier → render untranslated, in the flow
      "drop"      — per-page chrome (running head/footer, repeated folio) → omit

    Per-page chrome is dropped because a reflowed single document has no per-page
    running elements; brand/identifier strings are kept verbatim so the masthead
    or a DOI is neither translated nor lost.
    """
    text = (block.get("text") or "").strip()
    if not text:
        return "drop"
    if (block.get("element_type") or "").lower() in _IR_CHROME_TYPES:
        return "drop"
    if _normalize(text) in repeats:
        return "drop"
    if _normalize(text, drop_digits=False) in glossary:
        return "verbatim"
    if _looks_identifier(text):
        return "verbatim"
    return "translate"
