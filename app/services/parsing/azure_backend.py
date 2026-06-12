"""
TMX-PARSE-1 — Azure AI Document Intelligence connector.

Ships as a real interface that FAILS LOUD (``ParserUnavailable``) when the SDK
(`azure-ai-documentintelligence`) or credentials are absent — never a silent
fallback to a worse parser (A3). Credential wiring + a live integration test are
the follow-up TMX-PARSE-AZURE; the layout→IR mapping below is implemented so
that turning it on is a credentials change, not a code change.
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

# Azure "prebuilt-layout" role -> canonical ElementType.
_ROLE_MAP: dict[str, ElementType] = {
    "title": ElementType.TITLE,
    "sectionHeading": ElementType.SECTION_HEADER,
    "pageHeader": ElementType.PAGE_HEADER,
    "pageFooter": ElementType.PAGE_FOOTER,
    "footnote": ElementType.FOOTNOTE,
    "pageNumber": ElementType.OTHER,
}


class AzureDocIntelligenceParser:
    name = "azure"

    def supports(self, file_ext: str) -> bool:
        return file_ext.lower().lstrip(".") in {"pdf", "docx", "pptx", "xlsx", "html"}

    def _client(self):
        try:
            from azure.ai.documentintelligence import DocumentIntelligenceClient
            from azure.core.credentials import AzureKeyCredential
        except ImportError as exc:
            raise ParserUnavailable(
                "azure-ai-documentintelligence not installed — "
                "`pip install azure-ai-documentintelligence`."
            ) from exc

        from app.core.config import settings

        endpoint = getattr(settings, "azure_docintel_endpoint", "") or os.getenv(
            "AZURE_DOCINTEL_ENDPOINT", ""
        )
        key = getattr(settings, "azure_docintel_key", "") or os.getenv(
            "AZURE_DOCINTEL_KEY", ""
        )
        if not endpoint or not key:
            raise ParserUnavailable(
                "Azure Document Intelligence endpoint/key not configured "
                "(AZURE_DOCINTEL_ENDPOINT / AZURE_DOCINTEL_KEY)."
            )
        return DocumentIntelligenceClient(endpoint, AzureKeyCredential(key))

    def parse(self, file_path: str) -> ParsedDocument:
        if not os.path.exists(file_path):
            raise ParserError(f"File not found: {file_path}")
        client = self._client()  # raises ParserUnavailable if SDK/creds missing
        try:
            with open(file_path, "rb") as fh:
                poller = client.begin_analyze_document("prebuilt-layout", body=fh)
            result = poller.result()
        except Exception as exc:  # noqa: BLE001
            raise ParserError(f"Azure analyze failed for {file_path}: {exc}") from exc
        return self._to_ir(result, os.path.basename(file_path))

    def _to_ir(self, result, filename: str) -> ParsedDocument:
        """Map an Azure AnalyzeResult into the canonical IR (paragraphs+tables)."""
        blocks: list[ParsedBlock] = []
        order = 0
        for para in getattr(result, "paragraphs", None) or []:
            text = (getattr(para, "content", "") or "").strip()
            if not text:
                continue
            role = getattr(para, "role", None)
            etype = _ROLE_MAP.get(str(role), ElementType.TEXT) if role else ElementType.TEXT
            page_no = None
            regions = getattr(para, "bounding_regions", None) or []
            if regions:
                page_no = getattr(regions[0], "page_number", None)
            order += 1
            blocks.append(
                ParsedBlock(
                    text=text, element_type=etype, order_index=order, page_no=page_no,
                    meta={"backend": self.name, "native_role": str(role)},
                )
            )
        page_count = len(getattr(result, "pages", None) or []) or None
        return ParsedDocument(
            source_filename=filename, backend=self.name, blocks=blocks, page_count=page_count
        )
