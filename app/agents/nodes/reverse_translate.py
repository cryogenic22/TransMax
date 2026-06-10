import asyncio
import logging
from typing import Dict, Any, Optional
from langchain_core.messages import SystemMessage, HumanMessage
from app.services.llm import get_llm, resolve_model
from app.services.db_service import get_db_service
from app.services.quality_gate import get_quality_gate_service
from app.services.tracing import traced
from app.services.llm_usage import extract_token_usage, emit_usage_event

logger = logging.getLogger(__name__)

CONCURRENCY_LIMIT = 10

# TMX-DRIFT-GATE: a back-translation fidelity score (0-100, 100=identical) below
# this threshold holds the job for human review. Module constant for now — one
# edit away from per-tenant config later.
REFLEXION_REVIEW_THRESHOLD = 70.0


def assess_reflexion(
    segments: list[Dict[str, object]], threshold: float = REFLEXION_REVIEW_THRESHOLD
) -> Dict[str, object]:
    """Decide whether back-translation drift should hold the job for review.

    Only *genuinely assessed* scores count: ``validation_score`` must be
    ``not None`` and ``> 0.0``. ``calculate_semantic_drift`` returns ``0.0`` when
    there is no API key — indistinguishable from a real catastrophic score — so
    holding every keyless job would be a false-positive flood (A3: don't hold on
    a non-signal). See TMX-DRIFT-SENTINEL for the follow-up that makes the
    method return ``None`` on no-key.

    Returns ``{review_required, min_score, n_assessed, n_below}``. Pure.
    """
    scores = [
        s.get("validation_score")
        for s in segments
        if s.get("validation_score") is not None and s.get("validation_score") > 0.0
    ]
    if not scores:
        return {"review_required": False, "min_score": None, "n_assessed": 0, "n_below": 0}
    min_score = min(scores)
    n_below = sum(1 for sc in scores if sc < threshold)
    return {
        "review_required": n_below > 0,
        "min_score": min_score,
        "n_assessed": len(scores),
        "n_below": n_below,
    }

@traced("graph.node.reflexion")
async def reverse_translate_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    TMX-D020: Performs reverse translation for Reflexion.
    Translates EACH segment's 'translated_text' BACK to 'source_language' (English).
    Uses asyncio.gather with Semaphore for parallel processing (Sprint 4.1).
    
    This validates that the translation maintains semantic accuracy by:
    1. Translating German/French/etc back to English
    2. Comparing back-translation to original English
    3. Computing semantic drift score
    """
    logger.info("Reverse-translate node (parallel) starting")

    # Use correct state variable names that match TransMaxState
    target_lang = state.get("target_language", "de")  # The language we translated to (e.g., German)
    source_lang = state.get("source_language", "en")  # Back-translate to actual source language

    segments = state.get("segments", [])
    if not segments:
        logger.info("No segments to reverse translate")
        return {
            "segments": segments,
            "reflexion_review_required": False,
            "reflexion_min_score": None,
        }
        
    # TMX-ROUTER-5: cost-aware posture from consumption so far (translate +
    # refine usage on the report). No-op unless routing + a budget are on.
    from app.services.budget_guard import JobBudget, budget_posture
    _u = state.get("quality_report", {}).get("usage", {}) or {}
    _posture = budget_posture(
        _u.get("total_tokens", 0), _u.get("estimated_cost_usd", 0.0), JobBudget.from_settings()
    )

    llm = get_llm(task="review", budget_posture=_posture)  # TMX-ROUTER-2: back-translation = verification
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    # TMX-A6-2b-reflexion: accumulate per-segment back-translation token usage.
    # asyncio is single-threaded so += across the gathered workers is safe.
    usage_acc = {"in": 0, "out": 0}
    
    system_msg = SystemMessage(content=f"""You are a strict linguistic auditor performing back-translation verification.
    Translate the following {target_lang} text back into {source_lang}.
    Maintain exact meaning, tone, and technical precision.
    Do not add explanations or notes. Return ONLY the translation.""")

    async def process_segment(seg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Async worker for a single segment.
        Performs back-translation and calculates semantic drift score.
        """
        trans_text = seg.get("translated_text")
        if not trans_text:
            return None
            
        # Optimization: Skip if already has reverse translation
        # if seg.get('reverse_translation'): return None 

        async with semaphore:
            try:
                user_msg = HumanMessage(content=f"Text: {trans_text}")
                # Use ainvoke for async
                response = await llm.ainvoke([system_msg, user_msg])
                # TMX-A6-2b-reflexion: account this back-translation call's tokens.
                _i, _o = extract_token_usage(response)
                usage_acc["in"] += _i
                usage_acc["out"] += _o
                reverse_text = response.content.strip()
                
                # Update In-Memory
                seg['reverse_translation'] = reverse_text
                
                # Calculate validation score (semantic drift) for this segment
                source_text = seg.get('source_text', '')
                validation_score = None
                if source_text and reverse_text:
                    try:
                        gate_svc = get_quality_gate_service()
                        validation_score = gate_svc.calculate_semantic_drift(source_text, reverse_text)
                        seg['validation_score'] = validation_score
                    except Exception as e:
                        logger.warning(f"Drift calculation failed for {seg.get('segment_id')}: {e}")
                
                return {
                    "segment_id": seg['segment_id'],
                    "reverse_translation": reverse_text,
                    "validation_score": validation_score
                }
            except Exception as e:
                logger.warning(f"Reverse translation failed for {seg.get('segment_id')}: {e}")
                return None

    # Gather all tasks
    tasks = [process_segment(seg) for seg in segments]
    results = await asyncio.gather(*tasks)
    
    # Filter valid updates
    updates = [res for res in results if res is not None]
    
    if updates:
        try:
            # 1. Update Segments Batch with reverse_translation AND validation_score
            db = get_db_service()
            db.update_segments_batch(updates)
            logger.info(f"Persisted {len(updates)} reverse translations with validation scores")

            # 2. Compute Aggregate Drift Score from calculated scores
            scores = [u.get('validation_score') for u in updates if u.get('validation_score') is not None]
            avg_drift = sum(scores) / len(scores) if scores else 0

            logger.info(
                "Global back-translation fidelity: avg=%.2f  (>=90:%d  70-90:%d  <70:%d)",
                avg_drift,
                len([s for s in scores if s >= 90]),
                len([s for s in scores if 70 <= s < 90]),
                len([s for s in scores if s < 70]),
            )

            # 3. Update Scorecard
            if state.get('job_id'):
                db.update_quality_scorecard_metric(state['job_id'], {"drift_score": int(avg_drift)})

        except Exception as e:
            logger.warning(f"Reflexion persistence failed: {e}")

    # TMX-A6-2b-reflexion: record the reflexion pass's qualified-supplier
    # consumption in the immutable chain (A6/A1), summed across all segments.
    # Per-job total = translate + refine + reflexion usage events. A3-wrapped.
    job_id = state.get('job_id')
    if job_id and (usage_acc["in"] or usage_acc["out"]):
        try:
            emit_usage_event(
                job_id, resolve_model(task="review", budget_posture=_posture),
                usage_acc["in"], usage_acc["out"],
                actor_node="reflexion", extra={"pass": "reflexion"},
            )
        except Exception as e:  # noqa: BLE001 — telemetry never blocks the pipeline (A3)
            logger.warning(f"Failed to emit reflexion LLM_USAGE_RECORDED: {e}")

    # TMX-DRIFT-GATE: turn the measured per-segment fidelity into a routing
    # signal finalize_job can act on (A2 deterministic gate, A3 fail-toward-review).
    gate = assess_reflexion(segments)
    if gate["review_required"]:
        logger.info(
            "Reflexion drift gate tripped: %d/%d segment(s) below %.0f (min=%.2f) -> review",
            gate["n_below"], gate["n_assessed"], REFLEXION_REVIEW_THRESHOLD, gate["min_score"],
        )
    return {
        "segments": segments,
        "reflexion_review_required": gate["review_required"],
        "reflexion_min_score": gate["min_score"],
    }

