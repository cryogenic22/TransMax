"""TMX-EXPORT-1 — translatability classifier (the 'not hard-coded' core)."""
from app.services.export.base import LayoutBlock, Translatability
from app.services.export.classify import build_profile, classify


def _blk(text, *, size=10.0, y0=400.0, page=0, ph=792.0, font="Helvetica", bid=None):
    bid = bid or f"p{page}-{abs(hash(text)) % 9999}"
    return LayoutBlock(block_id=bid, text=text, bbox=(72, y0, 520, y0 + size + 2),
                       line_bboxes=((72, y0, 520, y0 + size + 2),), font_name=font,
                       size=size, color=0x000000, page_index=page,
                       page_width=595.0, page_height=ph)


def test_body_text_is_content():
    body = _blk("The recommended starting dose is 50 mg once daily for adults.")
    prof = build_profile([body])
    assert classify(body, prof) is Translatability.CONTENT


def test_masthead_repeated_across_pages_is_preserved():
    # same wordmark on two pages -> chrome by repetition, no source-name hard-code
    m1 = _blk("The New England Journal of Medicine", size=28, y0=40, page=0)
    m2 = _blk("The New England Journal of Medicine", size=28, y0=40, page=1)
    body = _blk("A" * 80, page=0)
    prof = build_profile([m1, m2, body])
    assert classify(m1, prof) is Translatability.PRESERVE
    assert classify(m2, prof) is Translatability.PRESERVE


def test_folio_with_varying_page_number_is_preserved():
    # digit-insensitive normalization makes "n engl j med 383;27" repeat
    f1 = _blk("n engl j med 383;27", size=8, y0=760, page=0)
    f2 = _blk("n engl j med 383;28", size=8, y0=760, page=1)
    prof = build_profile([f1, f2, _blk("B" * 90)])
    assert classify(f1, prof) is Translatability.PRESERVE


def test_identifier_doi_is_preserved():
    doi = _blk("DOI: 10.1056/NEJMoa2034577", size=8, y0=770)
    prof = build_profile([doi, _blk("C" * 90)])
    assert classify(doi, prof) is Translatability.PRESERVE


def test_dropcap_initial_detected():
    cap = _blk("C", size=36, y0=120)
    prof = build_profile([cap, _blk("D" * 120, size=10)])
    assert classify(cap, prof) is Translatability.DROP_CAP


def test_single_page_masthead_top_band_fallback():
    # no repetition signal (one page) -> top-band + display size catches it
    m = _blk("Acme Pharma Bulletin", size=24, y0=20, page=0)
    prof = build_profile([m, _blk("E" * 120, size=10, y0=400)])
    assert classify(m, prof) is Translatability.PRESERVE


def test_glossary_term_preserved():
    brand = _blk("Cardiomel", size=10, y0=400)
    prof = build_profile([brand, _blk("F" * 90)])
    assert classify(brand, prof, glossary=frozenset({"cardiomel"})) is Translatability.PRESERVE
    # without the glossary it is ordinary content
    assert classify(brand, prof) is Translatability.CONTENT
