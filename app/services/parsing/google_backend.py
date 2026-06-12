"""
TMX-PARSE-1 — Google Document AI connector.

Ships as a real interface that FAILS LOUD (``ParserUnavailable``) when the SDK
(`google-cloud-documentai`) or processor config are absent — never a silent
fallback (A3). Credential/processor wiring + a live integration test are the
follow-up TMX-PARSE-GOOGLE; the layout→IR mapping is implemented so enabling it
is a config change, not a code change.
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

# Document AI layout block type -> canonical ElementType. Document AI's Layout
# Parser emits block types like "heading-1", "paragraph", "list-item", "table".
_BLOCK_MAP: dict[str, ElementType] = {
    "title": ElementType.TITLE,
    "heading-1": ElementType.SECTION_HEADER,
    "heading-2": ElementType.SECTION_HEADER,
    "heading-3": ElementType.SECTION_HEADER,
    "paragraph": ElementType.TEXT,
    "list-item": ElementType.LIST_ITEM,
    "table": ElementType.TABLE,
    "page_header": ElementType.PAGE_HEADER,
    "page_footer": ElementType.PAGE_FOOTER,
}


class GoogleDocumentAIParser:
    name = "google"

    def supports(self, file_ext: str) -> bool:
        return file_ext.lower().lstrip(".") in {"pdf", "docx", "pptx", "xlsx", "html"}

    def _client_and_processor(self):
        try:
            from google.cloud import documentai
        except ImportError as exc:
            raise ParserUnavailable(
                "google-cloud-documentai not installed — "
                "`pip install google-cloud-documentai`."
            ) from exc

        from app.core.config import settings

        processor = getattr(settings, "google_docai_processor", "") or os.getenv(
            "GOOGLE_DOCAI_PROCESSOR", ""
        )
        if not processor:
            raise ParserUnavailable(
                "Google Document AI processor not configured "
                "(GOOGLE_DOCAI_PROCESSOR=projects/.../locations/.../processors/...)."
            )
        try:
            client = documentai.DocumentProcessorServiceClient()
        except Exception as exc:  # noqa: BLE001 - ADC/credentials failure
            raise ParserUnavailable(
                f"Google Document AI client could not authenticate: {exc}"
            ) from exc
        return documentai, client, processor

    def parse(self, file_path: str) -> ParsedDocument:
        if not os.path.exists(file_path):
            raise ParserError(f"File not found: {file_path}")
        documentai, client, processor = self._client_and_processor()
        try:
            with open(file_path, "rb") as fh:
                content = fh.read()
            mime = "application/pdf" if file_path.lower().endswith(".pdf") else "application/octet-stream"
            request = documentai.ProcessRequest(
                name=processor,
                raw_document=documentai.RawDocument(content=content, mime_type=mime),
            )
            result = client.process_document(request=request)
        except Exception as exc:  # noqa: BLE001
            raise ParserError(f"Document AI process failed for {file_path}: {exc}") from exc
        return self._to_ir(result.document, os.path.basename(file_path))

    def _to_ir(self, document, filename: str) -> ParsedDocument:
        """Map a Document AI Document into the canonical IR.

        Uses the document-layout blocks when present (Layout Parser); falls back
        to paragraph segments. Kept defensive so a proto-shape change degrades
        gracefully rather than crashing.
        """
        blocks: list[ParsedBlock] = []
        order = 0
        full_text = getattr(document, "text", "") or ""

        layout_doc = getattr(document, "document_layout", None)
        if layout_doc is not None and getattr(layout_doc, "blocks", None):
            for blk in layout_doc.blocks:
                tb = getattr(blk, "text_block", None)
                if tb is None:
                    continue
                text = (getattr(tb, "text", "") or "").strip()
                if not text:
                    continue
                etype = _BLOCK_MAP.get(str(getattr(tb, "type_", "")), ElementType.TEXT)
                order += 1
                blocks.append(
                    ParsedBlock(
                        text=text, element_type=etype, order_index=order,
                        meta={"backend": self.name, "native_type": str(getattr(tb, "type_", ""))},
                    )
                )
        else:
            for page in getattr(document, "pages", None) or []:
                for para in getattr(page, "paragraphs", None) or []:
                    text = self._anchor_text(full_text, getattr(para, "layout", None))
                    if not text:
                        continue
                    order += 1
                    blocks.append(
                        ParsedBlock(
                            text=text, element_type=ElementType.TEXT, order_index=order,
                            page_no=getattr(page, "page_number", None),
                            meta={"backend": self.name},
                        )
                    )

        page_count = len(getattr(document, "pages", None) or []) or None
        return ParsedDocument(
            source_filename=filename, backend=self.name, blocks=blocks, page_count=page_count
        )

    @staticmethod
    def _anchor_text(full_text: str, layout) -> str:
        """Resolve a Document AI text-anchor (offset ranges) into a string."""
        try:
            anchor = getattr(layout, "text_anchor", None)
            if anchor is None:
                return ""
            parts = []
            for seg in getattr(anchor, "text_segments", None) or []:
                start = int(getattr(seg, "start_index", 0) or 0)
                end = int(getattr(seg, "end_index", 0) or 0)
                parts.append(full_text[start:end])
            return "".join(parts).strip()
        except Exception:  # noqa: BLE001
            return ""
