"""Tests for Gemini LLM provider."""

from transmax_sdk.config import SDKConfig
from transmax_sdk.container import SDKContainer
from transmax_sdk.llm.gemini_provider import GeminiProvider
from transmax_sdk.llm.protocol import LLMProviderProtocol
from transmax_sdk.telemetry.noop import NoOpTelemetry


class TestGeminiProvider:
    def test_satisfies_protocol(self):
        provider = GeminiProvider(api_key="test-key")
        assert isinstance(provider, LLMProviderProtocol)

    def test_name(self):
        provider = GeminiProvider(api_key="test-key")
        assert provider.name == "gemini"

    def test_default_model(self):
        provider = GeminiProvider(api_key="test-key")
        assert provider._default_model == "gemini-2.0-flash"

    def test_custom_model(self):
        provider = GeminiProvider(api_key="test-key", default_model="gemini-2.5-pro")
        assert provider._default_model == "gemini-2.5-pro"

    def test_container_wires_gemini_when_only_key(self):
        """Container should create GeminiProvider when only gemini_api_key is set."""
        config = SDKConfig(gemini_api_key="test-gemini-key")
        container = SDKContainer(config=config, telemetry=NoOpTelemetry())
        container._register_defaults()
        provider = container.resolve("llm_provider")
        assert provider is not None
        assert provider.name == "gemini"
