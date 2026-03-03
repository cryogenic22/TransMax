"""Smart LLM router: picks the best provider per translation step."""

from __future__ import annotations

from typing import Dict, Optional, Set

from transmax_sdk.language.capabilities import DEFAULT_CAPABILITY_MATRIX, CapabilityMatrix
from transmax_sdk.language.router import AnyToAnyRouter
from transmax_sdk.telemetry.noop import NoOpTelemetry
from transmax_sdk.telemetry.protocol import TelemetryProtocol
from transmax_sdk.types import RoutePlan, RouteStep, RouteStrategy


# Cost tier normalization: tier 1 = 0.0, tier 2 = 0.5, tier 3 = 1.0
_COST_NORM = {1: 0.0, 2: 0.5, 3: 1.0}


class SmartRouter:
    """Routes translation steps to the best available LLM provider.

    Backwards-compatible with AnyToAnyRouter: same plan_route() and
    get_route_steps() API. Adds plan_smart_route() which returns a
    RoutePlan with per-step provider assignments.
    """

    def __init__(
        self,
        direct_pairs: Optional[Set[str]] = None,
        available_providers: Optional[Set[str]] = None,
        capability_matrix: Optional[CapabilityMatrix] = None,
        quality_weight: float = 0.7,
        cost_weight: float = 0.3,
        telemetry: Optional[TelemetryProtocol] = None,
    ) -> None:
        self._base_router = AnyToAnyRouter(
            direct_pairs=direct_pairs, telemetry=telemetry
        )
        self._available_providers = available_providers or set()
        self._matrix = capability_matrix or DEFAULT_CAPABILITY_MATRIX
        self._quality_weight = quality_weight
        self._cost_weight = cost_weight
        self._telemetry = telemetry or NoOpTelemetry()

    # --- Backwards-compatible API (same as AnyToAnyRouter) ---

    def plan_route(self, source_lang: str, target_lang: str) -> RouteStrategy:
        """Determine if a language pair can be translated directly."""
        return self._base_router.plan_route(source_lang, target_lang)

    def get_route_steps(
        self, source_lang: str, target_lang: str
    ) -> list[tuple[str, str]]:
        """Return translation steps as (source, target) pairs."""
        return self._base_router.get_route_steps(source_lang, target_lang)

    def add_direct_pair(self, source_lang: str, target_lang: str) -> None:
        """Register a new direct pair."""
        self._base_router.add_direct_pair(source_lang, target_lang)

    # --- Smart routing API ---

    def plan_smart_route(
        self, source_lang: str, target_lang: str
    ) -> RoutePlan:
        """Build a RoutePlan with per-step provider assignments.

        For each translation step:
        1. Query the capability matrix for all available providers
        2. Score each: quality_weight * confidence + cost_weight * (1 - norm_cost)
        3. Pick the highest-scoring provider
        """
        strategy = self.plan_route(source_lang, target_lang)
        raw_steps = self.get_route_steps(source_lang, target_lang)

        route_steps = []
        for src, tgt in raw_steps:
            step = self._pick_best_provider(src, tgt)
            route_steps.append(step)

        self._telemetry.log_structured(
            "info",
            f"Smart route {source_lang}->{target_lang}: "
            f"{len(route_steps)} step(s), "
            f"providers={[s.provider_name for s in route_steps]}",
        )

        return RoutePlan(strategy=strategy, steps=route_steps)

    def _pick_best_provider(self, src: str, tgt: str) -> RouteStep:
        """Score and pick the best provider for a single step."""
        candidates = self._matrix.providers_for_pair(src, tgt)
        if self._available_providers:
            candidates = [
                c for c in candidates if c.provider in self._available_providers
            ]

        if not candidates:
            # Fallback: use the first available provider with default confidence
            fallback_provider = (
                next(iter(self._available_providers))
                if self._available_providers
                else "unknown"
            )
            return RouteStep(
                source_lang=src,
                target_lang=tgt,
                provider_name=fallback_provider,
                model="default",
                confidence=0.5,
                estimated_cost=0.0,
            )

        best = None
        best_score = -1.0

        for cap in candidates:
            norm_cost = _COST_NORM.get(cap.cost_tier, 0.5)
            score = (
                self._quality_weight * cap.confidence
                + self._cost_weight * (1.0 - norm_cost)
            )
            if score > best_score:
                best_score = score
                best = cap

        assert best is not None
        return RouteStep(
            source_lang=src,
            target_lang=tgt,
            provider_name=best.provider,
            model=best.default_model,
            confidence=best.confidence,
            estimated_cost=0.0,
        )
