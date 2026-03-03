"""Tests for TM exact hash matching."""

from transmax_sdk.memory.tm import VectorTranslationMemory


class TestTMExactMatch:
    def test_exact_match_found(self):
        tm = VectorTranslationMemory()
        tm.store("Take 10mg daily", "Prendre 10mg par jour", "en", "fr")
        result = tm.find_match("Take 10mg daily", "en", "fr")
        assert result is not None
        assert result["type"] == "exact"
        assert result["score"] == 1.0
        assert result["target"] == "Prendre 10mg par jour"

    def test_exact_match_case_insensitive(self):
        tm = VectorTranslationMemory()
        tm.store("Take daily", "Prendre quotidiennement", "en", "fr")
        result = tm.find_match("take daily", "en", "fr")
        assert result is not None
        assert result["type"] == "exact"

    def test_no_match_returns_none(self):
        tm = VectorTranslationMemory()
        result = tm.find_match("Hello", "en", "fr")
        assert result is None

    def test_wrong_lang_pair_no_match(self):
        tm = VectorTranslationMemory()
        tm.store("Hello", "Bonjour", "en", "fr")
        result = tm.find_match("Hello", "en", "de")
        assert result is None

    def test_multiple_entries_correct_match(self):
        tm = VectorTranslationMemory()
        tm.store("Hello", "Bonjour", "en", "fr")
        tm.store("Hello", "Hallo", "en", "de")
        result_fr = tm.find_match("Hello", "en", "fr")
        result_de = tm.find_match("Hello", "en", "de")
        assert result_fr["target"] == "Bonjour"
        assert result_de["target"] == "Hallo"

    def test_store_and_size(self):
        tm = VectorTranslationMemory()
        assert tm.size == 0
        tm.store("A", "B", "en", "fr")
        assert tm.size == 1

    def test_clear(self):
        tm = VectorTranslationMemory()
        tm.store("A", "B", "en", "fr")
        tm.clear()
        assert tm.size == 0
        assert tm.find_match("A", "en", "fr") is None
