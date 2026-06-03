"""LangGraph node adapter for the translation engine.

Separated from ``translation_engine.py`` (which holds the engine *class*) so
the engine core and its LangGraph *surface adapter* live apart — "engine
first, surface second" (CLAUDE.md). This node is a thin wrapper: it invokes
``TranslationEngine.translate_document`` and, after it returns, records the
qualified-supplier consumption (TMX-A6-2) and any per-job budget breach
(TMX-BUDGET-1) into the immutable v2 audit chain. All audit emits are
A3-wrapped — telemetry/audit signals never block a translation.
"""
from __future__ import annotations

import logging
from typing import Optional

from app.agents._audit_v2_emit import emit_v2_audit_event
from app.agents.nodes.translation_engine import TranslationEngine
from app.core.defect_taxonomy import DefectCategory
from app.services.tracing import traced

logger = logging.getLogger(__name__)

_engine: Optional[TranslationEngine] = None


def get_engine() -> TranslationEngine:
    global _engine
    if not _engine:
        _engine = TranslationEngine()
    return _engine


@traced("graph.node.translate")
async def translation_engine_node(state: dict) -> dict:
    """LangGraph node that runs the TranslationEngine over the job's segments."""
    logger.info("=== TRANSLATION ENGINE NODE ===")

    segments = state.get('segments', [])
    if not segments:
        logger.warning("No segments to translate")
        return state

    engine = get_engine()

    try:
        result_segments, quality_report = await engine.translate_document(
            doc_id=state['doc_id'],
            segments=segments,
            target_language=state['target_language'],
            constraint_pack=state.get('constraint_pack', {}),
        )

        # Merge translations back into state segments
        result_map = {s['segment_id']: s for s in result_segments}
        for seg in state['segments']:
            if seg['segment_id'] in result_map:
                seg.update(result_map[seg['segment_id']])

        state['quality_report'] = quality_report
        job_id = state.get('job_id')

        # TMX-A6-2: record qualified-supplier consumption (A6) into the
        # immutable v2 audit chain (A1) — model, token usage, table-derived
        # cost. Wrapped + swallowed: telemetry must never block a translation
        # (A3 metrics carve-out, same contract as _audit_v2_emit Phase 1).
        usage = quality_report.get('usage')
        if usage and job_id:
            try:
                emit_v2_audit_event(
                    job_id=job_id,
                    event_type="LLM_USAGE_RECORDED",
                    actor_id=None,
                    actor_kind="agent",
                    payload={**usage, "_actor_node": "translator"},
                )
            except Exception as e:  # noqa: BLE001 — telemetry never blocks translation (A3)
                logger.warning(f"Failed to emit LLM_USAGE_RECORDED audit event: {e}")

        # TMX-BUDGET-1: record a per-job budget breach in the immutable chain
        # (A1). Same A3-wrapped pattern — the audit signal never blocks the job.
        budget = quality_report.get('budget')
        if budget and budget.get('exceeded') and job_id:
            try:
                emit_v2_audit_event(
                    job_id=job_id,
                    event_type="BUDGET_EXCEEDED",
                    actor_id=None,
                    actor_kind="agent",
                    payload={**budget, "_actor_node": "translator"},
                )
            except Exception as e:  # noqa: BLE001 — audit signal never blocks the job (A3)
                logger.warning(f"Failed to emit BUDGET_EXCEEDED audit event: {e}")

        # TMX-INJ-1b: if the deterministic injection gate (TMX-INJ-1) flagged
        # any source segment, record an INJECTION_DETECTED event in the
        # immutable chain (A1) — an attempted hijack of the qualified-supplier
        # call is security-relevant evidence, not just a quality violation.
        injections = [
            v for v in quality_report.get('violations', [])
            if v.get('category') == DefectCategory.PROMPT_INJECTION.value
        ]
        if injections and job_id:
            try:
                emit_v2_audit_event(
                    job_id=job_id,
                    event_type="INJECTION_DETECTED",
                    actor_id=None,
                    actor_kind="agent",
                    payload={
                        "count": len(injections),
                        "segment_ids": [v.get("segment_id") for v in injections][:50],
                        "messages": [v.get("message") for v in injections][:50],
                        "_actor_node": "translator",
                    },
                )
            except Exception as e:  # noqa: BLE001 — audit signal never blocks the job (A3)
                logger.warning(f"Failed to emit INJECTION_DETECTED audit event: {e}")

        logger.info(f"[Engine Node] Complete: {quality_report.get('status')}")

    except Exception as e:
        logger.error(f"[Engine Node] Failed: {e}")
        state['error'] = str(e)

    return state
