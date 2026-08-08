"""Tests for pipeline any-to-any language routing."""

import pytest
from transmax_sdk.pipeline.pipeline import DefaultTranslationPipeline
from transmax_sdk.types import TranslationRequest, TranslationSegment, RouteStrategy


class TestPipelineAnyToAny:
    @pytest.mark.asyncio
    async def test_direct_route(self):
        pipeline = DefaultTranslationPipeline(allow_passthrough=True)
        request = TranslationRequest(
            segments=[TranslationSegment(segment_id="s1", source_text="Bonjour")],
            source_lang="fr",
            target_lang="de",
        )
        result = await pipeline.execute(request)
        assert result.route_strategy == RouteStrategy.DIRECT

    @pytest.mark.asyncio
    async def test_pivot_route(self):
        pipeline = DefaultTranslationPipeline(allow_passthrough=True)
        request = TranslationRequest(
            segments=[TranslationSegment(segment_id="s1", source_text="テスト")],
            source_lang="ja",
            target_lang="ar",
        )
        result = await pipeline.execute(request)
        assert result.route_strategy == RouteStrategy.PIVOT_ENGLISH

    @pytest.mark.asyncio
    async def test_source_lang_propagated(self):
        pipeline = DefaultTranslationPipeline(allow_passthrough=True)
        request = TranslationRequest(
            segments=[TranslationSegment(segment_id="s1", source_text="Test")],
            source_lang="ko",
            target_lang="vi",
        )
        result = await pipeline.execute(request)
        assert result.source_lang == "ko"
        assert result.target_lang == "vi"
