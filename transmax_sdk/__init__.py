"""TransMax SDK - Pharmaceutical Translation Engine.

Usage:
    from transmax_sdk import TransMaxSDK

    sdk = TransMaxSDK(config={"openai_api_key": "sk-..."})
    result = await sdk.translate("Take 10mg daily", target_lang="ja")
    print(result.translated_text, result.confidence, result.defects)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from transmax_sdk.config import SDKConfig
from transmax_sdk.container import SDKContainer
from transmax_sdk.telemetry.protocol import TelemetryProtocol
from transmax_sdk.types import (
    CostRecord,
    LanguageDetectionResult,
    QualityDefect,
    RoutePlan,
    RouteStep,
    RouteStrategy,
    SegmentResult,
    Severity,
    TranslationRequest,
    TranslationResult,
    TranslationSegment,
    TranslationStatus,
)

__version__ = "0.1.0"

__all__ = [
    "TransMaxSDK",
    "SDKConfig",
    "SDKContainer",
    "TelemetryProtocol",
    # Types
    "TranslationSegment",
    "TranslationRequest",
    "TranslationResult",
    "SegmentResult",
    "QualityDefect",
    "LanguageDetectionResult",
    "CostRecord",
    "Severity",
    "TranslationStatus",
    "RouteStrategy",
    "RouteStep",
    "RoutePlan",
]


class TransMaxSDK:
    """Top-level facade for the TransMax SDK.

    Provides a simple interface for translation, quality checking,
    language detection, and audit operations. All methods delegate
    to pluggable components wired through the DI container.
    """

    def __init__(
        self,
        config: Optional[Union[SDKConfig, Dict[str, Any]]] = None,
        telemetry: Optional[TelemetryProtocol] = None,
    ) -> None:
        if isinstance(config, dict):
            config = SDKConfig(**config)
        self._container = SDKContainer(config=config, telemetry=telemetry)
        self._container._register_defaults()

    @property
    def config(self) -> SDKConfig:
        return self._container.config

    @property
    def container(self) -> SDKContainer:
        return self._container

    @property
    def telemetry(self) -> TelemetryProtocol:
        return self._container.telemetry

    async def translate(
        self,
        text: Union[str, List[str]],
        target_lang: str,
        source_lang: str = "auto",
        **kwargs: Any,
    ) -> TranslationResult:
        """Translate text to target language.

        Args:
            text: Single string or list of strings to translate.
            target_lang: BCP-47 target language code.
            source_lang: BCP-47 source language code, or "auto" for detection.
            **kwargs: Additional options passed to the pipeline.

        Returns:
            TranslationResult with translated segments, confidence, defects.
        """
        # Build segments
        if isinstance(text, str):
            segments = [TranslationSegment(segment_id="seg_0", source_text=text)]
        else:
            segments = [
                TranslationSegment(segment_id=f"seg_{i}", source_text=t)
                for i, t in enumerate(text)
            ]

        # Auto-detect source language
        if source_lang == "auto":
            detector = self._container.resolve("language_detector")
            detection = detector.detect(segments[0].source_text)
            source_lang = detection.lang_code

        # Get pipeline and execute
        pipeline = self._container.resolve("pipeline")
        request = TranslationRequest(
            segments=segments,
            source_lang=source_lang,
            target_lang=target_lang,
            **kwargs,
        )
        return await pipeline.execute(request)

    def detect_language(self, text: str) -> LanguageDetectionResult:
        """Detect the language of input text."""
        detector = self._container.resolve("language_detector")
        return detector.detect(text)

    async def quality_check(
        self,
        source_text: str,
        translated_text: str,
        source_lang: str,
        target_lang: str,
    ) -> List[QualityDefect]:
        """Run quality gates on a source/translation pair."""
        gate = self._container.resolve("quality_gate")
        return gate.check_segment(
            source_text=source_text,
            target_text=translated_text,
            source_lang=source_lang,
            target_lang=target_lang,
        )

    def estimate_cost(self, text: str, model: Optional[str] = None) -> float:
        """Estimate translation cost for text."""
        tracker = self._container.resolve("cost_tracker")
        return tracker.estimate_cost(text, model=model or self.config.default_model)

    def plan_route(self, source_lang: str, target_lang: str) -> RouteStrategy:
        """Determine routing strategy for a language pair."""
        router = self._container.resolve("router")
        return router.plan_route(source_lang, target_lang)
