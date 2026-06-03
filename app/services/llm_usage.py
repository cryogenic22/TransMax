"""Shared LLM usage telemetry helpers (TMX-A6-2 / TMX-A6-2b).

A single place to (a) extract response token counts from a LangChain message
and (b) build the canonical qualified-supplier consumption record that gets
written to the audit chain as ``LLM_USAGE_RECORDED`` (A6). Both the
translation engine (initial pass) and the graph refiner (refinement pass)
use these so the per-job consumption is captured consistently across every
LLM call — not just the first one.

Cost is computed at the engine's billing tier (gpt-4o-mini, per Feature 5)
via the canonical pricing table (TMX-PRICING-1); ``model`` records the
supplier model of record (provenance) and ``pricing_model`` records the tier
the cost was computed at, so the two are never conflated (A3).
"""
from __future__ import annotations

# The engine bills LLM drafting + refinement at this tier (Feature 5).
PRICING_TIER = "gpt-4o-mini"


def extract_token_usage(response: object) -> tuple[int, int]:
    """Pull (input_tokens, output_tokens) from a LangChain response.

    Handles both the ``response_metadata['token_usage']`` shape (OpenAI via
    langchain) and the newer ``usage_metadata`` shape. Returns ``(0, 0)`` when
    no usage is present (e.g. a mocked test model) — never raises (A3 metrics
    carve-out: telemetry must not break a translation).
    """
    try:
        token_usage = getattr(response, "response_metadata", {}) or {}
        token_usage = token_usage.get("token_usage", {}) if isinstance(token_usage, dict) else {}
        if token_usage:
            return (
                int(token_usage.get("prompt_tokens", 0)),
                int(token_usage.get("completion_tokens", 0)),
            )
        meta = getattr(response, "usage_metadata", None)
        if meta:
            return (
                int(getattr(meta, "input_tokens", 0)),
                int(getattr(meta, "output_tokens", 0)),
            )
    except Exception:
        pass
    return (0, 0)


def build_usage_record(model: str, input_tokens: int, output_tokens: int) -> dict:
    """Build the canonical qualified-supplier consumption record (A6).

    See module docstring for the ``model`` vs ``pricing_model`` distinction.
    Raises only if the pricing tier is unregistered (A3 — loud, never a wrong
    silent cost); callers wrap the call so the audit emit is skipped on error.
    """
    from app.core.model_pricing import cost_for

    in_tok = int(input_tokens)
    out_tok = int(output_tokens)
    estimated_cost = cost_for(PRICING_TIER, in_tok, out_tok)
    return {
        "model": model,
        "pricing_model": PRICING_TIER,
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "total_tokens": in_tok + out_tok,
        "estimated_cost_usd": round(estimated_cost, 6),
        "currency": "USD",
        "pricing_source": "app.core.model_pricing",
    }


def emit_usage_event(
    job_id: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    *,
    actor_node: str,
    extra: dict | None = None,
) -> None:
    """Write one ``LLM_USAGE_RECORDED`` v2 audit event for one LLM pass (A6/A1).

    Used by the graph refiner (TMX-A6-2b). Per-job consumption is the sum of
    all such events. Caller wraps this so a writer failure never blocks the
    pipeline (A3 metrics carve-out)."""
    from app.agents._audit_v2_emit import emit_v2_audit_event

    payload = build_usage_record(model, input_tokens, output_tokens)
    if extra:
        payload.update(extra)
    payload["_actor_node"] = actor_node
    emit_v2_audit_event(
        job_id=job_id,
        event_type="LLM_USAGE_RECORDED",
        actor_id=None,
        actor_kind="agent",
        payload=payload,
    )
