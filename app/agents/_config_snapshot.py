"""JobConfigSnapshot builder (extracted from graph.py — TMX-3202 / A6 / A8).

Freezes the request + qualified-supplier telemetry into the audit chain at
job start. Kept in its own module so the graph file stays focused on graph
wiring (and under the 800-line mega-file ratchet).
"""
from __future__ import annotations

from app.agents.prompts import PromptRegistry
from app.core.config import settings

# Agents whose prompts are pinned into the JobConfigSnapshot. The pipeline
# drives translation through these three LLM-backed agents (translator drafts,
# fixer repairs, reviewer scores), so a regulator asking "which exact prompt
# produced this output?" (A8) must be able to resolve every one of them.
_SNAPSHOT_PROMPT_AGENTS = ("translator", "fixer", "reviewer")


def build_config_snapshot(state: dict) -> dict:
    """Freeze the request + qualified-supplier telemetry for the audit chain.

    Per A6 (LLM = qualified supplier) the JobConfigSnapshot records the REAL
    configured model and the EXACT prompt versions used, not placeholders. Per
    A8 each agent's prompt is captured by its on-disk semver ``version`` plus
    its SHA-256 ``content_hash``, so the snapshot is reproducible. The model is
    ``settings.default_gpt_model`` (TMX-3202, replacing the old hard-coded
    "gpt-4o" placeholder). If the registry cannot resolve an agent — a real
    misconfiguration — we do NOT substitute (A3): ``PromptRegistry.load``
    raises and the job fails loud rather than recording a lying snapshot.
    """
    prompts: dict[str, dict[str, str]] = {}
    for agent in _SNAPSHOT_PROMPT_AGENTS:
        loaded = PromptRegistry.load(agent)
        prompts[agent] = {
            "version": loaded.version,
            "content_hash": loaded.content_hash,
        }

    return {
        "request": {
            k: v for k, v in state.items()
            if k in ["doc_id", "target_language", "job_id"]
        },
        "system": {
            "model": settings.default_gpt_model,
            "prompts": prompts,
        },
    }
