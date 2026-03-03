"""Tests for language capability matrix."""

from transmax_sdk.language.capabilities import (
    CapabilityMatrix,
    DEFAULT_CAPABILITY_MATRIX,
    LanguageCapability,
)


class TestLanguageCapability:
    def test_dataclass_fields(self):
        cap = LanguageCapability("openai", "en", "fr", 0.95, 2, "gpt-4o")
        assert cap.provider == "openai"
        assert cap.source_lang == "en"
        assert cap.target_lang == "fr"
        assert cap.confidence == 0.95
        assert cap.cost_tier == 2
        assert cap.default_model == "gpt-4o"

    def test_frozen(self):
        cap = LanguageCapability("openai", "en", "fr", 0.95, 2, "gpt-4o")
        try:
            cap.confidence = 0.5  # type: ignore
            assert False, "Should be frozen"
        except AttributeError:
            pass


class TestCapabilityMatrix:
    def test_exact_lookup(self):
        cap = DEFAULT_CAPABILITY_MATRIX.get("openai", "en", "fr")
        assert cap is not None
        assert cap.provider == "openai"
        assert cap.confidence == 0.95

    def test_exact_lookup_miss(self):
        result = DEFAULT_CAPABILITY_MATRIX.get("openai", "xx", "yy")
        assert result is None

    def test_best_for_pair_returns_highest_confidence(self):
        best = DEFAULT_CAPABILITY_MATRIX.get_best_for_pair("en", "fr")
        assert best is not None
        # OpenAI has 0.95 for en-fr, highest among providers
        assert best.provider == "openai"
        assert best.confidence == 0.95

    def test_best_for_pair_with_provider_filter(self):
        best = DEFAULT_CAPABILITY_MATRIX.get_best_for_pair(
            "en", "fr", available_providers={"gemini"}
        )
        assert best is not None
        assert best.provider == "gemini"

    def test_best_for_pair_unknown_pair(self):
        best = DEFAULT_CAPABILITY_MATRIX.get_best_for_pair("xx", "yy")
        assert best is None

    def test_confidence_for_pair(self):
        conf = DEFAULT_CAPABILITY_MATRIX.confidence_for_pair("en", "fr")
        assert conf == 0.95

    def test_confidence_for_pair_unknown(self):
        conf = DEFAULT_CAPABILITY_MATRIX.confidence_for_pair("xx", "yy")
        assert conf == 0.0

    def test_supported_languages_count(self):
        langs = DEFAULT_CAPABILITY_MATRIX.supported_languages()
        assert len(langs) >= 20

    def test_gemini_excels_at_indic(self):
        """Gemini should be best for en->hi (Indic strength)."""
        best = DEFAULT_CAPABILITY_MATRIX.get_best_for_pair("en", "hi")
        assert best is not None
        assert best.provider == "gemini"
        assert best.confidence >= 0.90

    def test_providers_for_pair_sorted(self):
        caps = DEFAULT_CAPABILITY_MATRIX.providers_for_pair("en", "fr")
        assert len(caps) == 3
        # Should be sorted descending by confidence
        assert caps[0].confidence >= caps[1].confidence >= caps[2].confidence

    def test_custom_matrix(self):
        caps = [
            LanguageCapability("custom", "en", "zz", 0.99, 1, "custom-model"),
        ]
        matrix = CapabilityMatrix(caps)
        assert matrix.get("custom", "en", "zz") is not None
        assert len(matrix.supported_languages()) == 2
