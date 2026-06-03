"""TMX-ROUTER-5 — cost-aware routing: budget_posture downgrades the tier."""
from __future__ import annotations

from app.core.config import settings
from app.core.model_registry import Complexity, Task, select_model
from app.services.budget_guard import JobBudget, budget_posture
from app.services.llm import resolve_model


def test_posture_normal_when_budget_disabled():
    assert budget_posture(10**9, 10**6, JobBudget()) == "normal"


def test_posture_token_threshold():
    b = JobBudget(max_tokens=1000)
    assert budget_posture(799, 0.0, b) == "normal"     # < 80%
    assert budget_posture(800, 0.0, b) == "constrained"  # >= 80%
    assert budget_posture(950, 0.0, b) == "constrained"


def test_posture_cost_threshold():
    b = JobBudget(max_cost_usd=1.0)
    assert budget_posture(0, 0.79, b) == "normal"
    assert budget_posture(0, 0.80, b) == "constrained"


def test_from_settings_reads_limits(monkeypatch):
    monkeypatch.setattr(settings, "max_tokens_per_job", 500)
    monkeypatch.setattr(settings, "max_cost_usd_per_job", None)
    b = JobBudget.from_settings()
    assert b.max_tokens == 500
    assert b.max_cost_usd is None


def test_constrained_posture_downgrades_routed_model(monkeypatch):
    """With routing on, a constrained posture drops translate/high from
    frontier (gpt-4o) to the balanced tier."""
    monkeypatch.setattr(settings, "enable_llm_router", True)
    assert resolve_model("translate", "high") == select_model(Task.TRANSLATE, Complexity.HIGH)  # gpt-4o
    assert resolve_model("translate", "high", budget_posture="constrained") == "gpt-4-turbo-preview"


def test_posture_ignored_when_router_off(monkeypatch):
    monkeypatch.setattr(settings, "enable_llm_router", False)
    # Even constrained, routing off ⇒ default model.
    assert resolve_model("translate", "high", budget_posture="constrained") == settings.default_gpt_model
