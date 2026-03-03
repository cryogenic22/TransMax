"""
TransMax Platform - Document Export Service
Format-preserving export: replaces source text with translations in original document format.
"""
import os
import io
from typing import List, Optional


class DocumentExportService:
    """Exports translated documents preserving original formatting."""

    def export_docx(self, original_path: str, segments: List[dict], force_new: bool = False) -> io.BytesIO:
        """
        Open the original DOCX from disk, replace each paragraph's text with the
        translated segment while preserving run formatting. Also handles table cells.
        Falls back to creating a fresh DOCX if original not found or force_new=True.
        """
        from docx import Document as DocxDocument

        # Build a lookup: order_index -> translated_text
        translation_map = {}
        for seg in segments:
            if seg.get("translated_text"):
                translation_map[seg["order_index"]] = seg["translated_text"]

        if not force_new and original_path and os.path.exists(original_path):
            doc = DocxDocument(original_path)
            idx = 1  # order_index starts at 1

            # Replace paragraph text while preserving formatting
            for para in doc.paragraphs:
                if not para.text.strip():
                    continue
                if idx in translation_map:
                    self._replace_paragraph_text(para, translation_map[idx])
                idx += 1

            # Replace table cell text
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        if not cell.text.strip():
                            continue
                        if idx in translation_map:
                            # Replace first paragraph in cell
                            if cell.paragraphs:
                                self._replace_paragraph_text(cell.paragraphs[0], translation_map[idx])
                                # Clear remaining paragraphs if any
                                for extra_para in cell.paragraphs[1:]:
                                    for run in extra_para.runs:
                                        run.text = ""
                        idx += 1
        else:
            # Fallback: create a fresh DOCX
            doc = DocxDocument()
            for seg in segments:
                text = seg.get("translated_text") or seg.get("source_text", "")
                doc.add_paragraph(text)

        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        return buffer

    def export_txt(self, segments: List[dict]) -> io.BytesIO:
        """Simple newline-joined translated text."""
        lines = []
        for seg in segments:
            text = seg.get("translated_text") or seg.get("source_text", "")
            lines.append(text)

        content = "\n\n".join(lines)
        buffer = io.BytesIO()
        buffer.write(content.encode("utf-8"))
        buffer.seek(0)
        return buffer

    @staticmethod
    def _replace_paragraph_text(para, new_text: str):
        """
        Replace paragraph text while preserving the first run's formatting.
        If the paragraph has runs, put all text into the first run and clear the rest.
        """
        if para.runs:
            para.runs[0].text = new_text
            for run in para.runs[1:]:
                run.text = ""
        else:
            para.text = new_text
