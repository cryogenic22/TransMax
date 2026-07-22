"""End-to-end tests for any-to-any language support."""

import pytest
from transmax_sdk import TransMaxSDK
from transmax_sdk.types import RouteStrategy


class TestE2EAnyToAny:
    @pytest.mark.asyncio
    async def test_fr_to_de(self):
        sdk = TransMaxSDK(config={"allow_passthrough": True})
        result = await sdk.translate(
            "Bonjour le monde", target_lang="de", source_lang="fr"
        )
        assert result.source_lang == "fr"
        assert result.target_lang == "de"
        assert result.route_strategy == RouteStrategy.DIRECT

    @pytest.mark.asyncio
    async def test_ja_to_ar_uses_pivot(self):
        sdk = TransMaxSDK(config={"allow_passthrough": True})
        result = await sdk.translate("テスト", target_lang="ar", source_lang="ja")
        assert result.route_strategy == RouteStrategy.PIVOT_ENGLISH

    @pytest.mark.asyncio
    async def test_auto_detect_french(self):
        sdk = TransMaxSDK(config={"allow_passthrough": True})
        result = await sdk.translate(
            "Ceci est une phrase en français sur les médicaments.",
            target_lang="de",
        )
        assert result.source_lang == "fr"

    @pytest.mark.asyncio
    async def test_auto_detect_german(self):
        sdk = TransMaxSDK(config={"allow_passthrough": True})
        result = await sdk.translate(
            "Dies ist ein deutscher Satz über Medikamente.",
            target_lang="fr",
        )
        assert result.source_lang == "de"
