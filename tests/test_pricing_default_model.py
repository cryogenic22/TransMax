"""TMX-PRICING-1a — the configured default model must be priceable.

settings.default_gpt_model is recorded as the model-of-record in the audit
snapshot (graph.py) and A6-2 usage telemetry. If it is absent from the
canonical pricing registry, any cost_for(settings.default_gpt_model) call
raises UnknownModelError — a regulated cost path that breaks. Register the
configured default at its confirmed public rate so that can't happen.
"""
from __future__ import annotations

from app.core.config import settings
from app.core.model_pricing import cost_for, get_pricing


def test_configured_default_model_is_registered():
    """The model TransMax is configured to run must have pricing (no UnknownModelError)."""
    pricing = get_pricing(settings.default_gpt_model)
    assert pricing.input_per_1m > 0
    assert pricing.output_per_1m > 0
    # cached rate never exceeds standard input (A3: never under-bill via a wrong cached rate)
    assert pricing.cached_input_per_1m <= pricing.input_per_1m


def test_gpt_4_turbo_preview_confirmed_rate():
    """gpt-4-turbo-preview at its confirmed public rate: $10 / $30 per 1M."""
    p = get_pricing("gpt-4-turbo-preview")
    assert p.input_per_1m == 10.00
    assert p.output_per_1m == 30.00


def test_cost_for_default_model_does_not_raise():
    """cost_for on the configured default returns a sane positive cost."""
    cost = cost_for(settings.default_gpt_model, 1_000_000, 1_000_000)
    # 1M in + 1M out at 10 + 30 = $40.00
    assert cost == 40.00
