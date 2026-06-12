"""
TMX-PARSE-1 — pypdf backend (the always-available fallback).

Wraps today's page-level text extraction into the canonical IR. It does NOT
recover structure (every block is TEXT) — that is exactly the limitation the
Docling backend exists to fix — but it is dependency-light and always works,
so it is the safe default until a richer backend is validated in deploy.
"""
from __future__ import annotations

import logging
import os

from app.services.parsing.base import (
    ElementType,
    ParsedBlock,
    ParsedDocument,
    ParserError,
)

logger = logging.getLogger(__name__)


class PyPdfParser:
    name = "pypdf"

    def supports(self, file_ext: str) -> bool:
        return file_ext.lower().lstrip(".") == "pdf"

    def parse(self, file_path: str) -> ParsedDocument:
        if not os.path.exists(file_path):
            raise ParserError(f"PDF file not found: {file_path}")
        try:
            import pypdf
        except ImportError as exc:  # pragma: no cover - pypdf is a hard dep
            raise ParserError(f"pypdf not importable: {exc}") from exc

        reader = pypdf.PdfReader(file_path)
        blocks: list[ParsedBlock] = []
        order = 0
        for i, page in enumerate(reader.pages):
            text = (page.extract_text() or "").strip()
            if not text:
                continue
            order += 1
            blocks.append(
                ParsedBlock(
                    text=text,
                    element_type=ElementType.TEXT,
                    order_index=order,
                    page_no=i + 1,
                    meta={"backend": self.name, "native_label": "pdf_page_text"},
                )
            )
        return ParsedDocument(
            source_filename=os.path.basename(file_path),
            backend=self.name,
            blocks=blocks,
            page_count=len(reader.pages),
        )
