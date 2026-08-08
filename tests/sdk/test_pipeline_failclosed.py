"""TMX-SDK-FAILCLOSED (A3): the SDK pipeline fails closed with typed errors.

Red-stop RS-02: no fabricated passthrough labelled "MT", no silently
swallowed model-response parse failures.
"""

import hashlib
import json
from typing import Dict, List, Optional

import pytest

from transmax_sdk import TransMaxSDK
from transmax_sdk.errors import (
    InvalidModelResponseError,
    ProviderUnavailableError,
    TransMaxSDKError,
)
from transmax_sdk.pipeline.pipeline import DefaultTranslationPipeline
from transmax_sdk.types import TranslationRequest, TranslationSegment


class CannedLLMProvider:
    """Minimal LLMProviderProtocol stand-in returning a fixed payload."""

    def __init__(self, content: str) -> None:
        self._content = content

    @property
    def name(self) -> str:
        return "canned"

    async def complete(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, str]:
        return {"content": self._content, "model": "canned-1"}


def _request() -> TranslationRequest:
    return TranslationRequest(
        segments=[TranslationSegment(segment_id="s1", source_text="Take 10mg daily")],
        source_lang="en",
        target_lang="fr",
    )


class TestProviderUnavailable:
    @pytest.mark.asyncio
    async def test_no_provider_raises_typed_error(self):
        """AC-1: no provider + no opt-in -> typed raise, never a fabricated MT."""
        pipeline = DefaultTranslationPipeline()
        with pytest.raises(ProviderUnavailableError) as exc_info:
            await pipeline.execute(_request())
        assert exc_info.value.code == "PROVIDER_UNAVAILABLE"
        assert isinstance(exc_info.value, TransMaxSDKError)

    @pytest.mark.asyncio
    async def test_error_message_names_the_opt_in(self):
        """AC-1: the raise is actionable — it names the explicit opt-in."""
        pipeline = DefaultTranslationPipeline()
        with pytest.raises(ProviderUnavailableError) as exc_info:
            await pipeline.execute(_request())
        assert "allow_passthrough" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_tm_covered_request_needs_no_provider(self):
        """A fully TM-covered request never needs a provider: no raise."""
        from transmax_sdk.memory.tm import VectorTranslationMemory

        tm = VectorTranslationMemory()
        tm.store("Take 10mg daily", "Prendre 10mg par jour", "en", "fr")
        pipeline = DefaultTranslationPipeline(tm=tm)
        result = await pipeline.execute(_request())
        assert result.segments[0].translation_source == "TM_EXACT"


class TestPassthroughOptIn:
    @pytest.mark.asyncio
    async def test_passthrough_is_honestly_labelled(self):
        """AC-2: opt-in passthrough returns source text, never labelled MT."""
        pipeline = DefaultTranslationPipeline(allow_passthrough=True)
        result = await pipeline.execute(_request())
        seg = result.segments[0]
        assert seg.translated_text == "Take 10mg daily"  # unaltered source
        assert seg.translation_source == "PASSTHROUGH_UNTRANSLATED"
        assert seg.translation_source != "MT"

    @pytest.mark.asyncio
    async def test_sdk_facade_passthrough_via_config(self):
        """AC-2: the opt-in flows through SDKConfig -> container -> pipeline."""
        sdk = TransMaxSDK(config={"allow_passthrough": True})
        result = await sdk.translate("Hello world", target_lang="fr", source_lang="en")
        assert result.segments[0].translation_source == "PASSTHROUGH_UNTRANSLATED"
        assert result.segments[0].translated_text == "Hello world"

    @pytest.mark.asyncio
    async def test_sdk_facade_default_fails_closed(self):
        """AC-1: the default (no opt-in) SDK facade raises, end to end."""
        sdk = TransMaxSDK()
        with pytest.raises(ProviderUnavailableError):
            await sdk.translate("Hello world", target_lang="fr", source_lang="en")


class TestInvalidModelResponse:
    @pytest.mark.asyncio
    async def test_corrupt_json_raises_typed_error(self):
        """AC-3: unparseable model output raises, never a silent {}."""
        payload = "not json {{{"
        pipeline = DefaultTranslationPipeline(llm_provider=CannedLLMProvider(payload))
        with pytest.raises(InvalidModelResponseError) as exc_info:
            await pipeline.execute(_request())
        err = exc_info.value
        assert err.code == "INVALID_MODEL_RESPONSE"
        assert err.raw_length == len(payload)
        assert err.raw_sha256 == hashlib.sha256(payload.encode("utf-8")).hexdigest()
        # The payload itself must never ride inside the error (may be regulated content).
        assert payload not in str(err)

    @pytest.mark.asyncio
    async def test_missing_target_text_key_raises_typed_error(self):
        """AC-3: schema-shaped JSON missing required keys is a parse failure."""
        payload = json.dumps({"segments": [{"segment_id": "s1"}]})
        pipeline = DefaultTranslationPipeline(llm_provider=CannedLLMProvider(payload))
        with pytest.raises(InvalidModelResponseError):
            await pipeline.execute(_request())

    @pytest.mark.asyncio
    async def test_non_object_json_raises_typed_error(self):
        """AC-3: valid JSON that is not an object is a parse failure, typed."""
        pipeline = DefaultTranslationPipeline(
            llm_provider=CannedLLMProvider("[1, 2, 3]")
        )
        with pytest.raises(InvalidModelResponseError):
            await pipeline.execute(_request())

    @pytest.mark.asyncio
    async def test_valid_empty_response_is_not_an_error(self):
        """AC-4: parseable JSON with zero segments is a valid empty result."""
        payload = json.dumps({"segments": []})
        pipeline = DefaultTranslationPipeline(llm_provider=CannedLLMProvider(payload))
        result = await pipeline.execute(_request())
        seg = result.segments[0]
        assert seg.translated_text == ""
        # An absent translation must not claim MT provenance.
        assert seg.translation_source == "UNTRANSLATED"
