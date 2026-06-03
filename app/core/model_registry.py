"""LLM model capability registry + routing policy (TMX-ROUTER-1).

The pricing registry (``app/core/model_pricing.py``) answers "what does a model
cost?". This module answers "which model should run THIS task?" — the brain of
the LLM router. It holds per-model *capability* metadata (tier, relative
quality, provider, context window) keyed to the same model ids as the pricing
registry, plus a pure, config-driven ``select_model`` policy.

Design rules:
- **Config, not branching.** The task→tier mapping is a data table (`_POLICY`),
  not an `if` ladder in business logic — open for extension (ROUTER-3 will make
  it per-tenant + DB-backed).
- **Every registered model must be priceable.** A model the router can pick but
  the pricing table can't cost would record a wrong/absent cost (A3) — enforced
  by a test.
- **Pure + deterministic.** No I/O, no LLM call. ROUTER-2 wires the chosen id
  into ``get_llm`` and records it in the audit snapshot (A6/A8).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ModelTier(str, Enum):
    """Cost/quality band. Higher tier = higher quality + cost."""

    CHEAP = "cheap"
    BALANCED = "balanced"
    FRONTIER = "frontier"


_TIER_ORDER = (ModelTier.CHEAP, ModelTier.BALANCED, ModelTier.FRONTIER)


class Task(str, Enum):
    """LLM-backed pipeline tasks that the router selects models for."""

    TRANSLATE = "translate"
    REFINE = "refine"
    REVIEW = "review"
    DETECT = "detect"


class Complexity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class ModelSpec:
    """Capability record for one model. ``model_id`` MUST be a key in the
    pricing registry so the router's choice is always costable."""

    model_id: str
    provider: str
    tier: ModelTier
    quality: int  # 0-100 relative translation/judgement quality
    max_context_tokens: int


# The canonical capability registry. Add models here AND in model_pricing.py.
_REGISTRY: dict[str, ModelSpec] = {
    "gpt-4o-mini": ModelSpec(
        model_id="gpt-4o-mini", provider="openai",
        tier=ModelTier.CHEAP, quality=72, max_context_tokens=128_000,
    ),
    "gpt-4-turbo-preview": ModelSpec(
        model_id="gpt-4-turbo-preview", provider="openai",
        tier=ModelTier.BALANCED, quality=85, max_context_tokens=128_000,
    ),
    "gpt-4o": ModelSpec(
        model_id="gpt-4o", provider="openai",
        tier=ModelTier.FRONTIER, quality=90, max_context_tokens=128_000,
    ),
}


# Task + complexity → desired tier. The default (unlisted key) is BALANCED.
# Rationale: high-risk/complex translation and quality REVIEW (the judge) want
# the best model; DETECT (e.g. language/injection signals) and trivial work go
# cheap; refinement is a balanced repair pass.
_POLICY: dict[tuple[Task, Complexity], ModelTier] = {
    (Task.TRANSLATE, Complexity.HIGH): ModelTier.FRONTIER,
    (Task.TRANSLATE, Complexity.MEDIUM): ModelTier.BALANCED,
    (Task.TRANSLATE, Complexity.LOW): ModelTier.CHEAP,
    (Task.REFINE, Complexity.HIGH): ModelTier.BALANCED,
    (Task.REFINE, Complexity.MEDIUM): ModelTier.BALANCED,
    (Task.REFINE, Complexity.LOW): ModelTier.CHEAP,
    (Task.REVIEW, Complexity.HIGH): ModelTier.FRONTIER,
    (Task.REVIEW, Complexity.MEDIUM): ModelTier.FRONTIER,
    (Task.REVIEW, Complexity.LOW): ModelTier.BALANCED,
    (Task.DETECT, Complexity.HIGH): ModelTier.CHEAP,
    (Task.DETECT, Complexity.MEDIUM): ModelTier.CHEAP,
    (Task.DETECT, Complexity.LOW): ModelTier.CHEAP,
}


def _coerce(value, enum_cls):
    """Accept either an enum member or its string value."""
    return value if isinstance(value, enum_cls) else enum_cls(value)


def _downgrade(tier: ModelTier) -> ModelTier:
    """One tier cheaper (floored at CHEAP)."""
    i = _TIER_ORDER.index(tier)
    return _TIER_ORDER[max(0, i - 1)]


def get_spec(model_id: str) -> ModelSpec:
    """Return the capability record for ``model_id`` (raises KeyError if absent)."""
    return _REGISTRY[model_id]


def registered_models() -> list[ModelSpec]:
    """All registered model specs (for the config UI / introspection)."""
    return list(_REGISTRY.values())


def model_for_tier(tier: ModelTier) -> str | None:
    """The highest-quality registered model of ``tier``, or None if none."""
    candidates = [s for s in _REGISTRY.values() if s.tier == tier]
    if not candidates:
        return None
    return max(candidates, key=lambda s: s.quality).model_id


def select_model(
    task: Task | str,
    complexity: Complexity | str = Complexity.MEDIUM,
    *,
    budget_posture: str = "normal",
    default_model: str = "gpt-4o-mini",
) -> str:
    """Pick the model id for a task.

    Args:
        task: the pipeline task (Task or its string).
        complexity: low/medium/high signal the caller derives (length, risk, domain).
        budget_posture: ``"normal"`` or ``"constrained"`` — when constrained
            (e.g. a job nearing its TMX-BUDGET-1 ceiling) the tier is downgraded
            one step to save cost.
        default_model: fallback if the resolved tier has no registered model.

    Returns:
        A model id guaranteed to be in the pricing registry (costable).
    """
    task = _coerce(task, Task)
    complexity = _coerce(complexity, Complexity)

    tier = _POLICY.get((task, complexity), ModelTier.BALANCED)
    if budget_posture == "constrained":
        tier = _downgrade(tier)

    return model_for_tier(tier) or default_model
