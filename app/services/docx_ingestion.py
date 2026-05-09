"""
TransMax Platform - DOCX Ingestion Service
Extracts translatable text blocks from all DOCX elements:
body paragraphs, tables, headers, footers, footnotes, endnotes, text boxes.

v2 (TMX-3700) adds tracked-change detection: each block's `meta` carries
a `revisions` dict when the block contains <w:ins>, <w:del>, <w:moveFrom>,
or <w:moveTo> marks. Body text remains the FINAL text (Word's display-final
mode) — inserted text included, deleted text excluded.
"""
from typing import List, Optional, Tuple
from lxml import etree

from app.services.docx_utils import (
    W, PNS, TBLNS, TCNS, TNS, TXBX_CONTENT,
    INS_NS, DEL_NS, MOVE_FROM_NS, MOVE_TO_NS,
    AUTHOR_ATTR, DATE_ATTR, REVISION_TAGS,
    cell_text_excluding_nested,
)


def _collect_revisions(element) -> Optional[dict]:
    """
    Walk `element` for tracked-change marks.

    Returns a dict shaped:
        {
            "has_insertions":  bool,
            "has_deletions":   bool,
            "has_moves_from":  bool,  # text was relocated AWAY from here
            "has_moves_to":    bool,  # text arrived HERE from elsewhere
            "has_moves":       bool,  # has_moves_from OR has_moves_to (back-compat)
            "authors":         list[str],
            "dates":           list[str],
        }
    or None if no revision marks are present (callers should omit the
    `meta.revisions` key entirely in that case for backward compatibility).

    Authors and dates are unique-deduplicated and ordered by first
    occurrence in the document tree.

    TMX-3704 split `has_moves` into directional `has_moves_from` /
    `has_moves_to` so a reviewer can distinguish "text left here" vs
    "text arrived here". `has_moves` is retained as the OR of both for
    backward compatibility with TMX-3702-v1's <RevisionIndicator>.
    """
    has_ins = False
    has_del = False
    has_move_from = False
    has_move_to = False
    authors: List[str] = []
    dates: List[str] = []
    seen_authors = set()
    seen_dates = set()

    for descendant in element.iter():
        tag = descendant.tag
        if tag == INS_NS:
            has_ins = True
        elif tag == DEL_NS:
            has_del = True
        elif tag == MOVE_FROM_NS:
            has_move_from = True
        elif tag == MOVE_TO_NS:
            has_move_to = True
        else:
            continue
        author = descendant.get(AUTHOR_ATTR)
        if author and author not in seen_authors:
            authors.append(author)
            seen_authors.add(author)
        date = descendant.get(DATE_ATTR)
        if date and date not in seen_dates:
            dates.append(date)
            seen_dates.add(date)

    has_move_any = has_move_from or has_move_to
    if not (has_ins or has_del or has_move_any):
        return None
    return {
        "has_insertions": has_ins,
        "has_deletions": has_del,
        "has_moves_from": has_move_from,
        "has_moves_to": has_move_to,
        "has_moves": has_move_any,
        "authors": authors,
        "dates": dates,
    }


def _attach_revisions(block_meta: dict, element) -> None:
    """If `element` has any revision marks, write them into `block_meta`."""
    rev = _collect_revisions(element)
    if rev is not None:
        block_meta["revisions"] = rev


class DocxIngestionService:
    """Extracts structured text blocks from a DOCX file."""

    def extract_blocks(self, file_path: str) -> List[dict]:
        """
        Extract all translatable text blocks from a DOCX file.
        Returns list of {"text": str, "type": str, "meta": dict}.
        Traversal order matches export exactly.
        """
        from docx import Document as DocxDocument

        doc = DocxDocument(file_path)
        blocks = []

        # 1. Body content — paragraphs and tables interleaved in document order
        self._extract_body(doc, blocks)

        # 2. Headers
        self._extract_headers(doc, blocks)

        # 3. Footers
        self._extract_footers(doc, blocks)

        # 4. Footnotes
        self._extract_footnotes(doc, blocks)

        # 5. Endnotes
        self._extract_endnotes(doc, blocks)

        # 6. Text boxes
        self._extract_text_boxes(doc, blocks)

        return blocks

    def _extract_body(self, doc, blocks: list):
        """Extract paragraphs and tables from body in document order."""
        body = doc.element.body

        # Map top-level <w:tbl> elements to python-docx Table objects by matching XML elements
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
                text = child.text_content() if hasattr(child, 'text_content') else ""
                if not text:
                    # Fallback: gather <w:t> nodes
                    parts = []
                    for t_node in child.iter(TNS):
                        if t_node.text:
                            parts.append(t_node.text)
                    text = "".join(parts)
                text = text.strip()
                if text:
                    meta: dict = {}
                    _attach_revisions(meta, child)
                    blocks.append({"text": text, "type": "Paragraph", "meta": meta})

            elif child.tag == TBLNS:
                tbl_obj = top_level_tables.get(id(child))
                if tbl_obj:
                    self._extract_table(tbl_obj, blocks, nested=False)

    def _extract_table(self, table, blocks: list, nested: bool = False):
        """Extract text from table cells, deduplicating merged cells."""
        seen_tcs = []
        for row in table.rows:
            for cell in row.cells:
                tc = cell._tc
                if any(s is tc for s in seen_tcs):
                    continue
                seen_tcs.append(tc)

                # Get cell text excluding nested table text
                text = cell_text_excluding_nested(cell).strip()
                if text:
                    meta = {"nested": nested}
                    _attach_revisions(meta, tc)
                    blocks.append({"text": text, "type": "TableCell", "meta": meta})

                # Recurse into nested tables
                for nested_table in cell.tables:
                    self._extract_table(nested_table, blocks, nested=True)

    def _extract_headers(self, doc, blocks: list):
        """Extract text from section headers."""
        for sec_idx, section in enumerate(doc.sections):
            for variant, attr in [
                ("default", "header"),
                ("first_page", "first_page_header"),
                ("even_page", "even_page_header"),
            ]:
                hdr = getattr(section, attr, None)
                if hdr is None:
                    continue
                if hdr.is_linked_to_previous:
                    continue
                for para in hdr.paragraphs:
                    text = para.text.strip()
                    if text:
                        meta: dict = {"section_idx": sec_idx, "variant": variant}
                        _attach_revisions(meta, para._element)
                        blocks.append({
                            "text": text,
                            "type": "Header",
                            "meta": meta,
                        })

    def _extract_footers(self, doc, blocks: list):
        """Extract text from section footers."""
        for sec_idx, section in enumerate(doc.sections):
            for variant, attr in [
                ("default", "footer"),
                ("first_page", "first_page_footer"),
                ("even_page", "even_page_footer"),
            ]:
                ftr = getattr(section, attr, None)
                if ftr is None:
                    continue
                if ftr.is_linked_to_previous:
                    continue
                for para in ftr.paragraphs:
                    text = para.text.strip()
                    if text:
                        meta: dict = {"section_idx": sec_idx, "variant": variant}
                        _attach_revisions(meta, para._element)
                        blocks.append({
                            "text": text,
                            "type": "Footer",
                            "meta": meta,
                        })

    def _extract_footnotes(self, doc, blocks: list):
        """Extract text from footnotes via raw XML."""
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
            if text:
                meta: dict = {"footnote_id": fn_id}
                _attach_revisions(meta, fn)
                blocks.append({
                    "text": text,
                    "type": "Footnote",
                    "meta": meta,
                })

    def _extract_endnotes(self, doc, blocks: list):
        """Extract text from endnotes via raw XML."""
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
            if text:
                meta: dict = {"endnote_id": en_id}
                _attach_revisions(meta, en)
                blocks.append({
                    "text": text,
                    "type": "Endnote",
                    "meta": meta,
                })

    def _extract_text_boxes(self, doc, blocks: list):
        """Extract text from text boxes (w:txbxContent elements)."""
        body = doc.element.body
        for txbx in body.iter(TXBX_CONTENT):
            parts = []
            for t_node in txbx.iter(TNS):
                if t_node.text:
                    parts.append(t_node.text)
            text = "".join(parts).strip()
            if text:
                meta: dict = {}
                _attach_revisions(meta, txbx)
                blocks.append({
                    "text": text,
                    "type": "TextBox",
                    "meta": meta,
                })
