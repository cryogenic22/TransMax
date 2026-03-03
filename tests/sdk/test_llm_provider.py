"""Tests for LLM provider protocol compliance."""

from transmax_sdk.llm.protocol import LLMProviderProtocol
from transmax_sdk.llm.openai_provider import OpenAIProvider
from transmax_sdk.llm.anthropic_provider import AnthropicProvider


class TestLLMProviderProtocol:
    def test_openai_satisfies_protocol(self):
        provider = OpenAIProvider(api_key="test-key")
        assert isinstance(provider, LLMProviderProtocol)
        assert provider.name == "openai"

    def test_anthropic_satisfies_protocol(self):
        provider = AnthropicProvider(api_key="test-key")
        assert isinstance(provider, LLMProviderProtocol)
        assert provider.name == "anthropic"
