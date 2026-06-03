"""Canonical model-pricing registry (TMX-PRICING-1).

Single source of truth for per-model LLM token pricing across the TransMax
application. Before this module, the gpt-4o-mini rates were hardcoded as bare
magic numbers in at least two call-sites (`app/api/documents.py` and
`app/services/observability.py`), each with its own copy and — in
observability — a silent fall-back to gpt-4o that could record a cost for a
DIFFERENT model than the one actually used. That violates single-source-of-
truth (Tier 1 / TMX-3017 spirit) and addendum A3 (no silent fallbacks in
regulated paths): a recorded translation cost is a regulator-facing number,
so it must be for the model that actually ran, or it must fail loud.

Prices are USD per 1,000,000 tokens (2026 published rates):

    model        input   output  cached-input
    gpt-4o       2.50    10.00   1.25
    gpt-4o-mini  0.15     0.60   0.075

`cost_for(...)` is the only function business logic should call. `get_pricing`
exposes the typed record for callers that need the rates themselves.
Unknown models raise `UnknownModelError` — never a silent zero or default.
"""
from __future__ import annotations

from dataclasses import dataclass

# Divisor: prices are quoted per 1,000,000 tokens.
_TOKENS_PER_PRICE_UNIT = 1_000_000


@dataclass(frozen=True)
class ModelPricing:
    """Immutable pricing record for one model, in USD per 1M tokens.

    `cached_input_per_1m` is the discounted rate charged for prompt tokens
    served from the provider's prompt cache (e.g. OpenAI cached input). It is
    always <= `input_per_1m`.
    """

    input_per_1m: float
    output_per_1m: float
    cached_input_per_1m: float


# The canonical registry. Keys are the exact model identifiers used in
# `settings.default_*_model` and in audit snapshots. Add new models here and
# NOWHERE else.
#
# TODO(TMX-PRICING-1a): register gpt-4.1 and the Claude tier (Opus/Sonnet/
# Haiku) once their published per-1M rates are confirmed. Until then, callers
# requesting those models get a loud UnknownModelError rather than a wrong
# silent cost — which is the A3-correct behaviour.
_PRICING: dict[str, ModelPricing] = {
    "gpt-4o": ModelPricing(
        input_per_1m=2.50,
        output_per_1m=10.00,
        cached_input_per_1m=1.25,
    ),
    "gpt-4o-mini": ModelPricing(
        input_per_1m=0.15,
        output_per_1m=0.60,
        cached_input_per_1m=0.075,
    ),
}


class UnknownModelError(KeyError):
    """Raised when pricing is requested for a model not in the registry.

    Subclasses `KeyError` for backwards-compatible `except KeyError` handling,
    but carries a human-readable message naming the offending model and the
    set of known models. A3: callers must NOT swallow this and substitute a
    default model's price — a cost recorded against the wrong model is a
    regulatory defect, not a rounding error.
    """

    def __init__(self, model: str) -> None:
        known = ", ".join(sorted(_PRICING)) or "<none registered>"
        super().__init__(
            f"No pricing registered for model {model!r}. "
            f"Known models: {known}. Register it in "
            f"app/core/model_pricing.py — do not default to another model "
            f"(addendum A3: no silent fallbacks in regulated paths)."
        )
        self.model = model


def get_pricing(model: str) -> ModelPricing:
    """Return the canonical pricing record for ``model``.

    Raises:
        UnknownModelError: if ``model`` is not in the registry.
    """
    try:
        return _PRICING[model]
    except KeyError as exc:
        raise UnknownModelError(model) from exc


def cost_for(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cached_input_tokens: int = 0,
) -> float:
    """Compute the USD cost of an LLM call from its token counts.

    Args:
        model: the model identifier (must be in the registry).
        input_tokens: standard (uncached) prompt tokens.
        output_tokens: completion tokens.
        cached_input_tokens: prompt tokens served from the provider cache,
            charged at the discounted `cached_input_per_1m` rate. These are
            counted IN ADDITION to ``input_tokens`` — the caller passes the
            split, not the total.

    Returns:
        Cost in USD as a float (not rounded — callers round for display).

    Raises:
        UnknownModelError: if ``model`` is not in the registry (A3).
        ValueError: if any token count is negative.
    """
    if input_tokens < 0 or output_tokens < 0 or cached_input_tokens < 0:
        raise ValueError(
            "token counts must be non-negative "
            f"(input={input_tokens}, output={output_tokens}, "
            f"cached_input={cached_input_tokens})"
        )

    pricing = get_pricing(model)
    return (
        input_tokens * pricing.input_per_1m
        + output_tokens * pricing.output_per_1m
        + cached_input_tokens * pricing.cached_input_per_1m
    ) / _TOKENS_PER_PRICE_UNIT
