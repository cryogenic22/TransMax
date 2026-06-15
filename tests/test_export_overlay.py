"""TMX-EXPORT-1 — pdf_overlay integration: preserve chrome, translate content.

Builds a synthetic 2-page PDF (repeated masthead + body) so the test is
self-contained and asserts the registry-level behaviour end to end with an
injected (no-LLM) translator.
"""
import pytest

from app.services.export.base import Translatability
from app.services.export.registry import get_exporter

fitz = pytest.importorskip("fitz")  # PyMuPDF is optional (AGPL); skip module if absent


@pytest.fixture
def sample_pdf(tmp_path):
    doc = fitz.open()
    for pno in range(2):
        page = doc.new_page(width=595, height=792)
        # repeated masthead near the top (display size) -> chrome by repetition
        page.insert_textbox(fitz.Rect(72, 26, 523, 76), "Acme Medical Journal",
                            fontsize=26, fontname="tiro", align=fitz.TEXT_ALIGN_CENTER)
        # body paragraph (genuinely distinct prose per page) -> content
        bodies = [
            "The recommended starting dose is fifty milligrams once daily for "
            "adult patients with essential hypertension and stable renal function.",
            "Adverse events were generally mild and transient, resolving without "
            "intervention; no treatment-related deaths occurred during the study.",
        ]
        page.insert_textbox(fitz.Rect(72, 120, 523, 300), bodies[pno],
                            fontsize=11, fontname="helv")
    path = str(tmp_path / "sample.pdf")
    doc.save(path)
    return path


def _fake_translate(texts):
    # deterministic, non-empty, visibly different from source
    return [f"[FR] {t}" for t in texts]


def test_overlay_preserves_masthead_translates_body(sample_pdf):
    exporter = get_exporter("pdf_overlay")
    result = exporter.export(sample_pdf, _fake_translate, target_lang="fr")

    assert result.media_type == "application/pdf"
    out = fitz.open(stream=result.data, filetype="pdf")
    page0_text = out[0].get_text()

    # masthead preserved verbatim (NOT translated)
    assert "Acme Medical Journal" in page0_text
    assert "[FR] Acme Medical Journal" not in page0_text
    # body translated in place
    assert "[FR]" in page0_text
    assert "body paragraph number 0" not in page0_text  # source removed

    # fidelity report classified the masthead as PRESERVE on both pages
    preserved = [v for v in result.fidelity.verdicts
                 if v.translatability is Translatability.PRESERVE]
    content = [v for v in result.fidelity.verdicts
               if v.translatability is Translatability.CONTENT]
    assert len(preserved) >= 2      # masthead on 2 pages
    assert len(content) >= 2        # body on 2 pages
    assert "by_translatability" in result.fidelity.summary()


def test_overlay_count_matches_translation(sample_pdf):
    exporter = get_exporter("pdf_overlay")
    # translate_fn returning the wrong count must fail loud
    with pytest.raises(ValueError):
        exporter.export(sample_pdf, lambda texts: ["only one"], target_lang="fr")
