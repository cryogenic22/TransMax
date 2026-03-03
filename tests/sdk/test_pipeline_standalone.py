"""Tests for pipeline running standalone (headless, no DB, no real LLM)."""

import pytest
from transmax_sdk.pipeline.pipeline import DefaultTranslationPipeline
from transmax_sdk.types import TranslationRequest, TranslationSegment, TranslationStatus


class TestPipelineStandalone:
    @pytest.mark.asyncio
    async def test_runs_without_llm(self):
        """Pipeline runs in headless mode with passthrough translations."""
        pipeline = DefaultTranslationPipeline()
        request = TranslationRequest(
            segments=[TranslationSegment(segment_id="s1", source_text="Hello world")],
            source_lang="en",
            target_lang="fr",
        )
        result = await pipeline.execute(request)
        assert result.source_lang == "en"
        assert result.target_lang == "fr"
        assert len(result.segments) == 1
        assert result.segments[0].translated_text  # Not empty

    @pytest.mark.asyncio
    async def test_multiple_segments(self):
        pipeline = DefaultTranslationPipeline()
        request = TranslationRequest(
            segments=[
                TranslationSegment(segment_id="s1", source_text="Take daily"),
                TranslationSegment(segment_id="s2", source_text="With food"),
            ],
            source_lang="en",
            target_lang="fr",
        )
        result = await pipeline.execute(request)
        assert len(result.segments) == 2

    @pytest.mark.asyncio
    async def test_tm_bypass_works(self):
        """Exact TM match skips LLM entirely."""
        from transmax_sdk.memory.tm import VectorTranslationMemory
        tm = VectorTranslationMemory()
        tm.store("Take 10mg daily", "Prendre 10mg par jour", "en", "fr")

        pipeline = DefaultTranslationPipeline(tm=tm)
        request = TranslationRequest(
            segments=[TranslationSegment(segment_id="s1", source_text="Take 10mg daily")],
            source_lang="en",
            target_lang="fr",
        )
        result = await pipeline.execute(request)
        assert result.segments[0].translated_text == "Prendre 10mg par jour"
        assert result.segments[0].translation_source == "TM_EXACT"
        assert result.segments[0].confidence == 100.0

    @pytest.mark.asyncio
    async def test_result_has_status(self):
        pipeline = DefaultTranslationPipeline()
        request = TranslationRequest(
            segments=[TranslationSegment(segment_id="s1", source_text="Hello")],
            source_lang="en",
            target_lang="fr",
        )
        result = await pipeline.execute(request)
        assert result.status in (TranslationStatus.PASS, TranslationStatus.REVIEW_REQUIRED, TranslationStatus.BLOCKED)

    @pytest.mark.asyncio
    async def test_result_to_dict(self):
        pipeline = DefaultTranslationPipeline()
        request = TranslationRequest(
            segments=[TranslationSegment(segment_id="s1", source_text="Hello")],
            source_lang="en",
            target_lang="fr",
        )
        result = await pipeline.execute(request)
        data = result.to_dict()
        assert "segments" in data
        assert "source_lang" in data
        assert "status" in data
