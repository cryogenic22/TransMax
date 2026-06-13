"""
TMX-EXPORT-1 — DOCX export backend (ADR-0006 Tier-3).

Folds the existing, fidelity-strong ``DocumentExportService`` under the uniform
exporter protocol: ingest source DOCX -> translate via the injected fn -> in-place
round-trip export (FidelityGate on). This is the PREFERRED path whenever the
editable source exists — Word/the layout engine does layout, so it is pixel-exact.
"""
from __future__ import annotations

from app.services.docx_ingestion import DocxIngestionService
from app.services.document_export import DocumentExportService
from app.services.export.base import (
    BlockVerdict,
    ExportResult,
    FidelityReport,
    FitStrategy,
    TranslateFn,
    Translatability,
)


class DocxExporter:
    name = "docx"

    def supports(self, file_ext: str) -> bool:
        return file_ext.lower().lstrip(".") == "docx"

    def export(self, source_path: str, translate_fn: TranslateFn,
               target_lang: str) -> ExportResult:
        blocks = DocxIngestionService().extract_blocks(source_path)
        texts = [b["text"] for b in blocks]
        translations = translate_fn(texts) if texts else []
        if len(translations) != len(texts):
            raise ValueError(
                f"translate_fn returned {len(translations)} for {len(texts)} blocks"
            )

        segments = [
            {
                "order_index": i + 1,
                "source_text": b["text"],
                "translated_text": translations[i],
                "element_type": b.get("type", "Paragraph"),
            }
            for i, b in enumerate(blocks)
        ]
        # FidelityError (structural loss) propagates — fail loud (A3).
        buf = DocumentExportService().export_docx(source_path, segments, enforce_fidelity=True)

        report = FidelityReport(
            backend=self.name, source_filename=source_path, target_lang=target_lang,
            verdicts=[
                BlockVerdict(
                    block_id=str(i + 1), page_index=0,
                    translatability=Translatability.CONTENT,
                    strategy=FitStrategy.IN_PLACE,
                )
                for i in range(len(blocks))
            ],
        )
        return ExportResult(
            data=buf.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            fidelity=report,
        )
