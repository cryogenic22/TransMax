"""
TMX-PARSE-1 — pluggable parser backends + canonical IR.

Deterministic + fast: the pypdf backend is exercised with a faked PdfReader and
the Docling/Azure/Google backends are tested for their CONTRACT (label mapping,
fail-loud on unavailable) without running a heavy model convert.
"""
import pytest

from app.services.parsing import (
    ElementType,
    ParsedBlock,
    ParsedDocument,
    ParserError,
    ParserUnavailable,
    available_backends,
    get_parser,
)


# --- AC-1: canonical IR + legacy adapter ------------------------------------


def test_ir_to_legacy_blocks_shape():
    doc = ParsedDocument(
        source_filename="x.pdf",
        backend="docling",
        blocks=[
            ParsedBlock(text="Intro", element_type=ElementType.SECTION_HEADER, order_index=1, page_no=1),
            ParsedBlock(text="a,b", element_type=ElementType.TABLE, order_index=2,
                        table_grid=[["a", "b"]]),
        ],
    )
    legacy = doc.to_legacy_blocks()
    assert legacy[0] == {
        "text": "Intro",
        "type": "section_header",
        "meta": {"backend": "docling", "page_no": 1},
    }
    # table_grid is carried through meta for a future export step
    assert legacy[1]["type"] == "table"
    assert legacy[1]["meta"]["table_grid"] == [["a", "b"]]
    assert doc.structure_histogram() == {"section_header": 1, "table": 1}


# --- AC-2: registry + factory -----------------------------------------------


def test_registry_lists_all_backends():
    assert set(available_backends()) == {"pypdf", "docling", "azure", "google"}


def test_get_parser_unknown_name_fails_loud():
    with pytest.raises(ParserError, match="Unknown parser backend"):
        get_parser("nope")


def test_get_parser_default_is_pypdf(monkeypatch):
    # AC-6: default behaviour is unchanged — settings default selects pypdf.
    parser = get_parser()  # settings.parser_backend defaults to "pypdf"
    assert parser.name == "pypdf"


def test_get_parser_honours_explicit_name():
    assert get_parser("docling").name == "docling"
    assert get_parser("azure").name == "azure"


# --- AC-3: pypdf backend (faked reader, deterministic) ----------------------


def test_pypdf_backend_produces_ir(tmp_path, monkeypatch):
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    class _FakePage:
        def __init__(self, t):
            self._t = t

        def extract_text(self):
            return self._t

    class _FakeReader:
        def __init__(self, _path):
            self.pages = [_FakePage("Hello world."), _FakePage(""), _FakePage("Third.")]

    monkeypatch.setattr("pypdf.PdfReader", _FakeReader)

    doc = get_parser("pypdf").parse(str(pdf))
    assert doc.backend == "pypdf"
    assert doc.page_count == 3
    # blank page skipped; two TEXT blocks, reading order preserved
    assert [b.text for b in doc.blocks] == ["Hello world.", "Third."]
    assert all(b.element_type is ElementType.TEXT for b in doc.blocks)
    assert doc.blocks[0].page_no == 1 and doc.blocks[1].page_no == 3


def test_pypdf_backend_missing_file_fails_loud():
    with pytest.raises(ParserError, match="not found"):
        get_parser("pypdf").parse("does-not-exist.pdf")


# --- AC-4: Docling label mapping + import-guard -----------------------------


def test_docling_label_mapping():
    from app.services.parsing.docling_backend import _canon

    class _Lbl:
        def __init__(self, v):
            self.value = v

    assert _canon(_Lbl("section_header")) is ElementType.SECTION_HEADER
    assert _canon(_Lbl("list_item")) is ElementType.LIST_ITEM
    assert _canon(_Lbl("table")) is ElementType.TABLE
    assert _canon(_Lbl("picture")) is ElementType.FIGURE
    assert _canon(_Lbl("footnote")) is ElementType.FOOTNOTE
    assert _canon(_Lbl("something_new")) is ElementType.OTHER


def test_docling_unavailable_fails_loud(tmp_path, monkeypatch):
    f = tmp_path / "d.pdf"
    f.write_bytes(b"%PDF-1.4 fake")
    parser = get_parser("docling")
    # Simulate Docling import/init failure -> must raise ParserUnavailable,
    # NEVER silently downgrade (A3).
    monkeypatch.setattr(parser, "_converter", lambda: (_ for _ in ()).throw(RuntimeError("no docling")))
    with pytest.raises(ParserUnavailable):
        parser.parse(str(f))


# --- AC-5: cloud connectors fail loud when SDK/creds absent ------------------


def test_azure_backend_fails_loud_without_sdk(tmp_path):
    f = tmp_path / "a.pdf"
    f.write_bytes(b"%PDF-1.4 fake")
    # azure-ai-documentintelligence is not installed in this env -> loud.
    with pytest.raises(ParserUnavailable):
        get_parser("azure").parse(str(f))


def test_google_backend_fails_loud_without_sdk(tmp_path):
    f = tmp_path / "g.pdf"
    f.write_bytes(b"%PDF-1.4 fake")
    with pytest.raises(ParserUnavailable):
        get_parser("google").parse(str(f))


def test_cloud_backends_support_pdf():
    assert get_parser("azure").supports(".pdf")
    assert get_parser("google").supports("pdf")
