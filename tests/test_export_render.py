"""TMX-EXPORT-1 — Tier-2 pdf_render: re-typeset IR to PDF (no Docling needed).

Drives the render() path with synthetic IR blocks + an injected translator, so it
is fast and deterministic. Asserts structural fidelity (content + tables present,
translated) and the honest figure-loss flag.
"""
import fitz  # only to read back the produced PDF text
import pytest

from app.services.export.base import Translatability
from app.services.export.registry import get_exporter

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
