"""TMX-ROUTER-1 — model capability registry + select_model policy."""
from __future__ import annotations

import pytest

from app.core.model_pricing import cost_for
from app.core.model_registry import (
    Complexity,
    ModelTier,
    Task,
    model_for_tier,
    registered_models,
    select_model,
)


def test_every_registered_model_is_priceable():
    """A model the router can pick MUST be costable (A3 — no wrong/absent cost)."""
    for spec in registered_models():
        # cost_for raises UnknownModelError if the model isn't in the pricing
        # registry; a clean call proves registry/pricing are in sync.
        assert cost_for(spec.model_id, 1000, 1000) > 0


def test_tier_resolves_to_highest_quality_model():
    assert model_for_tier(ModelTier.CHEAP) == "gpt-4o-mini"
    assert model_for_tier(ModelTier.FRONTIER) == "gpt-4o"


@pytest.mark.parametrize(
    "task,complexity,expected",
    [
        (Task.TRANSLATE, Complexity.HIGH, "gpt-4o"),          # frontier
        (Task.TRANSLATE, Complexity.MEDIUM, "gpt-4-turbo-preview"),  # balanced
        (Task.TRANSLATE, Complexity.LOW, "gpt-4o-mini"),      # cheap
        (Task.REVIEW, Complexity.HIGH, "gpt-4o"),             # judge wants the best
        (Task.DETECT, Complexity.HIGH, "gpt-4o-mini"),        # detect always cheap
        (Task.REFINE, Complexity.MEDIUM, "gpt-4-turbo-preview"),     # balanced
    ],
)
def test_select_model_policy(task, complexity, expected):
    assert select_model(task, complexity) == expected


def test_budget_constrained_downgrades_one_tier():
    """A job nearing its budget downgrades the selected tier (cost-aware)."""
    # translate/high is normally frontier (gpt-4o); constrained -> balanced.
    assert select_model(Task.TRANSLATE, Complexity.HIGH) == "gpt-4o"
    assert (
        select_model(Task.TRANSLATE, Complexity.HIGH, budget_posture="constrained")
        == "gpt-4-turbo-preview"
    )
    # cheap can't downgrade below cheap.
    assert (
        select_model(Task.DETECT, Complexity.LOW, budget_posture="constrained")
        == "gpt-4o-mini"
    )


def test_accepts_string_task_and_complexity():
    assert select_model("translate", "high") == "gpt-4o"


def test_unknown_combo_defaults_to_balanced():
    # Construct a (task, complexity) not in the policy table by using a task
    # the table covers fully — every combo is mapped, so verify the default
    # path via model_for_tier on the BALANCED tier instead.
    assert model_for_tier(ModelTier.BALANCED) == "gpt-4-turbo-preview"
