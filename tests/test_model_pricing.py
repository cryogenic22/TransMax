"""TMX-PRICING-1 — tests for the canonical model-pricing registry.

These tests pin the single source of truth for per-model token pricing
(`app/core/model_pricing.py`). They guard three properties:

1. Exact cost arithmetic for the currently-priced models (regression pins so
   a refactor of the call-sites cannot silently change a recorded cost).
2. Unknown models FAIL LOUD (addendum A3 — no silent fallback that would
   record a cost for the wrong model / a zero cost).
3. The cached-input tier applies its discounted rate.

Prices are USD per 1M tokens (2026):
    gpt-4o       input 2.50  / output 10.00 / cached-input 1.25
    gpt-4o-mini  input 0.15  / output  0.60 / cached-input 0.075
"""
import math

import pytest

from app.core.model_pricing import (
    ModelPricing,
    UnknownModelError,
    cost_for,
    get_pricing,
)


def _approx(value: float, expected: float) -> bool:
    return math.isclose(value, expected, rel_tol=0.0, abs_tol=1e-12)


class TestCostFor:
    def test_gpt_4o_mini_one_million_each_way(self) -> None:
        # 1M input @ 0.15/1M + 1M output @ 0.60/1M == 0.15 + 0.60 == 0.75
        cost = cost_for("gpt-4o-mini", 1_000_000, 1_000_000)
        assert _approx(cost, 0.75)

    def test_gpt_4o_pricing_pins(self) -> None:
        # 1M input @ 2.50/1M + 1M output @ 10.00/1M == 12.50
        cost = cost_for("gpt-4o", 1_000_000, 1_000_000)
        assert _approx(cost, 12.50)

    def test_unknown_model_raises_not_zero(self) -> None:
        # A3: must fail loud, never silently return 0 or default to another model.
        with pytest.raises(UnknownModelError):
            cost_for("gpt-9-imaginary", 1000, 1000)

    def test_cached_input_tier_applies_discount(self) -> None:
        # gpt-4o cached-input is 1.25/1M (half of the 2.50/1M standard input).
        # 1M cached-input tokens @ 1.25/1M == 1.25; zero standard in/out.
        cost = cost_for(
            "gpt-4o",
            input_tokens=0,
            output_tokens=0,
            cached_input_tokens=1_000_000,
        )
        assert _approx(cost, 1.25)

    def test_cached_plus_standard_input_sum(self) -> None:
        # 1M standard input @ 2.50 + 1M cached input @ 1.25 + 0 output == 3.75
        cost = cost_for(
            "gpt-4o",
            input_tokens=1_000_000,
            output_tokens=0,
            cached_input_tokens=1_000_000,
        )
        assert _approx(cost, 3.75)

    def test_documents_estimate_equivalence(self) -> None:
        # Pins behavioural identity with the old documents.py magic numbers:
        #   (in * 0.00000015) + (out * 0.0000006)
        est_input_tokens = 12_345
        est_output_tokens = 6_789
        legacy = (est_input_tokens * 0.00000015) + (est_output_tokens * 0.0000006)
        new = cost_for("gpt-4o-mini", est_input_tokens, est_output_tokens)
        assert _approx(new, legacy)


class TestRegistry:
    def test_get_pricing_returns_typed_record(self) -> None:
        pricing = get_pricing("gpt-4o-mini")
        assert isinstance(pricing, ModelPricing)
        assert pricing.input_per_1m == 0.15
        assert pricing.output_per_1m == 0.60
        assert pricing.cached_input_per_1m == 0.075

    def test_get_pricing_unknown_raises(self) -> None:
        with pytest.raises(UnknownModelError):
            get_pricing("does-not-exist")

    def test_negative_tokens_rejected(self) -> None:
        with pytest.raises(ValueError):
            cost_for("gpt-4o-mini", -1, 0)
