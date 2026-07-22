"""Tests for pipeline integration with smart routing."""

import pytest
from transmax_sdk import TransMaxSDK
from transmax_sdk.config import SDKConfig
from transmax_sdk.container import SDKContainer
from transmax_sdk.language.smart_router import SmartRouter
from transmax_sdk.telemetry.noop import NoOpTelemetry
from transmax_sdk.types import TranslationStatus


class TestPipelineSmartRouting:
    def test_multi_provider_creates_smart_router(self):
        """When multiple API keys are set, container creates SmartRouter."""
        config = SDKConfig(
            openai_api_key="test-openai",
            gemini_api_key="test-gemini",
        )
        container = SDKContainer(config=config, telemetry=NoOpTelemetry())
        container._register_defaults()
        router = container.resolve("router")
        assert isinstance(router, SmartRouter)

    def test_single_provider_creates_any_to_any(self):
        """With only one provider, AnyToAnyRouter is used (no smart routing)."""
        from transmax_sdk.language.router import AnyToAnyRouter

        config = SDKConfig(openai_api_key="test-openai")
        container = SDKContainer(config=config, telemetry=NoOpTelemetry())
        container._register_defaults()
        router = container.resolve("router")
        assert isinstance(router, AnyToAnyRouter)
        assert not isinstance(router, SmartRouter)

    @pytest.mark.asyncio
    async def test_headless_pipeline_with_smart_router(self):
        """Pipeline still works headless even with SmartRouter configured."""
        sdk = TransMaxSDK(config={"allow_passthrough": True})
        result = await sdk.translate(
            "Take 10mg ibuprofen daily.",
            target_lang="fr",
            source_lang="en",
        )
        assert result.source_lang == "en"
        assert result.target_lang == "fr"
        assert len(result.segments) == 1
        assert result.status in (
            TranslationStatus.PASS,
            TranslationStatus.REVIEW_REQUIRED,
        )
