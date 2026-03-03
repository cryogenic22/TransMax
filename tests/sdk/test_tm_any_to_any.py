"""Tests for TM with any-to-any language pairs."""

from transmax_sdk.memory.tm import VectorTranslationMemory


class TestTMAnyToAny:
    def test_fr_to_de(self):
        tm = VectorTranslationMemory()
        tm.store("Prendre quotidiennement", "Täglich einnehmen", "fr", "de")
        result = tm.find_match("Prendre quotidiennement", "fr", "de")
        assert result is not None
        assert result["target"] == "Täglich einnehmen"

    def test_ja_to_ar(self):
        tm = VectorTranslationMemory()
        tm.store("毎日服用", "تناول يومياً", "ja", "ar")
        result = tm.find_match("毎日服用", "ja", "ar")
        assert result is not None
        assert result["target"] == "تناول يومياً"

    def test_mixed_pairs_isolated(self):
        tm = VectorTranslationMemory()
        tm.store("Hello", "Bonjour", "en", "fr")
        tm.store("Hello", "Hola", "en", "es")
        tm.store("Bonjour", "Hallo", "fr", "de")

        assert tm.find_match("Hello", "en", "fr")["target"] == "Bonjour"
        assert tm.find_match("Hello", "en", "es")["target"] == "Hola"
        assert tm.find_match("Bonjour", "fr", "de")["target"] == "Hallo"
        assert tm.find_match("Hello", "fr", "de") is None
