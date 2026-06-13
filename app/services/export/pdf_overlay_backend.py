"""
TMX-EXPORT-1 — PDF->PDF overlay export backend (ADR-0006 Tier-1).

Preserve-everything-except-text: keep the source page intact (images, vector
graphics, table rules, colour fills, side boxes, mastheads) and only swap the
translatable text. Per-block decisions are delegated to the format-agnostic
intelligence services so the backend never branches on a source type:

    collect geometry -> classify (content/preserve/drop-cap)
                     -> translate CONTENT (+ drop-cap body) via injected fn
                     -> resolve font + negotiate fit
                     -> redact source glyphs (fill=None keeps background)
                     -> re-insert translation; re-seat drop-cap initial
                     -> emit a FidelityReport

Requires PyMuPDF (``fitz``). Missing -> ExporterUnavailable (A3, never a silent
fallback). PyMuPDF is AGPL — a licence review gates shipping this in product.
"""
from __future__ import annotations

import statistics
from typing import Optional

from app.services.export.base import (
    BlockVerdict,
    ExporterUnavailable,
    ExportResult,
    FidelityReport,
    FitStrategy,
    LayoutBlock,
    TranslateFn,
    Translatability,
)
from app.services.export import classify as _classify
from app.services.export import fonts as _fonts
from app.services.export import layout as _layout


def _serif_default(_: str) -> bool:  # pragma: no cover - tiny shim
    return False


def collect_layout_blocks(doc, page_indices: Optional[list[int]] = None) -> list[LayoutBlock]:
    """Extract generic LayoutBlocks from a fitz document (one per text block)."""
    import fitz  # local import — keeps the dep optional

    pages = page_indices if page_indices is not None else range(doc.page_count)
    out: list[LayoutBlock] = []
    for pno in pages:
        page = doc[pno]
        pw, ph = page.rect.width, page.rect.height
        for bi, b in enumerate(page.get_text("dict")["blocks"]):
            if b["type"] != 0:
                continue
            spans = [s for ln in b["lines"] for s in ln["spans"] if s["text"].strip()]
            if not spans:
                continue
            line_texts, line_bboxes = [], []
            for ln in b["lines"]:
                lt = "".join(s["text"] for s in ln["spans"])
                if lt.strip():
                    line_texts.append(lt)
                    line_bboxes.append(tuple(ln["bbox"]))
            text = " ".join(" ".join(line_texts).split())
            if not text:
                continue
            dom = max(spans, key=lambda s: len(s["text"]))
            out.append(LayoutBlock(
                block_id=f"p{pno}b{bi}",
                text=text,
                bbox=tuple(b["bbox"]),
                line_bboxes=tuple(line_bboxes),
                font_name=dom["font"],
                size=round(float(dom["size"]), 2),
                color=int(dom["color"]),
                page_index=pno,
                page_width=pw,
                page_height=ph,
            ))
    return out


def _color_rgb(c: int) -> tuple[float, float, float]:
    return ((c >> 16 & 255) / 255, (c >> 8 & 255) / 255, (c & 255) / 255)


def _pair_dropcap(cap: LayoutBlock, content: list[LayoutBlock]) -> Optional[LayoutBlock]:
    """The body block a drop-cap initial belongs to: same page, starts to the
    right of / below the cap and vertically overlapping its top."""
    cands = []
    cx1, cy0, cy1 = cap.bbox[2], cap.bbox[1], cap.bbox[3]
    for b in content:
        if b.page_index != cap.page_index:
            continue
        bx0, by0, by1 = b.bbox[0], b.bbox[1], b.bbox[3]
        vertically_near = by0 <= cy1 and by1 >= cy0
        to_the_right = bx0 >= cx1 - 2
        if vertically_near and to_the_right:
            cands.append((bx0, b))
    if not cands:
        return None
    return min(cands, key=lambda t: t[0])[1]


class PdfOverlayExporter:
    name = "pdf_overlay"

    def supports(self, file_ext: str) -> bool:
        return file_ext.lower().lstrip(".") == "pdf"

    def export(self, source_path: str, translate_fn: TranslateFn,
               target_lang: str, *, page_indices: Optional[list[int]] = None,
               glossary: frozenset = frozenset()) -> ExportResult:
        try:
            import fitz  # noqa: F401
        except ImportError as e:  # A3 — fail loud, no silent downgrade
            raise ExporterUnavailable(
                "pdf_overlay backend requires PyMuPDF (fitz); it is not installed."
            ) from e

        doc = fitz.open(source_path)
        blocks = collect_layout_blocks(doc, page_indices)
        profile = _classify.build_profile(blocks)

        # 1) classify every block
        kinds = {b.block_id: _classify.classify(b, profile, glossary=glossary)
                 for b in blocks}
        content = [b for b in blocks if kinds[b.block_id] is Translatability.CONTENT]

        # 2) translate CONTENT blocks in one batched call (A2/A6 via injected fn)
        translations = translate_fn([b.text for b in content]) if content else []
        if len(translations) != len(content):
            raise ValueError(
                f"translate_fn returned {len(translations)} for {len(content)} blocks"
            )
        tr_by_id = {b.block_id: t for b, t in zip(content, translations)}

        verdicts: list[BlockVerdict] = []
        measure = self._make_measure(fitz)

        # 3) per page: redact source text of non-PRESERVE blocks, then re-render
        for pno in {b.page_index for b in blocks}:
            page = doc[pno]
            page_blocks = [b for b in blocks if b.page_index == pno]

            # drop-cap pairing (needs translated body text)
            dropcap_letter: dict[str, str] = {}
            for cap in [b for b in page_blocks if kinds[b.block_id] is Translatability.DROP_CAP]:
                body = _pair_dropcap(cap, content)
                if body is not None and tr_by_id.get(body.block_id):
                    first = tr_by_id[body.block_id].strip()[:1].upper()
                    if first:
                        dropcap_letter[cap.block_id] = first

            # redact glyphs of everything we will re-render (fill=None preserves bg)
            for b in page_blocks:
                kind = kinds[b.block_id]
                if kind is Translatability.PRESERVE:
                    continue
                if kind is Translatability.DROP_CAP and b.block_id not in dropcap_letter:
                    continue  # unpaired drop-cap: keep the original initial
                for lb in b.line_bboxes:
                    page.add_redact_annot(fitz.Rect(lb), fill=None)
            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

            # re-insert
            for b in page_blocks:
                kind = kinds[b.block_id]
                if kind is Translatability.PRESERVE:
                    verdicts.append(BlockVerdict(b.block_id, pno, kind, note="kept source"))
                    continue
                if kind is Translatability.DROP_CAP:
                    letter = dropcap_letter.get(b.block_id)
                    if not letter:
                        verdicts.append(BlockVerdict(b.block_id, pno, kind,
                                                     note="unpaired; original kept"))
                        continue
                    cap_fc = _fonts.resolve(b.font_name, letter)
                    page.insert_textbox(fitz.Rect(b.bbox), letter, fontsize=b.size,
                                        fontname=cap_fc.fontname, fontfile=cap_fc.fontfile,
                                        color=_color_rgb(b.color), align=fitz.TEXT_ALIGN_LEFT)
                    verdicts.append(BlockVerdict(b.block_id, pno, kind,
                                                 strategy=FitStrategy.IN_PLACE,
                                                 note="drop-cap re-seated"))
                    continue

                # CONTENT
                text = tr_by_id.get(b.block_id, "").strip()
                if not text:
                    verdicts.append(BlockVerdict(b.block_id, pno, kind, note="empty translation"))
                    continue
                fc = _fonts.resolve(b.font_name, text)
                is_heading = b.size >= 14 or len(text) < 60
                align = fitz.TEXT_ALIGN_LEFT if is_heading else fitz.TEXT_ALIGN_JUSTIFY
                fit = _layout.negotiate(text, b.bbox, fc.fontname, fc.fontfile,
                                        b.size, b.page_height, measure)
                page.insert_textbox(fitz.Rect(fit.rect), text, fontsize=fit.fontsize,
                                    fontname=fc.fontname, fontfile=fc.fontfile,
                                    color=_color_rgb(b.color), align=align)
                verdicts.append(BlockVerdict(
                    b.block_id, pno, kind, strategy=fit.strategy,
                    font_substituted=fc.substituted, fitted_size=fit.fontsize,
                    overflow=fit.overflow,
                    note=fc.reason if not fc.charset_ok else "",
                ))

        out = doc.tobytes(garbage=4, deflate=True)
        report = FidelityReport(backend=self.name, source_filename=source_path,
                                target_lang=target_lang, verdicts=verdicts)
        return ExportResult(data=out, media_type="application/pdf", fidelity=report)

    @staticmethod
    def _make_measure(fitz):
        """A fitz-backed text measurer for layout.negotiate (insert into a scratch
        page; positive return = it fit)."""
        def measure(text: str, width: float, height: float, fontname: str,
                    fontfile, size: float) -> float:
            scratch = fitz.open()
            pg = scratch.new_page(width=max(width, 1) + 4, height=max(height, 1) + 4)
            leftover = pg.insert_textbox(
                fitz.Rect(0, 0, max(width, 1), max(height, 1)), text,
                fontsize=size, fontname=fontname, fontfile=fontfile,
                align=fitz.TEXT_ALIGN_LEFT,
            )
            scratch.close()
            return leftover
        return measure
