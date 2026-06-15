"""TMX-EXPORT-1 — Tier-2 pdf_render: re-typeset IR to PDF (no Docling needed).

Drives the render() path with synthetic IR blocks + an injected translator, so it
is fast and deterministic. Asserts structural fidelity (content + tables present,
translated) and the honest figure-loss flag.
"""
import pytest

from app.services.export.registry import get_exporter

fitz = pytest.importorskip("fitz")  # PyMuPDF is optional (AGPL); only to read PDF text

IR = [
    {"text": "Safety and Efficacy of the Vaccine", "element_type": "title"},
    {"text": "Methods", "element_type": "section_header"},
    {"text": "The recommended dose is fifty milligrams once daily.", "element_type": "text"},
    {"text": "n engl j med 383;27", "element_type": "page_footer"},   # chrome -> dropped
    {"text": "", "element_type": "figure"},                          # figure -> placeholder
    {"text": "", "element_type": "table",
     "table_grid": [["Group", "Dose"], ["Adults", "50 mg"], ["Elderly", "25 mg"]]},
    {"text": "Adverse events were mild.", "element_type": "list_item"},
]


def _fake_translate(texts):
    return [f"[FR]{t}" for t in texts]


def test_render_produces_pdf_with_translated_content():
    exporter = get_exporter("pdf_render")
    result = exporter.render(IR, _fake_translate, target_lang="fr",
                             source_filename="sample.pdf")
    assert result.media_type == "application/pdf"
    assert result.data[:4] == b"%PDF"

    text = "".join(p.get_text() for p in fitz.open(stream=result.data, filetype="pdf"))
    # prose + heading + table cells translated and present
    assert "[FR]Safety and Efficacy of the Vaccine" in text
    assert "[FR]Methods" in text
    assert "[FR]Group" in text and "[FR]50 mg" in text     # table cells
    # chrome (running footer) dropped from the reflow
    assert "n engl j med" not in text


def test_render_flags_figure_loss():
    result = get_exporter("pdf_render").render(IR, _fake_translate, target_lang="fr")
    figs = [v for v in result.fidelity.verdicts if v.note and "figure" in v.note]
    assert figs and figs[0].overflow is True          # honest: figure not re-rendered
    assert result.fidelity.degraded is True           # report says so


def test_render_count_mismatch_fails_loud():
    with pytest.raises(ValueError):
        get_exporter("pdf_render").render(IR, lambda t: ["one"], target_lang="fr")


def test_pdf_render_registered():
    assert get_exporter("pdf_render").name == "pdf_render"


# --- IR disposition (chrome / brand / content) -----------------------------

def test_ir_disposition_translate_verbatim_drop():
    from app.services.export.classify import build_ir_repeats, ir_disposition

    blocks = [
        {"text": "The recommended dose is 50 mg.", "element_type": "text", "page_no": 1},
        {"text": "n engl j med 383;27", "element_type": "text", "page_no": 1},   # repeats
        {"text": "n engl j med 383;28", "element_type": "text", "page_no": 2},   # repeats
        {"text": "Running header", "element_type": "page_header", "page_no": 1},  # chrome
        {"text": "DOI: 10.1056/NEJMoa2034577", "element_type": "text", "page_no": 3},
        {"text": "The New England Journal of Medicine", "element_type": "text", "page_no": 1},
    ]
    repeats = build_ir_repeats(blocks)
    g = frozenset({"the new england journal of medicine"})
    assert ir_disposition(blocks[0], repeats) == "translate"
    assert ir_disposition(blocks[1], repeats) == "drop"        # repeated folio
    assert ir_disposition(blocks[3], repeats) == "drop"        # page_header type
    assert ir_disposition(blocks[4], repeats) == "verbatim"    # DOI identifier
    assert ir_disposition(blocks[5], repeats, glossary=g) == "verbatim"  # brand glossary


def test_render_keeps_brand_verbatim_drops_chrome():
    ir = [
        {"text": "The New England Journal of Medicine", "element_type": "text", "page_no": 1},
        {"text": "Page 1", "element_type": "page_footer", "page_no": 1},
        {"text": "Adults received the vaccine.", "element_type": "text", "page_no": 1},
    ]
    res = get_exporter("pdf_render").render(
        ir, lambda ts: [f"[FR]{t}" for t in ts], target_lang="fr",
        glossary=frozenset({"the new england journal of medicine"}))
    text = "".join(p.get_text() for p in fitz.open(stream=res.data, filetype="pdf"))
    assert "The New England Journal of Medicine" in text   # brand kept, NOT translated
    assert "[FR]The New England" not in text
    assert "[FR]Adults received the vaccine." in text       # prose translated
    assert "Page 1" not in text                             # chrome footer dropped


# --- figure rasterisation (pypdfium2, permissive) --------------------------

def test_pdf_raster_renders_region():
    import os
    from app.services.export import pdf_raster
    src = r"C:\Users\kapil\Downloads\sample_files_test\Manucript 1 (1).pdf"
    if not (pdf_raster.is_available() and os.path.exists(src)):
        import pytest
        pytest.skip("pypdfium2 or sample PDF unavailable")
    png = pdf_raster.render_region(src, 1, (60.0, 700.0, 300.0, 500.0),
                                   coord_origin="BOTTOMLEFT")
    assert png is not None and png[:8] == b"\x89PNG\r\n\x1a\n"
