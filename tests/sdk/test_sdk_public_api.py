"""Tests for TransMaxSDK public API (facade)."""

import pytest
from transmax_sdk import TransMaxSDK, SDKConfig


class TestTransMaxSDKPublicAPI:
    def test_init_default(self):
        sdk = TransMaxSDK()
        assert sdk.config is not None

    def test_init_with_dict(self):
        sdk = TransMaxSDK(config={"openai_api_key": "test-key"})
        assert sdk.config.openai_api_key == "test-key"

    def test_init_with_config(self):
        config = SDKConfig(openai_api_key="test-key")
        sdk = TransMaxSDK(config=config)
        assert sdk.config.openai_api_key == "test-key"

    def test_detect_language(self):
        sdk = TransMaxSDK()
        result = sdk.detect_language("This is an English sentence about medicine.")
        assert result.lang_code == "en"
        assert result.confidence > 0.5

    def test_plan_route_direct(self):
        sdk = TransMaxSDK()
        from transmax_sdk.types import RouteStrategy

        route = sdk.plan_route("en", "fr")
        assert route == RouteStrategy.DIRECT

    def test_plan_route_pivot(self):
        sdk = TransMaxSDK()
        from transmax_sdk.types import RouteStrategy

        route = sdk.plan_route("ja", "ar")
        assert route == RouteStrategy.PIVOT_ENGLISH

    def test_estimate_cost(self):
        sdk = TransMaxSDK()
        cost = sdk.estimate_cost("Take 10mg daily with food")
        assert cost > 0

    @pytest.mark.asyncio
    async def test_translate_headless(self):
        sdk = TransMaxSDK(config={"allow_passthrough": True})
        result = await sdk.translate("Hello world", target_lang="fr", source_lang="en")
        assert result.source_lang == "en"
        assert result.target_lang == "fr"
        assert len(result.segments) == 1
        assert result.translated_text  # Not empty

    @pytest.mark.asyncio
    async def test_translate_multiple_segments(self):
        sdk = TransMaxSDK(config={"allow_passthrough": True})
        result = await sdk.translate(
            ["Take daily", "With food"],
            target_lang="fr",
            source_lang="en",
        )
        assert len(result.segments) == 2

    @pytest.mark.asyncio
    async def test_quality_check(self):
        sdk = TransMaxSDK()
        defects = await sdk.quality_check(
            source_text="Take 10mg daily",
            translated_text="Prendre quotidiennement",
            source_lang="en",
            target_lang="fr",
        )
        # Should find missing number 10
        assert len(defects) > 0

    @pytest.mark.asyncio
    async def test_translate_auto_detect(self):
        sdk = TransMaxSDK(config={"allow_passthrough": True})
        result = await sdk.translate(
            "Ceci est une phrase en français.",
            target_lang="en",
        )
        assert result.source_lang == "fr"

    def test_container_accessible(self):
        sdk = TransMaxSDK()
        assert sdk.container is not None
        assert sdk.container.has("quality_gate")
        assert sdk.container.has("pipeline")
        assert sdk.container.has("tm")
        assert sdk.container.has("audit")
