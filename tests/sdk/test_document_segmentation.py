"""Tests for document segmentation strategies."""

from transmax_sdk.documents.strategies import (
    SentenceStrategy,
    ParagraphStrategy,
    PageStrategy,
)
from transmax_sdk.documents.manager import DefaultDocumentManager


class TestSentenceStrategy:
    def test_basic_sentences(self):
        s = SentenceStrategy()
        result = s.segment("First sentence. Second sentence. Third sentence.")
        assert len(result) == 3

    def test_question_marks(self):
        s = SentenceStrategy()
        result = s.segment("What is this? It is a test. Really!")
        assert len(result) == 3

    def test_empty_text(self):
        s = SentenceStrategy()
        assert s.segment("") == []

    def test_single_sentence(self):
        s = SentenceStrategy()
        result = s.segment("Just one sentence.")
        assert len(result) == 1


class TestParagraphStrategy:
    def test_two_paragraphs(self):
        p = ParagraphStrategy()
        result = p.segment("First paragraph.\n\nSecond paragraph.")
        assert len(result) == 2

    def test_multiple_newlines(self):
        p = ParagraphStrategy()
        result = p.segment("Para 1.\n\n\nPara 2.\n\n\n\nPara 3.")
        assert len(result) == 3

    def test_single_paragraph(self):
        p = ParagraphStrategy()
        result = p.segment("Single paragraph with no breaks.")
        assert len(result) == 1


class TestPageStrategy:
    def test_form_feed(self):
        p = PageStrategy()
        result = p.segment("Page 1 content.\fPage 2 content.")
        assert len(result) == 2

    def test_page_marker(self):
        p = PageStrategy()
        result = p.segment("Page 1.---PAGE BREAK---Page 2.")
        assert len(result) == 2

    def test_single_page(self):
        p = PageStrategy()
        result = p.segment("Just one page of content.")
        assert len(result) == 1


class TestDocumentManager:
    def test_segment_text_sentence(self):
        dm = DefaultDocumentManager()
        result = dm.segment_text("First. Second. Third.", "sentence")
        assert len(result) == 3

    def test_segment_text_paragraph(self):
        dm = DefaultDocumentManager()
        result = dm.segment_text("Para 1.\n\nPara 2.", "paragraph")
        assert len(result) == 2

    def test_text_to_segments(self):
        dm = DefaultDocumentManager()
        segs = dm.text_to_segments("First. Second.", "sentence", "doc_1")
        assert len(segs) == 2
        assert segs[0].segment_id == "doc_1_seg_0"
        assert segs[0].order_index == 0
        assert segs[1].segment_id == "doc_1_seg_1"

    def test_invalid_strategy_raises(self):
        dm = DefaultDocumentManager()
        try:
            dm.segment_text("Test", "nonexistent")
            assert False
        except ValueError:
            pass

    def test_register_custom_strategy(self):
        dm = DefaultDocumentManager()

        class LineStrategy:
            name = "line"
            def segment(self, text):
                return [l.strip() for l in text.split("\n") if l.strip()]

        dm.register_strategy("line", LineStrategy())
        result = dm.segment_text("Line 1\nLine 2\nLine 3", "line")
        assert len(result) == 3
