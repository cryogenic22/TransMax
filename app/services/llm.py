"""LLM gateway (TMX-ROUTER-2).

`get_llm(task, complexity)` is the single chokepoint for obtaining an LLM
instance. When the opt-in router is enabled (`settings.enable_llm_router`) it
selects a model per task/complexity via the capability registry
(`app/core/model_registry.select_model`); otherwise it returns the configured
`default_gpt_model` — the pre-router behaviour — so production is unchanged
until the operator turns routing on. Instances are cached per resolved model.
"""
from langchain_openai import ChatOpenAI

from app.core.config import settings

# Cache of resolved-model-id -> LLM instance (one fake model under "__fake__").
_llm_cache: dict = {}


def resolve_model(task=None, complexity="medium") -> str:
    """Resolve the model id for a task.

    Routes via the capability registry only when a task is given AND
    `enable_llm_router` is set; otherwise returns `default_gpt_model`. The
    chosen id is what the usage telemetry records (A6 provenance)."""
    if task and getattr(settings, "enable_llm_router", False):
        from app.core.model_registry import select_model
        return select_model(task, complexity, default_model=settings.default_gpt_model)
    return settings.default_gpt_model


def get_llm(task=None, complexity="medium"):
    """Return an LLM instance for ``task`` (routed when enable_llm_router is on).

    Cached per resolved model. In non-live mode returns a single deterministic
    fake model (test path) — model identity is irrelevant there.
    """
    if not settings.enable_live_llm_inference:
        if "__fake__" not in _llm_cache:
            from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
            from langchain_core.messages import AIMessage
            _llm_cache["__fake__"] = GenericFakeChatModel(messages=iter([
                AIMessage(content='{"segments": [{"segment_id": "1", "target_text": "Translated (Mock)"}]}')
            ]))
        return _llm_cache["__fake__"]

    model = resolve_model(task, complexity)
    if model not in _llm_cache:
        _llm_cache[model] = ChatOpenAI(
            model=model,
            temperature=0,
            api_key=settings.openai_api_key,
        )
    return _llm_cache[model]


def reset_llm_cache_for_test() -> None:
    """Test-only: clear the per-model LLM cache (so a settings change is picked up)."""
    _llm_cache.clear()
