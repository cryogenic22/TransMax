"""Any-to-any language routing: direct pairs vs English pivot."""

from __future__ import annotations

from typing import Optional, Set

from transmax_sdk.telemetry.noop import NoOpTelemetry
from transmax_sdk.telemetry.protocol import TelemetryProtocol
from transmax_sdk.types import RouteStrategy

# Default high-quality direct pairs
DEFAULT_DIRECT_PAIRS: Set[str] = {
    "en-fr", "fr-en", "en-de", "de-en", "en-es", "es-en",
    "en-pt", "pt-en", "en-it", "it-en", "en-nl", "nl-en",
    "en-ja", "ja-en", "en-zh", "zh-en", "en-ko", "ko-en",
    "en-ar", "ar-en", "fr-de", "de-fr", "es-pt", "pt-es",
    "fr-es", "es-fr", "fr-it", "it-fr",
}


class AnyToAnyRouter:
    """Plans translation routing: direct pair or English pivot.

    For high-quality pairs (en-fr, fr-de), translates directly.
    For lower-resource pairs (ja-ar), routes through English as pivot.
    """

    def __init__(
        self,
        direct_pairs: Optional[Set[str]] = None,
        telemetry: Optional[TelemetryProtocol] = None,
    ) -> None:
        self._direct_pairs = direct_pairs or DEFAULT_DIRECT_PAIRS
        self._telemetry = telemetry or NoOpTelemetry()

    def plan_route(self, source_lang: str, target_lang: str) -> RouteStrategy:
        """Determine if a language pair can be translated directly."""
        if source_lang == target_lang:
            return RouteStrategy.DIRECT

        # Normalize to base codes for lookup
        src = source_lang.split("-")[0].lower()
        tgt = target_lang.split("-")[0].lower()

        pair_key = f"{src}-{tgt}"
        if pair_key in self._direct_pairs:
            self._telemetry.log_structured("info", f"Direct route: {pair_key}")
            return RouteStrategy.DIRECT

        # Either source or target is English -> always direct
        if src == "en" or tgt == "en":
            return RouteStrategy.DIRECT

        self._telemetry.log_structured("info", f"Pivot route: {pair_key} via English")
        return RouteStrategy.PIVOT_ENGLISH

    def get_route_steps(self, source_lang: str, target_lang: str) -> list[tuple[str, str]]:
        """Return the translation steps needed for a language pair.

        Returns a list of (source, target) pairs. For direct, it's one step.
        For pivot, it's two steps: source->en, en->target.
        """
        strategy = self.plan_route(source_lang, target_lang)
        if strategy == RouteStrategy.DIRECT:
            return [(source_lang, target_lang)]
        return [(source_lang, "en"), ("en", target_lang)]

    def add_direct_pair(self, source_lang: str, target_lang: str) -> None:
        """Register a new direct pair."""
        self._direct_pairs.add(f"{source_lang}-{target_lang}")
