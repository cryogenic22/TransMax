"""TMX-EXPORT-WIRE — download route routes PDF formats through the export registry."""
import pytest

from app.api.documents import _export_via_backend

fitz = pytest.importorskip("fitz")  # PyMuPDF is optional (AGPL); skip module if absent


class _Doc:
    def __init__(self, path, file_type="pdf", target_language="fr"):
        self.file_path = path
        self.file_type = file_type
        self.target_language = target_language


@pytest.fixture
def pdf_source(tmp_path):
    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    page.insert_textbox(fitz.Rect(40, 40, 360, 120),
                        "The recommended dose is fifty milligrams once daily.",
                        fontsize=11, fontname="helv")
    p = str(tmp_path / "src.pdf")
    doc.save(p)
    return p


def _segs():
    return [{"source_text": "The recommended dose is fifty milligrams once daily.",
             "translated_text": "La dose recommandée est de cinquante milligrammes par jour."}]


def test_pdf_overlay_reuses_translations(pdf_source):
    buf = _export_via_backend("pdf_overlay", _Doc(pdf_source), _segs())
    data = buf.getvalue()
    assert data[:4] == b"%PDF"
    text = "".join(p.get_text() for p in fitz.open(stream=data, filetype="pdf"))
    assert "cinquante milligrammes" in text          # used the existing translation
    assert "fifty milligrams" not in text            # source replaced


def test_pdf_render_produces_pdf(pdf_source):
    # uses the default parser backend (pypdf) — no Docling needed for the smoke
    data = _export_via_backend("pdf_render", _Doc(pdf_source), _segs()).getvalue()
    assert data[:4] == b"%PDF"


def test_overlay_rejects_non_pdf_source(tmp_path):
    from fastapi import HTTPException
    docx = str(tmp_path / "src.docx")
    open(docx, "wb").close()
    with pytest.raises(HTTPException) as ei:
        _export_via_backend("pdf_overlay", _Doc(docx, file_type="docx"), _segs())
    assert ei.value.status_code == 400


def test_missing_source_fails_loud():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as ei:
        _export_via_backend("pdf_render", _Doc("/no/such/file.pdf"), _segs())
    assert ei.value.status_code == 400
