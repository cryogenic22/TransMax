"""
TMX-PARSE-1 — canonical document IR + parser protocol.

The IR is the single source of truth between a parser backend (pypdf, Docling,
Azure, Google) and every downstream consumer (segmenter, translation engine,
DOCX reconstruction/export, FidelityGate). Backends normalise their native
output into this shape; downstream code reads ONLY this shape — never a
backend-specific structure. (A4 / single-source-of-truth.)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Protocol, runtime_checkable


class ElementType(str, Enum):
    """Canonical structural element types.

    The minimal, backend-agnostic vocabulary a faithful translation must
    preserve. Backend-native labels (Docling's ``section_header``,
    unstructured's ``Title``, Azure's ``sectionHeading`` …) are mapped onto
    these by each backend, so downstream code branches on ONE enum.
    """

    TITLE = "title"
    SECTION_HEADER = "section_header"
    TEXT = "text"
    LIST_ITEM = "list_item"
    TABLE = "table"
    FIGURE = "figure"
    CAPTION = "caption"
    PAGE_HEADER = "page_header"
    PAGE_FOOTER = "page_footer"
    FOOTNOTE = "footnote"
    OTHER = "other"


# Element types that carry NO translatable prose on their own (rendered
# structure / artwork). Downstream may skip translating these but must still
# preserve them in the output skeleton.
NON_PROSE_TYPES = frozenset({ElementType.FIGURE})


@dataclass
class ParsedBlock:
    """One structural element in reading order."""

    text: str
    element_type: ElementType = ElementType.TEXT
    # 1-based reading-order position across the whole document.
    order_index: int = 0
    # 1-based page number when the backend knows it; None otherwise.
    page_no: Optional[int] = None
    # (x0, y0, x1, y1) in the backend's coordinate space, when available.
    bbox: Optional[tuple[float, float, float, float]] = None
    # For ElementType.TABLE: row-major list of row -> list of cell strings.
    table_grid: Optional[list[list[str]]] = None
    # Free-form per-backend extras (confidence, native label, ids, …). Always
    # carries `backend` so a block's provenance is never ambiguous (A1 spirit).
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedDocument:
    """A parsed document as an ordered list of canonical blocks."""

    source_filename: str
    backend: str
    blocks: list[ParsedBlock] = field(default_factory=list)
    page_count: Optional[int] = None

    def to_legacy_blocks(self) -> list[dict[str, Any]]:
        """Emit the legacy ``{"text","type","meta"}`` shape.

        Backward-compatible drop-in for the existing ingestion in
        ``app/api/documents.py`` (which reads ``block["text"]`` /
        ``block.get("type")`` / ``block.get("meta")``). ``type`` is the
        canonical ElementType *value* so a future export step can map it to a
        heading/list/table style deterministically.
        """
        out: list[dict[str, Any]] = []
        for b in self.blocks:
            meta = dict(b.meta)
            meta.setdefault("backend", self.backend)
            if b.page_no is not None:
                meta.setdefault("page_no", b.page_no)
            if b.table_grid is not None:
                meta.setdefault("table_grid", b.table_grid)
            out.append({"text": b.text, "type": b.element_type.value, "meta": meta})
        return out

    def structure_histogram(self) -> dict[str, int]:
        """Count blocks per ElementType value — used by the A/B eval + tests."""
        hist: dict[str, int] = {}
        for b in self.blocks:
            hist[b.element_type.value] = hist.get(b.element_type.value, 0) + 1
        return hist


class ParserError(Exception):
    """Base class for parser failures."""


class ParserUnavailable(ParserError):
    """The requested backend cannot run here.

    Raised when a backend's library or credentials are missing. A3: a backend
    that cannot run MUST fail loud, NEVER silently fall back to a worse parser —
    a reviewer must never translate a degraded extraction believing it faithful.
    The caller decides whether to surface the error or pick an explicit fallback.
    """


@runtime_checkable
class DocumentParser(Protocol):
    """Protocol every parser backend implements."""

    name: str

    def supports(self, file_ext: str) -> bool:
        """True if this backend can parse the given extension (e.g. ".pdf")."""
        ...

    def parse(self, file_path: str) -> ParsedDocument:
        """Parse a file into the canonical IR. Raise ParserUnavailable if the
        backend cannot run, or ParserError on a genuine parse failure."""
        ...
