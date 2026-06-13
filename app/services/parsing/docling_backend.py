"""
TMX-PARSE-1 — Docling backend (layout / tables / reading order / unicode).

Measured on a 17-page oncology PDF: 36 section_header, 114 list_item, 4 tables,
30 figures, correct reading order, clean unicode — vs pypdf's 747 undifferentiated
"Sentence" blocks with mojibake. See ADR-0005.

Import-guarded: Docling pulls torch + layout/table models and is pinned via
`tokenizers<0.22`. If it cannot import/run here, ``parse`` raises
``ParserUnavailable`` (A3 — never a silent downgrade to a worse parser).
"""
from __future__ import annotations

import logging
import os

from app.services.parsing.base import (
    ElementType,
    ParsedBlock,
    ParsedDocument,
    ParserError,
    ParserUnavailable,
)

logger = logging.getLogger(__name__)

# Docling native label (lower-cased) -> canonical ElementType.
_LABEL_MAP: dict[str, ElementType] = {
    "title": ElementType.TITLE,
    "document_index": ElementType.SECTION_HEADER,
    "section_header": ElementType.SECTION_HEADER,
    "subtitle-level-1": ElementType.SECTION_HEADER,
    "paragraph": ElementType.TEXT,
    "text": ElementType.TEXT,
    "list_item": ElementType.LIST_ITEM,
    "table": ElementType.TABLE,
    "picture": ElementType.FIGURE,
    "figure": ElementType.FIGURE,
    "caption": ElementType.CAPTION,
    "page_header": ElementType.PAGE_HEADER,
    "page_footer": ElementType.PAGE_FOOTER,
    "footnote": ElementType.FOOTNOTE,
    "formula": ElementType.OTHER,
    "code": ElementType.OTHER,
}


def _canon(label: object) -> ElementType:
    raw = getattr(label, "value", None) or str(label)
    return _LABEL_MAP.get(str(raw).lower(), ElementType.OTHER)


class DoclingParser:
    name = "docling"

    def supports(self, file_ext: str) -> bool:
        return file_ext.lower().lstrip(".") in {"pdf", "docx", "pptx", "xlsx", "html", "md"}

    def _converter(self):
        """Build a DocumentConverter, disabling OCR unless configured on.

        OCR off is the right default for born-digital PDFs (far faster); a tenant
        sending scanned PDFs flips ``parser_ocr_enabled``. Built defensively so a
        Docling API shift degrades to the library default rather than crashing.
        """
        from docling.document_converter import DocumentConverter

        try:
            from app.core.config import settings
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.document_converter import PdfFormatOption

            opts = PdfPipelineOptions()
            opts.do_ocr = bool(getattr(settings, "parser_ocr_enabled", False))
            return DocumentConverter(
                format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
            )
        except Exception as exc:  # pragma: no cover - API-shift defensive path
            logger.warning("Docling pipeline-options setup failed (%s); using defaults", exc)
            return DocumentConverter()

    def parse(self, file_path: str) -> ParsedDocument:
        if not os.path.exists(file_path):
            raise ParserError(f"File not found: {file_path}")

        # Import-guard: a missing/broken Docling install must fail loud, not
        # silently degrade. The caller decides whether to pick a fallback.
        try:
            converter = self._converter()
        except Exception as exc:  # noqa: BLE001 - import OR init failure both mean "unavailable"
            raise ParserUnavailable(f"Docling unavailable: {exc}") from exc

        try:
            result = converter.convert(file_path)
            ddoc = result.document
        except Exception as exc:  # noqa: BLE001 - a genuine parse failure
            raise ParserError(f"Docling failed to parse {file_path}: {exc}") from exc

        blocks: list[ParsedBlock] = []
        order = 0
        for item, _level in self._iter_items(ddoc):
            etype = _canon(getattr(item, "label", None))
            page_no = self._page_no(item)
            bbox, gmeta = self._geom(item, ddoc)
            if etype is ElementType.TABLE:
                text, grid = self._table(item, ddoc)
                order += 1
                blocks.append(
                    ParsedBlock(
                        text=text, element_type=etype, order_index=order,
                        page_no=page_no, bbox=bbox, table_grid=grid,
                        meta={"backend": self.name, "native_label": "table", **gmeta},
                    )
                )
                continue
            if etype is ElementType.FIGURE:
                # Preserve the figure in the skeleton; bbox lets a renderer crop the
                # real bitmap from the source (pypdfium2) instead of dropping it.
                order += 1
                blocks.append(
                    ParsedBlock(
                        text="", element_type=etype, order_index=order, page_no=page_no,
                        bbox=bbox,
                        meta={"backend": self.name, "native_label": "picture", **gmeta},
                    )
                )
                continue
            text = (getattr(item, "text", "") or "").strip()
            if not text:
                continue
            order += 1
            blocks.append(
                ParsedBlock(
                    text=text, element_type=etype, order_index=order, page_no=page_no,
                    bbox=bbox,
                    meta={"backend": self.name, "native_label": str(getattr(item, "label", "")), **gmeta},
                )
            )

        return ParsedDocument(
            source_filename=os.path.basename(file_path),
            backend=self.name,
            blocks=blocks,
            page_count=self._page_count(ddoc),
        )

    # --- defensive accessors (insulate us from Docling API drift) ----------

    @staticmethod
    def _iter_items(ddoc):
        try:
            return list(ddoc.iterate_items())
        except Exception:  # noqa: BLE001
            # Fallback: texts only, in their stored order.
            return [(t, 0) for t in getattr(ddoc, "texts", [])]

    @staticmethod
    def _page_no(item):
        try:
            prov = getattr(item, "prov", None) or []
            if prov:
                return getattr(prov[0], "page_no", None)
        except Exception:  # noqa: BLE001
            pass
        return None

    @staticmethod
    def _geom(item, ddoc):
        """Return (bbox, geom_meta) from prov, or (None, {}).

        bbox is (l, t, r, b) in PDF points. geom_meta carries coord_origin + page
        size so a downstream renderer (figure cropping, layout-aware placement) can
        convert correctly. Defensive against Docling API drift (A3-adjacent: a
        missing bbox degrades to None, never crashes the parse)."""
        try:
            prov = getattr(item, "prov", None) or []
            if not prov:
                return None, {}
            b = getattr(prov[0], "bbox", None)
            if b is None:
                return None, {}
            bbox = (float(b.l), float(b.t), float(b.r), float(b.b))
            origin = getattr(getattr(b, "coord_origin", None), "value", None) \
                or str(getattr(b, "coord_origin", "")) or None
            meta = {"coord_origin": origin}
            page_no = getattr(prov[0], "page_no", None)
            pages = getattr(ddoc, "pages", {}) or {}
            page = pages.get(page_no) if hasattr(pages, "get") else None
            size = getattr(page, "size", None)
            if size is not None:
                meta["page_width"] = float(getattr(size, "width", 0)) or None
                meta["page_height"] = float(getattr(size, "height", 0)) or None
            return bbox, meta
        except Exception:  # noqa: BLE001 — geometry is best-effort
            return None, {}

    @staticmethod
    def _page_count(ddoc):
        try:
            return len(getattr(ddoc, "pages", {}) or {})
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def _table(item, ddoc):
        """Return (text, grid) for a table item, defensively."""
        try:
            try:
                df = item.export_to_dataframe(ddoc)  # current Docling API
            except TypeError:
                df = item.export_to_dataframe()  # older Docling (no doc arg)
            grid = [list(map(str, df.columns))] + df.astype(str).values.tolist()
            return df.to_csv(index=False), grid
        except Exception:  # noqa: BLE001
            try:
                return item.export_to_markdown(ddoc), None
            except Exception:  # noqa: BLE001
                return (getattr(item, "text", "") or "").strip(), None
