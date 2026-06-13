"""
TMX-EXPORT-1 — Tier-2 PDF re-render export backend (ADR-0006).

Parse a PDF into the canonical IR (Docling: headings / paragraphs / lists /
tables / captions / reading order), translate, then RE-TYPESET to a fresh PDF
with reportlab. This is *structural* fidelity, not pixel fidelity: the output is
a clean, reflowed document that preserves content + reading order + tables, but
NOT the source's exact layout / colours / fonts / figures.

Why it exists: it reflows naturally (translation expansion never clips), scales
to long narrative documents (CSRs), and uses only permissively-licensed deps
(Docling + reportlab) — no PyMuPDF/AGPL. Complementary to the Tier-1 overlay,
which keeps the exact look but does not reflow and needs PyMuPDF.

Honest losses vs Tier-1 (recorded in the FidelityReport): exact visual layout,
in-place colours/branding, embedded figures (re-rendered as flagged
placeholders — the IR carries figure position, not the bitmap).
"""
from __future__ import annotations

import io
from typing import Optional

from app.services.export.base import (
    BlockVerdict,
    ExportResult,
    FidelityReport,
    FitStrategy,
    TranslateFn,
    Translatability,
)
from app.services.export import fonts as _fonts

# Canonical ElementType values (ADR-0005). Kept as strings so this module does
# not import the parsing package just for the enum.
_TRANSLATABLE = {"title", "section_header", "text", "list_item", "caption",
                 "footnote", "other"}
_CHROME = {"page_header", "page_footer"}
_FIGURE = "figure"
_TABLE = "table"


def _xml_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class PdfRenderExporter:
    name = "pdf_render"

    def supports(self, file_ext: str) -> bool:
        return file_ext.lower().lstrip(".") in {"pdf", "docx", "pptx", "html"}

    # -- public API ---------------------------------------------------------

    def export(self, source_path: str, translate_fn: TranslateFn, target_lang: str,
               *, parser_name: Optional[str] = None) -> ExportResult:
        from app.services.parsing.registry import get_parser

        parsed = get_parser(parser_name).parse(source_path)
        blocks = [
            {
                "text": b.text,
                "element_type": b.element_type.value,
                "table_grid": b.table_grid,
            }
            for b in parsed.blocks
        ]
        return self.render(blocks, translate_fn, target_lang,
                           source_filename=parsed.source_filename)

    def render(self, blocks: list[dict], translate_fn: TranslateFn, target_lang: str,
               *, source_filename: str = "") -> ExportResult:
        """Re-typeset IR ``blocks`` (dicts with text/element_type/table_grid) to PDF.

        Separated from parsing so it is unit-testable without Docling.
        """
        # 1) gather every translatable string in order (prose blocks + table cells)
        strings: list[str] = []
        plan: list[tuple] = []   # (kind, block, payload) describing how to render
        for b in blocks:
            etype = (b.get("element_type") or "text").lower()
            if etype == _FIGURE:
                plan.append(("figure", b, None))
            elif etype == _TABLE and b.get("table_grid"):
                grid = b["table_grid"]
                idxs = []
                for row in grid:
                    row_idx = []
                    for cell in row:
                        row_idx.append(len(strings))
                        strings.append(str(cell))
                    idxs.append(row_idx)
                plan.append(("table", b, idxs))
            elif etype in _CHROME:
                plan.append(("chrome", b, None))     # dropped from the flow
            elif etype in _TRANSLATABLE and (b.get("text") or "").strip():
                plan.append((etype, b, len(strings)))
                strings.append(b["text"])
            else:
                plan.append(("skip", b, None))

        translations = translate_fn(strings) if strings else []
        if len(translations) != len(strings):
            raise ValueError(
                f"translate_fn returned {len(translations)} for {len(strings)} strings"
            )

        # 2) build flowables + verdicts
        flowables, verdicts = self._build_flowables(plan, translations, target_lang)

        # 3) render to PDF bytes
        data = self._typeset(flowables)
        report = FidelityReport(backend=self.name, source_filename=source_filename,
                                target_lang=target_lang, verdicts=verdicts)
        return ExportResult(data=data, media_type="application/pdf", fidelity=report)

    # -- rendering ----------------------------------------------------------

    def _styles(self):
        from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        # Register a Unicode serif (DejaVu) so French typography renders — reportlab
        # base-14 is Latin-1 only (same œ/em-dash limit as the overlay).
        body_font, bold_font = "Times-Roman", "Times-Bold"
        reg = _fonts._locate("DejaVuSerif.ttf")
        regb = _fonts._locate("DejaVuSerif-Bold.ttf")
        if reg:
            try:
                pdfmetrics.registerFont(TTFont("TMXSerif", reg))
                body_font = "TMXSerif"
                if regb:
                    pdfmetrics.registerFont(TTFont("TMXSerif-Bold", regb))
                    bold_font = "TMXSerif-Bold"
                else:
                    bold_font = "TMXSerif"
            except Exception:  # noqa: BLE001 - already-registered or IO; fall back
                body_font, bold_font = "TMXSerif", "TMXSerif"

        return {
            "title": ParagraphStyle("t", fontName=bold_font, fontSize=17, leading=21,
                                    spaceAfter=12, textColor=(0.04, 0.15, 0.42)),
            "section_header": ParagraphStyle("h", fontName=bold_font, fontSize=12.5,
                                             leading=15, spaceBefore=10, spaceAfter=5,
                                             textColor=(0.04, 0.15, 0.42)),
            "text": ParagraphStyle("b", fontName=body_font, fontSize=10, leading=13.5,
                                   alignment=TA_JUSTIFY, spaceAfter=6),
            "list_item": ParagraphStyle("li", fontName=body_font, fontSize=10,
                                        leading=13.5, leftIndent=14, bulletIndent=4,
                                        spaceAfter=3),
            "caption": ParagraphStyle("c", fontName=body_font, fontSize=8.5, leading=11,
                                      alignment=TA_LEFT, spaceAfter=6,
                                      textColor=(0.3, 0.3, 0.3)),
            "footnote": ParagraphStyle("fn", fontName=body_font, fontSize=8, leading=10,
                                       textColor=(0.3, 0.3, 0.3), spaceAfter=3),
            "other": ParagraphStyle("o", fontName=body_font, fontSize=10, leading=13.5,
                                    spaceAfter=6),
            "_body_font": body_font, "_bold_font": bold_font,
        }

    def _build_flowables(self, plan, translations, target_lang):
        from reportlab.lib import colors
        from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

        st = self._styles()
        flow, verdicts = [], []
        for kind, b, payload in plan:
            if kind == "figure":
                flow.append(self._figure_placeholder(st))
                verdicts.append(BlockVerdict("figure", 0, Translatability.PRESERVE,
                                             overflow=True,
                                             note="figure bitmap not re-rendered (Tier-2 limit)"))
            elif kind == "chrome":
                verdicts.append(BlockVerdict("chrome", 0, Translatability.PRESERVE,
                                             note="running head/footer dropped from reflow"))
            elif kind == "table":
                data = [[Paragraph(_xml_escape(translations[i]), st["caption"])
                         for i in row] for row in payload]
                tbl = Table(data, repeatRows=1)
                tbl.setStyle(TableStyle([
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9fb3d1")),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbe5f1")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ]))
                flow.append(tbl)
                flow.append(Spacer(1, 8))
                verdicts.append(BlockVerdict("table", 0, Translatability.CONTENT,
                                             strategy=FitStrategy.REFLOWED))
            elif kind == "skip":
                continue
            else:  # a translatable prose block
                text = _xml_escape(translations[payload])
                style = st.get(kind, st["text"])
                bullet = "•" if kind == "list_item" else None
                flow.append(Paragraph(text, style, bulletText=bullet))
                verdicts.append(BlockVerdict(kind, 0, Translatability.CONTENT,
                                             strategy=FitStrategy.REFLOWED,
                                             font_substituted=True))
        return flow, verdicts

    @staticmethod
    def _figure_placeholder(st):
        from reportlab.lib import colors
        from reportlab.platypus import Table, TableStyle

        ph = Table([["[ figure — not re-rendered in Tier-2 ]"]], colWidths=[400],
                   rowHeights=[46])
        ph.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#bbbbbb")),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f3f3f3")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#888888")),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("FONTNAME", (0, 0), (-1, -1), st["_body_font"]),
        ]))
        return ph

    @staticmethod
    def _typeset(flowables) -> bytes:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=54, rightMargin=54,
                                topMargin=54, bottomMargin=54, title="Translated document")
        doc.build(flowables or [])
        return buf.getvalue()
