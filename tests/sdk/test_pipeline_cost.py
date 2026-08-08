"""Tests for cost tracking in pipeline."""

import pytest
from transmax_sdk.pipeline.pipeline import DefaultTranslationPipeline
from transmax_sdk.types import TranslationRequest, TranslationSegment


class TestPipelineCost:
    @pytest.mark.asyncio
    async def test_no_llm_zero_cost(self):
        """Without LLM provider (explicit passthrough opt-in), cost is zero."""
        pipeline = DefaultTranslationPipeline(allow_passthrough=True)
        request = TranslationRequest(
            segments=[TranslationSegment(segment_id="s1", source_text="Hello")],
            source_lang="en",
            target_lang="fr",
        )
        result = await pipeline.execute(request)
        assert result.total_cost_usd == 0.0

    @pytest.mark.asyncio
    async def test_tm_bypass_zero_cost(self):
        from transmax_sdk.memory.tm import VectorTranslationMemory

        tm = VectorTranslationMemory()
        tm.store("Hello", "Bonjour", "en", "fr")

        pipeline = DefaultTranslationPipeline(tm=tm)
        request = TranslationRequest(
            segments=[TranslationSegment(segment_id="s1", source_text="Hello")],
            source_lang="en",
            target_lang="fr",
        )
        result = await pipeline.execute(request)
        assert result.total_cost_usd == 0.0
