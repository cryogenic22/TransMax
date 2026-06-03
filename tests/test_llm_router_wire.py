"""TMX-ROUTER-2 — opt-in routing wired into the LLM gateway.

resolve_model/get_llm select a model per task when enable_llm_router is on, and
fall back to default_gpt_model (current behaviour) when off — so production is
unchanged until the operator turns routing on.
"""
from __future__ import annotations

from app.core.config import settings
from app.services.llm import get_llm, reset_llm_cache_for_test, resolve_model


def test_resolve_model_default_when_router_off(monkeypatch):
    monkeypatch.setattr(settings, "enable_llm_router", False)
    # Even a high-complexity task returns the configured default when off.
    assert resolve_model(task="translate", complexity="high") == settings.default_gpt_model
    assert resolve_model() == settings.default_gpt_model


def test_resolve_model_routes_when_on(monkeypatch):
    from app.core.model_registry import Complexity, Task, select_model

    monkeypatch.setattr(settings, "enable_llm_router", True)
    assert resolve_model(task="translate", complexity="high") == select_model(
        Task.TRANSLATE, Complexity.HIGH
    )  # frontier → gpt-4o
    assert resolve_model(task="detect", complexity="low") == "gpt-4o-mini"  # cheap
    # No task ⇒ still the default even when the router is on.
    assert resolve_model() == settings.default_gpt_model


def test_get_llm_builds_routed_model(monkeypatch):
    """get_llm(task) constructs the routed model when routing is on + live."""
    monkeypatch.setattr(settings, "enable_llm_router", True)
    monkeypatch.setattr(settings, "enable_live_llm_inference", True)
    reset_llm_cache_for_test()

    captured = {}

    class _FakeChat:
        def __init__(self, model, **kwargs):
            captured["model"] = model

    import app.services.llm as llm_mod
    monkeypatch.setattr(llm_mod, "ChatOpenAI", _FakeChat)

    get_llm(task="review", complexity="high")  # review → frontier
    assert captured["model"] == "gpt-4o"
    reset_llm_cache_for_test()


def test_get_llm_default_model_when_router_off(monkeypatch):
    monkeypatch.setattr(settings, "enable_llm_router", False)
    monkeypatch.setattr(settings, "enable_live_llm_inference", True)
    reset_llm_cache_for_test()

    captured = {}

    class _FakeChat:
        def __init__(self, model, **kwargs):
            captured["model"] = model

    import app.services.llm as llm_mod
    monkeypatch.setattr(llm_mod, "ChatOpenAI", _FakeChat)

    get_llm(task="review", complexity="high")
    assert captured["model"] == settings.default_gpt_model
    reset_llm_cache_for_test()
