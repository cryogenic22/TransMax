"""TMX-PAGECOUNT-1 — PDF page count reflects real pages, not block/segment count.

Reproduces the UI defect: a 13-page PDF showed "316 pages" because page_count
was len(blocks) (the segment count). count_pages must report the actual pages.
"""
from __future__ import annotations

import pypdf

from app.services.pdf_service import PDFService


def _make_pdf(path, pages: int) -> None:
    w = pypdf.PdfWriter()
    for _ in range(pages):
        w.add_blank_page(width=200, height=200)
    with open(path, "wb") as f:
        w.write(f)


def test_count_pages_returns_real_page_count(tmp_path):
    p = tmp_path / "multi.pdf"
    _make_pdf(p, 5)
    # 5 pages — NOT a block/segment count.
    assert PDFService().count_pages(str(p)) == 5


def test_count_pages_single_page(tmp_path):
    p = tmp_path / "one.pdf"
    _make_pdf(p, 1)
    assert PDFService().count_pages(str(p)) == 1


def test_count_pages_falls_back_to_one_on_bad_file(tmp_path):
    bad = tmp_path / "not_a_pdf.txt"
    bad.write_text("hello, not a pdf")
    # Never raises; never reports a wrong count.
    assert PDFService().count_pages(str(bad)) == 1
