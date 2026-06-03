"""
TransMax Platform - Document Export Service
Format-preserving export: replaces source text with translations in original document format.
Handles body paragraphs, tables (with merged/nested cells), headers, footers,
footnotes, endnotes, and text boxes — mirroring the ingestion traversal order.
"""
import os
import io
import re
from typing import List, Optional

from app.services.docx_utils import (
    W, PNS, TBLNS, TNS, TXBX_CONTENT,
    cell_text_excluding_nested, replace_xml_text_nodes,
)


class DocumentExportService:
    """Exports translated documents preserving original formatting."""

    def export_docx(self, original_path: str, segments: List[dict], force_new: bool = False) -> io.BytesIO:
        """
        Open the original DOCX from disk, replace each element's text with the
        translated segment while preserving formatting. Traversal order matches ingestion.
        Falls back to creating a fresh DOCX if original not found or force_new=True.
        """
        from docx import Document as DocxDocument

        # Build lookups for content-based matching and sequential fallback
        translation_map = {}  # order_index -> translated_text
        content_map = {}  # normalized source_text -> translated_text
        for seg in segments:
            if seg.get("translated_text"):
                translation_map[seg["order_index"]] = seg["translated_text"]
                source = seg.get("source_text", "").strip()
                if source:
                    content_map[source] = seg["translated_text"]

        if not force_new and original_path and os.path.exists(original_path):
            doc = DocxDocument(original_path)
            idx = [1]  # mutable counter; order_index starts at 1

            # 1. Body — paragraphs and tables interleaved in document order
            self._export_body(doc, idx, content_map, translation_map)

            # 2. Headers
            self._export_headers(doc, idx, content_map, translation_map)

            # 3. Footers
            self._export_footers(doc, idx, content_map, translation_map)

            # 4. Footnotes
            self._export_footnotes(doc, idx, content_map, translation_map)

            # 5. Endnotes
            self._export_endnotes(doc, idx, content_map, translation_map)

            # 6. Text boxes
            self._export_text_boxes(doc, idx, content_map, translation_map)
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

    def _export_body(self, doc, idx: list, content_map: dict, translation_map: dict):
        """Replace body paragraphs and table cells in document order."""
        body = doc.element.body
        # Map top-level <w:tbl> elements to python-docx Table objects
        top_level_tables = {}
        tbl_idx = 0
        tables = doc.tables
        for child in body:
            if child.tag == TBLNS:
                if tbl_idx < len(tables):
                    top_level_tables[id(child)] = tables[tbl_idx]
                    tbl_idx += 1

        for child in body:
            if child.tag == PNS:
                # Gather text from <w:t> nodes
                parts = []
                for t_node in child.iter(TNS):
                    if t_node.text:
                        parts.append(t_node.text)
                text = "".join(parts).strip()
                if not text:
                    continue
                translated = self._match_translation(text, idx[0], content_map, translation_map)
                if translated is not None:
                    # Find the matching python-docx paragraph
                    for para in doc.paragraphs:
                        if para._element is child:
                            self._replace_paragraph_text(para, translated)
                            break
                idx[0] += 1

            elif child.tag == TBLNS:
                tbl_obj = top_level_tables.get(id(child))
                if tbl_obj:
                    self._export_table(tbl_obj, idx, content_map, translation_map)

    def _export_table(self, table, idx: list, content_map: dict, translation_map: dict):
        """Replace table cell text, deduplicating merged cells and recursing into nested tables."""
        seen_tcs = []
        for row in table.rows:
            for cell in row.cells:
                tc = cell._tc
                if any(s is tc for s in seen_tcs):
                    continue
                seen_tcs.append(tc)

                text = cell_text_excluding_nested(cell).strip()
                if not text:
                    # Still recurse into nested tables
                    for nested_table in cell.tables:
                        self._export_table(nested_table, idx, content_map, translation_map)
                    continue

                translated = self._match_translation(text, idx[0], content_map, translation_map)
                if translated is not None:
                    self._replace_cell_text(cell, translated)
                idx[0] += 1

                # Recurse into nested tables
                for nested_table in cell.tables:
                    self._export_table(nested_table, idx, content_map, translation_map)

    def _export_headers(self, doc, idx: list, content_map: dict, translation_map: dict):
        """Replace header paragraph text."""
        for section in doc.sections:
            for attr in ["header", "first_page_header", "even_page_header"]:
                hdr = getattr(section, attr, None)
                if hdr is None or hdr.is_linked_to_previous:
                    continue
                for para in hdr.paragraphs:
                    text = para.text.strip()
                    if not text:
                        continue
                    translated = self._match_translation(text, idx[0], content_map, translation_map)
                    if translated is not None:
                        self._replace_paragraph_text(para, translated)
                    idx[0] += 1

    def _export_footers(self, doc, idx: list, content_map: dict, translation_map: dict):
        """Replace footer paragraph text."""
        for section in doc.sections:
            for attr in ["footer", "first_page_footer", "even_page_footer"]:
                ftr = getattr(section, attr, None)
                if ftr is None or ftr.is_linked_to_previous:
                    continue
                for para in ftr.paragraphs:
                    text = para.text.strip()
                    if not text:
                        continue
                    translated = self._match_translation(text, idx[0], content_map, translation_map)
                    if translated is not None:
                        self._replace_paragraph_text(para, translated)
                    idx[0] += 1

    def _export_footnotes(self, doc, idx: list, content_map: dict, translation_map: dict):
        """Replace footnote text via raw XML."""
        try:
            from docx.opc.constants import RELATIONSHIP_TYPE as RT
            footnotes_part = doc.part.part_related_by(RT.FOOTNOTES)
        except (KeyError, Exception):
            return

        root = footnotes_part._element
        ns = {"w": W}
        for fn in root.findall("w:footnote", ns):
            fn_id = fn.get(f"{{{W}}}id")
            if fn_id is not None and int(fn_id) <= 0:
                continue
            parts = []
            for t_node in fn.iter(TNS):
                if t_node.text:
                    parts.append(t_node.text)
            text = "".join(parts).strip()
            if not text:
                continue
            translated = self._match_translation(text, idx[0], content_map, translation_map)
            if translated is not None:
                replace_xml_text_nodes(fn, translated)
            idx[0] += 1

    def _export_endnotes(self, doc, idx: list, content_map: dict, translation_map: dict):
        """Replace endnote text via raw XML."""
        try:
            from docx.opc.constants import RELATIONSHIP_TYPE as RT
            endnotes_part = doc.part.part_related_by(RT.ENDNOTES)
        except (KeyError, Exception):
            return

        root = endnotes_part._element
        ns = {"w": W}
        for en in root.findall("w:endnote", ns):
            en_id = en.get(f"{{{W}}}id")
            if en_id is not None and int(en_id) <= 0:
                continue
            parts = []
            for t_node in en.iter(TNS):
                if t_node.text:
                    parts.append(t_node.text)
            text = "".join(parts).strip()
            if not text:
                continue
            translated = self._match_translation(text, idx[0], content_map, translation_map)
            if translated is not None:
                replace_xml_text_nodes(en, translated)
            idx[0] += 1

    def _export_text_boxes(self, doc, idx: list, content_map: dict, translation_map: dict):
        """Replace text box content."""
        body = doc.element.body
        for txbx in body.iter(TXBX_CONTENT):
            parts = []
            for t_node in txbx.iter(TNS):
                if t_node.text:
                    parts.append(t_node.text)
            text = "".join(parts).strip()
            if not text:
                continue
            translated = self._match_translation(text, idx[0], content_map, translation_map)
            if translated is not None:
                replace_xml_text_nodes(txbx, translated)
            idx[0] += 1

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
    def _match_translation(para_text: str, idx: int, content_map: dict, translation_map: dict) -> Optional[str]:
        """Try content-based matching first, fall back to sequential index."""
        stripped = para_text.strip()
        if stripped in content_map:
            return content_map[stripped]
        if idx in translation_map:
            return translation_map[idx]
        return None

    @staticmethod
    def _replace_paragraph_text(para, new_text: str):
        """
        Replace paragraph text while preserving per-run formatting.
        Distributes translated text proportionally across existing runs
        so each run's font properties (bold, italic, color, etc.) are kept.
        """
        runs = para.runs
        if not runs:
            para.text = new_text
            return

        if len(runs) == 1:
            runs[0].text = new_text
            return

        # Identify whitespace-only runs to preserve as-is
        content_runs = []
        for i, run in enumerate(runs):
            if run.text.strip():
                content_runs.append(i)

        if not content_runs:
            # All runs are whitespace; just put text in first run
            runs[0].text = new_text
            for run in runs[1:]:
                run.text = ""
            return

        # Calculate original character proportions for content runs
        original_lengths = []
        for i in content_runs:
            original_lengths.append(len(runs[i].text))
        total_original = sum(original_lengths)
        if total_original == 0:
            runs[content_runs[0]].text = new_text
            return

        # Split translated text into words
        words = new_text.split()
        if not words:
            for i in content_runs:
                runs[i].text = ""
            return

        # Distribute words proportionally across content runs
        total_words = len(words)
        word_pos = 0
        for ci, run_idx in enumerate(content_runs):
            if ci == len(content_runs) - 1:
                # Last content run gets all remaining words
                runs[run_idx].text = " ".join(words[word_pos:])
            else:
                proportion = original_lengths[ci] / total_original
                word_count = max(1, round(proportion * total_words))
                end_pos = min(word_pos + word_count, total_words)
                runs[run_idx].text = " ".join(words[word_pos:end_pos])
                word_pos = end_pos
                if word_pos >= total_words:
                    # No more words; clear remaining content runs
                    for remaining_idx in content_runs[ci + 1:]:
                        runs[remaining_idx].text = ""
                    break

        # Clear whitespace-only runs that sit between content runs
        # but preserve leading/trailing whitespace runs
        for i, run in enumerate(runs):
            if i not in content_runs and run.text.strip() == "":
                # Keep whitespace runs that are before first or after last content run
                if content_runs and (i < content_runs[0] or i > content_runs[-1]):
                    pass  # preserve leading/trailing whitespace
                else:
                    run.text = " "  # normalize inter-run whitespace

    @staticmethod
    def _distribute_text_across_paragraphs(paragraphs, text: str):
        """Split text across multiple paragraphs by sentences."""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        num_paras = len(paragraphs)

        if num_paras <= 1:
            return [text]

        # Distribute sentences across paragraphs
        chunks = []
        per_para = max(1, len(sentences) // num_paras)
        pos = 0
        for i in range(num_paras):
            if i == num_paras - 1:
                chunks.append(" ".join(sentences[pos:]))
            else:
                end = min(pos + per_para, len(sentences))
                chunks.append(" ".join(sentences[pos:end]))
                pos = end
                if pos >= len(sentences):
                    chunks.extend([""] * (num_paras - i - 1))
                    break
        return chunks

    def _replace_cell_text(self, cell, translated: str):
        """Replace text in a table cell, distributing across paragraphs if needed."""
        paras = [p for p in cell.paragraphs if p.text.strip()]
        if not paras:
            if cell.paragraphs:
                self._replace_paragraph_text(cell.paragraphs[0], translated)
            return

        if len(paras) == 1:
            self._replace_paragraph_text(paras[0], translated)
            # Clear any other paragraphs
            for p in cell.paragraphs:
                if p is not paras[0] and p.text.strip():
                    for run in p.runs:
                        run.text = ""
            return

        # Multiple paragraphs: distribute translated text by sentences
        chunks = self._distribute_text_across_paragraphs(paras, translated)
        for i, para in enumerate(paras):
            if i < len(chunks):
                self._replace_paragraph_text(para, chunks[i])
            else:
                for run in para.runs:
                    run.text = ""
