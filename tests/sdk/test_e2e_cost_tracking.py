"""End-to-end cost tracking tests."""

import pytest
from transmax_sdk import TransMaxSDK


class TestE2ECostTracking:
    @pytest.mark.asyncio
    async def test_no_llm_zero_cost(self):
        sdk = TransMaxSDK()
        result = await sdk.translate("Hello", target_lang="fr", source_lang="en")
        assert result.total_cost_usd == 0.0

    @pytest.mark.asyncio
    async def test_tm_bypass_zero_cost(self):
        sdk = TransMaxSDK()
        tm = sdk.container.resolve("tm")
        tm.store("Hello", "Bonjour", "en", "fr")

        result = await sdk.translate("Hello", target_lang="fr", source_lang="en")
        assert result.total_cost_usd == 0.0

    def test_cost_estimation(self):
        sdk = TransMaxSDK()
        cost = sdk.estimate_cost("Take 10mg ibuprofen twice daily with food after meals")
        assert cost > 0
        assert cost < 1.0  # Shouldn't cost a dollar for one sentence

    def test_cost_tracker_accessible(self):
        sdk = TransMaxSDK()
        tracker = sdk.container.resolve("cost_tracker")
        assert tracker.total_cost == 0.0
