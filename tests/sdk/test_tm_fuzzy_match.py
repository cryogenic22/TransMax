"""Tests for TM fuzzy matching."""

from transmax_sdk.memory.tm import VectorTranslationMemory


class TestTMFuzzyMatch:
    def test_fuzzy_match_similar_text(self):
        tm = VectorTranslationMemory(fuzzy_threshold=0.5)
        tm.store("Take 10mg daily with food", "Prendre 10mg par jour avec nourriture", "en", "fr")
        # Very similar but not exact
        result = tm.find_match("Take 10mg daily with meals", "en", "fr")
        assert result is not None
        assert result["type"] == "fuzzy"
        assert result["score"] >= 0.5

    def test_fuzzy_match_below_threshold(self):
        tm = VectorTranslationMemory(fuzzy_threshold=0.95)
        tm.store("Take 10mg daily", "Prendre 10mg par jour", "en", "fr")
        result = tm.find_match("Completely different sentence", "en", "fr")
        assert result is None

    def test_exact_preferred_over_fuzzy(self):
        tm = VectorTranslationMemory(fuzzy_threshold=0.5)
        tm.store("Take daily", "Prendre quotidiennement", "en", "fr")
        result = tm.find_match("Take daily", "en", "fr")
        assert result["type"] == "exact"

    def test_fuzzy_respects_lang_pair(self):
        tm = VectorTranslationMemory(fuzzy_threshold=0.5)
        tm.store("Take medication daily", "Tomar medicación diariamente", "en", "es")
        # Look for French - should not match Spanish entry
        result = tm.find_match("Take medication daily now", "en", "fr")
        assert result is None
