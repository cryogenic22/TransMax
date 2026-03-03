"""Tests for TM bypass in pipeline (exact matches skip LLM)."""

import pytest
from transmax_sdk.memory.tm import VectorTranslationMemory
from transmax_sdk.pipeline.pipeline import DefaultTranslationPipeline
from transmax_sdk.types import TranslationRequest, TranslationSegment


class TestPipelineTMBypass:
    @pytest.mark.asyncio
    async def test_all_tm_hits_zero_llm(self):
        """When all segments have TM matches, no LLM call is needed."""
        tm = VectorTranslationMemory()
        tm.store("Hello", "Bonjour", "en", "fr")
        tm.store("World", "Monde", "en", "fr")

        pipeline = DefaultTranslationPipeline(tm=tm, llm_provider=None)
        request = TranslationRequest(
            segments=[
                TranslationSegment(segment_id="s1", source_text="Hello"),
                TranslationSegment(segment_id="s2", source_text="World"),
            ],
            source_lang="en",
            target_lang="fr",
        )
        result = await pipeline.execute(request)
        assert result.segments[0].translation_source == "TM_EXACT"
        assert result.segments[1].translation_source == "TM_EXACT"
        assert result.total_cost_usd == 0.0

    @pytest.mark.asyncio
    async def test_partial_tm_hits(self):
        """Mix of TM hits and passthrough translations."""
        tm = VectorTranslationMemory()
        tm.store("Hello", "Bonjour", "en", "fr")

        pipeline = DefaultTranslationPipeline(tm=tm)
        request = TranslationRequest(
            segments=[
                TranslationSegment(segment_id="s1", source_text="Hello"),
                TranslationSegment(segment_id="s2", source_text="New sentence"),
            ],
            source_lang="en",
            target_lang="fr",
        )
        result = await pipeline.execute(request)
        assert result.segments[0].translation_source == "TM_EXACT"
        assert result.segments[1].translation_source == "MT"
