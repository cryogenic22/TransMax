"""Tests for glossary management."""

from transmax_sdk.memory.glossary import GlossaryManager


class TestGlossaryManager:
    def test_add_and_lookup(self):
        gm = GlossaryManager()
        gm.add_term("adverse event", "événement indésirable", "en", "fr")
        matches = gm.lookup("adverse event", "fr")
        assert len(matches) == 1
        assert matches[0]["target_text"] == "événement indésirable"

    def test_lookup_case_insensitive(self):
        gm = GlossaryManager()
        gm.add_term("Adverse Event", "événement indésirable", "en", "fr")
        matches = gm.lookup("adverse event", "fr")
        assert len(matches) == 1

    def test_lookup_no_match(self):
        gm = GlossaryManager()
        gm.add_term("adverse event", "événement indésirable", "en", "fr")
        matches = gm.lookup("different term", "fr")
        assert len(matches) == 0

    def test_lookup_filters_by_target_lang(self):
        gm = GlossaryManager()
        gm.add_term("adverse event", "événement indésirable", "en", "fr")
        gm.add_term("adverse event", "Nebenwirkung", "en", "de")
        matches = gm.lookup("adverse event", "fr")
        assert len(matches) == 1
        assert matches[0]["target_text"] == "événement indésirable"

    def test_get_terms_for_pair(self):
        gm = GlossaryManager()
        gm.add_term("drug", "médicament", "en", "fr")
        gm.add_term("dose", "dose", "en", "fr")
        gm.add_term("drug", "Medikament", "en", "de")
        terms = gm.get_terms_for_pair("en", "fr")
        assert len(terms) == 2

    def test_bulk_load(self):
        gm = GlossaryManager()
        gm.load_terms([
            {"source_text": "a", "target_text": "b", "source_lang": "en", "target_lang": "fr"},
            {"source_text": "c", "target_text": "d", "source_lang": "en", "target_lang": "fr"},
        ])
        assert gm.size == 2

    def test_clear(self):
        gm = GlossaryManager()
        gm.add_term("a", "b", "en", "fr")
        gm.clear()
        assert gm.size == 0

    def test_forbidden_term(self):
        gm = GlossaryManager()
        gm.add_term("deprecated_term", "x", "en", "fr", is_forbidden=True)
        matches = gm.lookup("deprecated_term", "fr")
        assert matches[0]["is_forbidden"] is True
