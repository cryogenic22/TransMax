"""Tests for any-to-any language router."""

from transmax_sdk.language.router import AnyToAnyRouter
from transmax_sdk.types import RouteStrategy


class TestAnyToAnyRouter:
    def test_en_fr_is_direct(self):
        router = AnyToAnyRouter()
        assert router.plan_route("en", "fr") == RouteStrategy.DIRECT

    def test_fr_de_is_direct(self):
        router = AnyToAnyRouter()
        assert router.plan_route("fr", "de") == RouteStrategy.DIRECT

    def test_ja_ar_is_pivot(self):
        router = AnyToAnyRouter()
        assert router.plan_route("ja", "ar") == RouteStrategy.PIVOT_ENGLISH

    def test_hi_bn_is_pivot(self):
        router = AnyToAnyRouter()
        assert router.plan_route("hi", "bn") == RouteStrategy.PIVOT_ENGLISH

    def test_same_language_is_direct(self):
        router = AnyToAnyRouter()
        assert router.plan_route("fr", "fr") == RouteStrategy.DIRECT

    def test_any_to_en_is_direct(self):
        router = AnyToAnyRouter()
        assert router.plan_route("vi", "en") == RouteStrategy.DIRECT

    def test_en_to_any_is_direct(self):
        router = AnyToAnyRouter()
        assert router.plan_route("en", "th") == RouteStrategy.DIRECT

    def test_route_steps_direct(self):
        router = AnyToAnyRouter()
        steps = router.get_route_steps("en", "fr")
        assert steps == [("en", "fr")]

    def test_route_steps_pivot(self):
        router = AnyToAnyRouter()
        steps = router.get_route_steps("ja", "ar")
        assert steps == [("ja", "en"), ("en", "ar")]

    def test_add_direct_pair(self):
        router = AnyToAnyRouter()
        assert router.plan_route("hi", "bn") == RouteStrategy.PIVOT_ENGLISH
        router.add_direct_pair("hi", "bn")
        assert router.plan_route("hi", "bn") == RouteStrategy.DIRECT

    def test_bcp47_variants_normalized(self):
        router = AnyToAnyRouter()
        # fr-CA -> fr base code used for lookup
        assert router.plan_route("fr-CA", "de") == RouteStrategy.DIRECT

    def test_custom_direct_pairs(self):
        router = AnyToAnyRouter(direct_pairs={"hi-bn"})
        assert router.plan_route("hi", "bn") == RouteStrategy.DIRECT
        assert router.plan_route("ja", "ar") == RouteStrategy.PIVOT_ENGLISH
