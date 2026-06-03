import asyncio
import logging
from typing import Dict, Any, Optional
from langchain_core.messages import SystemMessage, HumanMessage
from app.services.llm import get_llm
from app.services.db_service import get_db_service
from app.services.quality_gate import get_quality_gate_service
from app.services.tracing import traced
from app.services.llm_usage import extract_token_usage, emit_usage_event
from app.core.config import settings

logger = logging.getLogger(__name__)

CONCURRENCY_LIMIT = 10

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
    print("--- REVERSE TRANSLATE NODE (PARALLEL) ---")
    
    # Use correct state variable names that match TransMaxState
    target_lang = state.get("target_language", "de")  # The language we translated to (e.g., German)
    source_lang = state.get("source_language", "en")  # Back-translate to actual source language
    
    segments = state.get("segments", [])
    if not segments:
        print("No segments to reverse translate")
        return {"segments": segments}
        
    llm = get_llm()
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
                        print(f"Drift calculation failed for {seg.get('segment_id')}: {e}")
                
                return {
                    "segment_id": seg['segment_id'],
                    "reverse_translation": reverse_text,
                    "validation_score": validation_score
                }
            except Exception as e:
                print(f"Reverse Translation Failed for {seg.get('segment_id')}: {e}")
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
            print(f"Persisted {len(updates)} reverse translations with validation scores.")
            
            # 2. Compute Aggregate Drift Score from calculated scores
            scores = [u.get('validation_score') for u in updates if u.get('validation_score') is not None]
            avg_drift = sum(scores) / len(scores) if scores else 0
            
            print(f"--- Global Semantic Drift Score: {avg_drift:.2f} ---")
            print(f"    Segments with score >= 90: {len([s for s in scores if s >= 90])}")
            print(f"    Segments with score 70-90: {len([s for s in scores if 70 <= s < 90])}")
            print(f"    Segments with score < 70:  {len([s for s in scores if s < 70])}")
            
            # 3. Update Scorecard
            if state.get('job_id'):
                db.update_quality_scorecard_metric(state['job_id'], {"drift_score": int(avg_drift)})
                
        except Exception as e:
            print(f"Reflexion Persistence Failed: {e}")

    # TMX-A6-2b-reflexion: record the reflexion pass's qualified-supplier
    # consumption in the immutable chain (A6/A1), summed across all segments.
    # Per-job total = translate + refine + reflexion usage events. A3-wrapped.
    job_id = state.get('job_id')
    if job_id and (usage_acc["in"] or usage_acc["out"]):
        try:
            emit_usage_event(
                job_id, settings.default_gpt_model, usage_acc["in"], usage_acc["out"],
                actor_node="reflexion", extra={"pass": "reflexion"},
            )
        except Exception as e:  # noqa: BLE001 — telemetry never blocks the pipeline (A3)
            logger.warning(f"Failed to emit reflexion LLM_USAGE_RECORDED: {e}")

    return {"segments": segments}

