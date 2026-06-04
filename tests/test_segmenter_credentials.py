"""TMX-3801 — segmenter hardening: initials, credentials, and PDF wiring.

Reproduces the NEJM-manuscript failure mode (author bylines + credentials
shattered into junk fragments by naive '.'-splitting) and proves the hardened
segmenter keeps them whole, and that PDF ingestion now uses it.
"""
from __future__ import annotations

from app.services.segmenter import get_segmenter

SEG = get_segmenter("en")


def test_author_byline_with_initials_and_credentials_stays_whole():
    """The exact pattern that shattered: middle initials + M.D. credentials."""
    byline = (
        "Fernando P. Polack, M.D., Stephen J. Thomas, M.D., "
        "Nicholas Kitchin, M.D., Judith Absalon, M.D."
    )
    out = SEG.segment(byline)
    # The whole byline is one unit — initials (P., J.) and M.D. don't split it.
    assert out == [byline], out


def test_single_initial_is_not_a_boundary():
    # The real NEJM reprint address: middle initial 'N.' must not split; the
    # comma after 'Rd.' already prevents a split there.
    addr = "401 N. Middletown Rd., Pearl River, NY 10965"
    assert SEG.segment(addr) == [addr], SEG.segment(addr)


def test_plural_doctor_title_not_a_boundary():
    assert SEG.segment("Drs. Polack and Thomas contributed equally.") == [
        "Drs. Polack and Thomas contributed equally."
    ]


def test_real_sentence_boundaries_still_split():
    out = SEG.segment("Safe vaccines are needed. The trial enrolled 43,548 participants.")
    assert out == [
        "Safe vaccines are needed.",
        "The trial enrolled 43,548 participants.",
    ]


def test_credential_can_end_a_sentence():
    # 'M.D.' followed by a clear new sentence still splits.
    out = SEG.segment("He is John Perez, M.D. The results were positive.")
    assert out == ["He is John Perez, M.D.", "The results were positive."]


def test_decimal_and_dose_abbrev_not_split():
    assert SEG.segment("Take 5.5 mg b.i.d. with food.") == ["Take 5.5 mg b.i.d. with food."]


def test_pdf_service_delegates_to_segmenter():
    """PDF ingestion no longer naive-splits — it uses the shared segmenter."""
    from app.services.pdf_service import PDFService

    text = "Fernando P. Polack, M.D., Stephen J. Thomas, M.D."
    out = PDFService()._split_sentences(text)
    assert out == [text], out
