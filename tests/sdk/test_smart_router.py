"""Tests for SmartRouter: provider-aware language routing."""

from transmax_sdk.language.capabilities import (
    CapabilityMatrix,
    DEFAULT_CAPABILITY_MATRIX,
    LanguageCapability,
)
from transmax_sdk.language.smart_router import SmartRouter
from transmax_sdk.types import RouteStrategy


class TestSmartRouterBackwardsCompat:
    """SmartRouter must behave like AnyToAnyRouter for basic operations."""

    def test_en_fr_is_direct(self):
        router = SmartRouter()
        assert router.plan_route("en", "fr") == RouteStrategy.DIRECT

    def test_ja_ar_is_pivot(self):
        router = SmartRouter()
        assert router.plan_route("ja", "ar") == RouteStrategy.PIVOT_ENGLISH

    def test_route_steps_direct(self):
        router = SmartRouter()
        steps = router.get_route_steps("en", "fr")
        assert steps == [("en", "fr")]

    def test_route_steps_pivot(self):
        router = SmartRouter()
        steps = router.get_route_steps("ja", "ar")
        assert steps == [("ja", "en"), ("en", "ar")]

    def test_add_direct_pair(self):
        router = SmartRouter()
        router.add_direct_pair("ja", "ar")
        assert router.plan_route("ja", "ar") == RouteStrategy.DIRECT


class TestSmartRouteProviderSelection:
    """SmartRouter selects best provider per step."""

    def test_smart_route_direct_picks_best(self):
        router = SmartRouter(
            available_providers={"openai", "anthropic", "gemini"},
        )
        plan = router.plan_smart_route("en", "fr")
        assert plan.strategy == RouteStrategy.DIRECT
        assert len(plan.steps) == 1
        # Gemini wins: 0.7*0.92 + 0.3*1.0 = 0.944 (cheap tier 1)
        # vs OpenAI: 0.7*0.95 + 0.3*0.5 = 0.815 (tier 2)
        assert plan.steps[0].provider_name == "gemini"

    def test_smart_route_indic_prefers_gemini(self):
        router = SmartRouter(
            available_providers={"openai", "anthropic", "gemini"},
        )
        plan = router.plan_smart_route("en", "hi")
        assert len(plan.steps) == 1
        # Gemini excels at Indic languages (0.93 vs 0.85 openai, 0.84 anthropic)
        # With cost_weight=0.3: gemini score = 0.7*0.93 + 0.3*1.0 = 0.951
        # openai score = 0.7*0.85 + 0.3*0.5 = 0.745
        assert plan.steps[0].provider_name == "gemini"

    def test_smart_route_with_single_provider(self):
        router = SmartRouter(
            available_providers={"anthropic"},
        )
        plan = router.plan_smart_route("en", "fr")
        assert plan.steps[0].provider_name == "anthropic"

    def test_smart_route_pivot_two_steps(self):
        router = SmartRouter(
            available_providers={"openai", "gemini"},
        )
        # Use a pair that is not in direct_pairs and neither side is English
        plan = router.plan_smart_route("pl", "th")
        assert plan.strategy == RouteStrategy.PIVOT_ENGLISH
        assert len(plan.steps) == 2
        # Each step gets its own provider assignment
        assert plan.steps[0].source_lang == "pl"
        assert plan.steps[0].target_lang == "en"
        assert plan.steps[1].source_lang == "en"
        assert plan.steps[1].target_lang == "th"

    def test_smart_route_fallback_for_unknown_pair(self):
        router = SmartRouter(
            available_providers={"openai"},
        )
        plan = router.plan_smart_route("xx", "yy")
        # Unknown pair pivots through English (2 steps), both fallback
        assert plan.strategy == RouteStrategy.PIVOT_ENGLISH
        assert len(plan.steps) == 2
        assert plan.steps[0].provider_name == "openai"
        assert plan.steps[0].confidence == 0.5  # default fallback
        assert plan.steps[1].provider_name == "openai"

    def test_custom_weights_favor_cost(self):
        """With high cost_weight, cheaper provider (gemini tier 1) wins."""
        router = SmartRouter(
            available_providers={"openai", "gemini"},
            quality_weight=0.3,
            cost_weight=0.7,
        )
        plan = router.plan_smart_route("en", "fr")
        # Gemini: 0.3*0.92 + 0.7*1.0 = 0.976
        # OpenAI: 0.3*0.95 + 0.7*0.5 = 0.635
        assert plan.steps[0].provider_name == "gemini"
