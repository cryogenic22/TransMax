from typing import TypedDict, List, Dict, Any, Optional
from datetime import datetime, timezone
import hashlib
import json
import logging

from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage, HumanMessage

from app.agents.prompts import PromptRegistry
from app.services.tracing import traced
from app.services.quality_gate import QualityGateService
from app.services.db_service import DatabaseService
from app.services.audit_service import AuditService
from app.agents._audit_v2_emit import emit_v2_audit_event as _emit_v2_audit_event
from app.agents._config_snapshot import build_config_snapshot
from app.services.resilience import get_resilience_service
from app.services.json_parser import RobustParser
from app.services.llm import get_llm, resolve_model
from app.models.database import DocumentStatus, SegmentStatus
from app.agents.nodes.reverse_translate import reverse_translate_node

# Initialize Logger
logger = logging.getLogger(__name__)

# Initialize Service Globals (None initially)
_quality_gate_service = None
_db_service = None
_audit_service = None

def get_quality_gate_service():
    global _quality_gate_service
    if not _quality_gate_service:
        _quality_gate_service = QualityGateService()
    return _quality_gate_service

def get_db_service():
    global _db_service
    if not _db_service:
        _db_service = DatabaseService()
    return _db_service

def get_audit_service():
    global _audit_service
    if not _audit_service:
        _audit_service = AuditService()
    return _audit_service

class TransMaxState(TypedDict):
    """
    The state object flowing through the TransMax graph.
    """
    # Input
    doc_id: str
    target_language: str
    source_language: Optional[str]  # Any-to-any: detected or specified source language
    job_id: Optional[str] # Added job_id optional
    audit_id: Optional[str] # TMX-020: Linked Audit Trail
    segment_ids_filter: Optional[List[str]]  # Optional filter for selective translation
    
    # Internal Resources
    constraint_pack: Dict[str, Any]
    
    # Processing State
    segments: List[Dict[str, Any]] # In-memory representation for LLM
    quality_report: Dict[str, Any]
    scorecard_history: List[Dict[str, Any]] # Epic 2: Track evolution
    iteration_count: int
    final_decision: Optional[str]
    
    # Error handling
    error: Optional[str]
    
    # Reflexion (Sprint D)
    reverse_translation: Optional[str]
    # TMX-DRIFT-GATE: back-translation fidelity review flags set by the reflexion node.
    reflexion_review_required: Optional[bool]
    reflexion_min_score: Optional[float]
    # TMX-3211: explicit "stop refining, go straight to finalize" signal — replaces
    # the old iteration_count=999 sentinel. Set on a safety regression during refine.
    force_finalize: Optional[bool]

# ---------------------------------------------------------
# NODES
# ---------------------------------------------------------

@traced("graph.node.validate")
async def validate_request(state: TransMaxState) -> TransMaxState:
    """
    Validates input and ensures document exists.
    """
    logger.info(f"Validating document {state['doc_id']}...")
    
    current_status = get_db_service().get_document_status(state['doc_id'])
    if not current_status:
        error_msg = f"Document {state['doc_id']} not found"
        logger.error(error_msg)
        raise ValueError(error_msg)
        
    # Update status to PROCESSING if not already
    try:
        get_db_service().update_document_status(state['doc_id'], DocumentStatus.PROCESSING.value)
    except Exception as e:
        logger.warning(f"Failed to update document status, proceeding anyway: {e}")
    
    # Resolve source language: metadata → auto-detect → fallback to "en"
    if not state.get('source_language'):
        try:
            doc_meta = get_db_service().get_document_metadata(state['doc_id'])
            if doc_meta and doc_meta.get('source_language'):
                state['source_language'] = doc_meta['source_language']
            else:
                # Auto-detect from first segments
                from app.services.language_detection import detect_language
                segments = get_db_service().get_segments_for_doc(state['doc_id'])
                sample_text = " ".join(s['source_text'] for s in segments[:5])[:2000]
                if sample_text.strip():
                    detection = detect_language(sample_text)
                    if detection.confidence >= 0.5:
                        state['source_language'] = detection.language
                        logger.info(f"Auto-detected source language: {detection.language} (confidence={detection.confidence:.2f})")
                    else:
                        state['source_language'] = "en"
                        logger.info(f"Low detection confidence ({detection.confidence:.2f}), defaulting to 'en'")
                else:
                    state['source_language'] = "en"
        except Exception as e:
            logger.warning(f"Language detection failed: {e}, defaulting to 'en'")
            state['source_language'] = "en"

    # Initialize iteration state
    state['iteration_count'] = 0
    
    # TMX-020: Initialize GxP Audit Trail
    # If job_id exists (it should via API), create the chain.
    if state.get('job_id'):
        audit_svc = get_audit_service()
        try:
            # 1. Create Trail
            audit_id = audit_svc.create_audit_trail(state['job_id'])
            state['audit_id'] = audit_id

            # 1b. TMX-3110 Phase 1: also emit to v2 chain. The v1 audit_id is
            # preserved in the v2 payload as `audit_id_v1` for cross-reference
            # during the Phase 2 coverage audit (TMX-3110b).
            _emit_v2_audit_event(
                job_id=state['job_id'],
                event_type="AUDIT_TRAIL_INITIALIZED",
                actor_id=None,
                actor_kind="system",
                payload={
                    "audit_id_v1": audit_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )

            # 2. Capture Config Snapshot (Inputs)
            # Freeze the request + the REAL qualified-supplier telemetry: the
            # configured model and the pinned prompt versions + content hashes
            # (A6 / A8). See _build_config_snapshot for the provenance contract.
            config_snapshot = build_config_snapshot(state)
            audit_svc.capture_config_snapshot(state['job_id'], config_snapshot)

            # 2b. TMX-3110 Phase 1: also emit to v2 chain.
            _emit_v2_audit_event(
                job_id=state['job_id'],
                event_type="CONFIG_SNAPSHOT_CAPTURED",
                actor_id=None,
                actor_kind="system",
                payload=config_snapshot,
            )

            # 3. Log Genesis Event
            genesis_payload = {
                "doc_id": state['doc_id'],
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            audit_svc.log_event(audit_id, "JOB_STARTED", genesis_payload)

            # 3b. TMX-3110 Phase 1: also emit to v2 chain.
            _emit_v2_audit_event(
                job_id=state['job_id'],
                event_type="JOB_STARTED",
                actor_id=None,
                actor_kind="system",
                payload=genesis_payload,
            )

        except Exception as e:
            logger.error(f"Failed to initialize Audit Trail: {e}")
            # In strict GxP, we might start failing here. For now, log.

    return state

@traced("graph.node.load_segments")
async def load_segments(state: TransMaxState) -> TransMaxState:
    """
    Loads segments from the database (v2.0 table) into the graph state.
    If segment_ids_filter is provided, only those segments are loaded for translation.
    """
    logger.info(f"Loading segments for {state['doc_id']}...")
    
    segments_list = get_db_service().get_segments_for_doc(state['doc_id'])
    
    # Filter segments if segment_ids_filter is provided
    segment_filter = state.get('segment_ids_filter')
    if segment_filter:
        filter_set = set(segment_filter)
        segments_list = [s for s in segments_list if s['segment_id'] in filter_set]
        logger.info(f"Filtered to {len(segments_list)} selected segments (out of {len(filter_set)} requested).")
    else:
        logger.info(f"Loaded all {len(segments_list)} segments.")
    
    state['segments'] = segments_list
        
    return state

@traced("graph.node.constraints")
async def compile_constraints(state: TransMaxState) -> TransMaxState:
    """
    Fetches Glossary terms and TM matches via pgvector.
    """
    logger.info("Compiling constraints...")
    segments = state.get('segments', [])
    if not segments:
        state['constraint_pack'] = {"glossary": [], "tm_matches": []}
        return state

    query_text = " ".join([s['source_text'] for s in segments])[:2000]

    # Resolve glossary_id from the document record
    glossary_id = None
    try:
        from app.models.database import SessionLocal, Document
        with SessionLocal() as _session:
            doc = _session.query(Document).filter(Document.id == state['doc_id']).first()
            if doc and doc.glossary_id:
                glossary_id = doc.glossary_id
    except Exception as e:
        logger.warning(f"Failed to read glossary_id from document: {e}")

    # Reuse existing logic in db_service
    source_lang = state.get('source_language', 'en')
    constraints = get_db_service().get_constraints(
        source_lang=source_lang,
        target_lang=state['target_language'],
        query_text=query_text,
        glossary_id=glossary_id,
    )
    
    state['constraint_pack'] = constraints
    
    # Batch exact-match lookup: single DB query replaces N sequential find_best_match() calls
    logger.info("Checking for TM Exact Matches (batch)...")
    exact_matches = get_db_service().find_exact_matches_batch(
        segments=state['segments'],
        source_lang=source_lang,
        target_lang=state['target_language']
    )
    for seg in state['segments']:
        match = exact_matches.get(seg['segment_id'])
        if match:
            seg['tm_match'] = match

    logger.info(f"Found {len(exact_matches)} exact TM matches.")
    return state





from app.core.defect_taxonomy import DefectSeverity, DefectCategory, is_critical

@traced("graph.node.gates")
async def run_quality_gates(state: TransMaxState) -> TransMaxState:
    """
    Runs deterministic checks, updates Segment.gate_results, and persists Quality Scorecard.
    The Safety Net (Epic 2): Tracks history and detects regressions.
    """
    logger.info("Running Quality Gates (Regulatory Risk Control)...")
    try:
        violations = []
        constraint_pack = state.get('constraint_pack', {})
        updates = []
        
        # 1. Run Checks per Segment
        for seg in state['segments']:
            if not seg.get('translated_text'):
                continue
            seg_defects = get_quality_gate_service().check_segment(
                source_text=seg['source_text'],
                target_text=seg['translated_text'],
                constraints=constraint_pack,
                target_lang=state['target_language'],
                source_lang=state.get('source_language', 'en')
            )
            
            gate_results = {
                "units_ok": not any(d['category'] == DefectCategory.UNIT_MISMATCH.value for d in seg_defects),
                "negation_ok": not any(d['severity'] == DefectSeverity.CRITICAL.value for d in seg_defects),
                "pii_redacted": not any(d['category'] == DefectCategory.PII_LEAK.value for d in seg_defects),
                "violations": seg_defects
            }
            
            has_critical = any(d['severity'] == DefectSeverity.CRITICAL.value for d in seg_defects)
            update_data = {
                "segment_id": seg['segment_id'],
                "gate_results": gate_results
            }
            if has_critical:
                logger.warning(f"CRITICAL DEFECT in Segment {seg['segment_id']}: BLOCKING.")
                update_data["status"] = SegmentStatus.BLOCKED.value
            updates.append(update_data)
            
            if seg_defects:
                for d in seg_defects:
                    d['segment_id'] = seg['segment_id']
                violations.extend(seg_defects)
        
        if updates:
            get_db_service().update_segments_batch(updates)
            logger.info("Quality gates persisted.")

        # 2. Verdict & History (Epic 1 & 2)
        gate_service = get_quality_gate_service()
        verdict = gate_service.evaluate_verdict(violations)
        
        status = verdict["status"]
        current_metrics = verdict["metrics"]
        
        # --- Epic 2: Regression Check ---
        history = state.get('scorecard_history', [])
        
        if history:
            prev_metrics = history[-1]['metrics'] # Last entry
            comparison = gate_service.compare_scorecards(prev_metrics, current_metrics)
            logger.info(f"Reflexion Outcome: {comparison}")
            
            if comparison == "DEGRADED":
                logger.warning("SAFETY REGRESSION: Refinement made things worse.")
                # Force Exit Loop (fail safe)
                if status != "BLOCKED":
                    status = "REVIEW_REQUIRED"
                    verdict["reason"] = "Safety Regression detected during refinement."
                # We do not update history with this bad run, or we mark it?
                # We let it pass to state, decide_next_step will see REVIEW_REQUIRED and if it checks history it might stop?
                # Actually, simply setting status to REVIEW_REQUIRED is enough, but we should ensure decide_next_step stops.
                # If we are in loop, decide_next_step checks iterations < 3.
                # If we set STATUS="REVIEW_REQUIRED", it continues if it < 3.
                # TMX-3211: a safety regression during refinement must stop the
                # loop and route straight to finalize. An explicit flag is read
                # by decide_next_step — clearer + testable than overloading the
                # iteration counter with a magic 999 sentinel.
                state['force_finalize'] = True

        # Append current to history
        new_history_entry = {
            "metrics": current_metrics,
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        history.append(new_history_entry)
        state['scorecard_history'] = history

        logger.info(f"Gate Verdict: {status} ({verdict['reason']})")
        
        # Scorecard Persistence
        scorecard_data = {
            "status": status,
            "drift_score": 0,
            "pass_rate": 100 if not violations else max(0, 100 - (len(violations) * 5)) 
        }
        
        if state.get('job_id'):
            get_db_service().save_quality_scorecard(state['job_id'], scorecard_data, violations)
            if state.get('audit_id'):
                scorecard_payload = {
                    "status": status,
                    "reason": verdict["reason"],
                    "metrics": current_metrics
                }
                get_audit_service().log_event(state['audit_id'], "SCORECARD_GENERATED", scorecard_payload)
                # TMX-3110 Phase 1: also emit to v2 chain. quality_gate node IS
                # the agent emitting this — actor_kind=agent. NOTE: actor_id is
                # `None` because v2 schema types actor_id as GUID (FK target),
                # and agent node-names are not UUIDs. The node-name is preserved
                # in the payload as `_actor_node` for cross-reference until
                # TMX-3110-actor-id-schema decides whether to widen actor_id to
                # String or to mint UUID5s per node-name.
                _emit_v2_audit_event(
                    job_id=state['job_id'],
                    event_type="SCORECARD_GENERATED",
                    actor_id=None,
                    actor_kind="agent",
                    payload={**scorecard_payload, "_actor_node": "quality_gate"},
                )

        state['quality_report'] = {
            "violations": violations,
            "count": len(violations),
            "status": status,
            "scorecard": scorecard_data
        }
        
    except Exception as e:
        logger.error(f"Quality Gate Error: {e}")
        state['error'] = f"Quality Gate Failed: {e}"
        state['quality_report'] = {"status": "BLOCKED", "error": str(e)}
        
    return state

@traced("graph.node.refine")
async def refine_translation(state: TransMaxState) -> TransMaxState:
    """
    Auto-fixes non-critical violations.
    """
    logger.info(f"Refining Translation (Iteration {state.get('iteration_count', 0) + 1})...")
    state['iteration_count'] = state.get('iteration_count', 0) + 1
    
    constraint_pack = state.get('constraint_pack', {})
    violations = state.get('quality_report', {}).get('violations', [])
    
    # Identify segments that need fixing
    # (Those with violations, excluding TM Exact Matches which shouldn't happen here if logic holds)
    problem_segment_ids = set(v['segment_id'] for v in violations)
    
    to_refine = []
    for seg in state['segments']:
        if seg['segment_id'] in problem_segment_ids:
             # Enrich with specific violations for that segment
             # FILTER: Only include NON-CRITICAL violations for auto-fix
             # Critical violations must be handled by human (Safety Rule)
             seg_violations = [v for v in violations if v['segment_id'] == seg['segment_id'] and not is_critical(v.get('severity'))]
             
             if seg_violations:
                 to_refine.append({
                     "segment_id": seg['segment_id'], # Fixer prompt expects segment_id
                     "source_text": seg['source_text'],
                     "translated_text": seg['translated_text'],
                     "violations": [v['message'] for v in seg_violations]
                 })
             
    if not to_refine:
        return state

    # Construct Refinement Prompt
    # We can reuse the translator user prompt but with "Fix these specific issues" instruction
    # Ideally a specialized prompt. For v2.0/Sprint 6, we'll append instructions.
    
    
    refinement_payload = json.dumps(to_refine, indent=2)
    
    # Use Targeted Fixer Prompt
    fixer_prompt = PromptRegistry.load("fixer")
    user_content = fixer_prompt.user.replace(
        "{{target_language}}", state['target_language']
    ).replace(
        "{{constraint_pack_json}}", json.dumps(constraint_pack)
    ).replace(
        "{{segments_to_fix_json}}", refinement_payload
    )

    messages = [
        SystemMessage(content=fixer_prompt.system),
        HumanMessage(content=user_content)
    ]

    # TMX-ROUTER-5: cost-aware posture from the consumption so far (the
    # translate pass's usage). When the job is near its budget the router
    # downgrades the refine model tier. No-op unless routing + a budget are on.
    from app.services.budget_guard import JobBudget, budget_posture as _budget_posture
    _u = state.get('quality_report', {}).get('usage', {}) or {}
    _posture = _budget_posture(
        _u.get('total_tokens', 0), _u.get('estimated_cost_usd', 0.0), JobBudget.from_settings()
    )

    ref_in = ref_out = 0
    try:
        response = await get_resilience_service().resilient_llm_call(
            get_llm(task="refine", budget_posture=_posture).ainvoke, messages
        )
        # TMX-A6-2b: capture the refinement call's tokens before any parse/DB
        # work so the consumption is recorded even if downstream steps fail.
        from app.services.llm_usage import extract_token_usage
        ref_in, ref_out = extract_token_usage(response)
        data = RobustParser.parse(response.content)
        
        # Helper to find list
        fixed_segments = data.get('fixed_segments') or data.get('segments', [])
        
        refinement_updates = []
        
        for fixed in fixed_segments:
            seg_id = fixed.get('segment_id') or fixed.get('id')
            new_text = fixed.get('target_text') or fixed.get('translated_text')
            
            if seg_id and new_text:
                refinement_updates.append({
                    "segment_id": seg_id,
                    "translated_text": new_text
                })
                
                # Update state
                for s in state['segments']:
                    if s['segment_id'] == seg_id:
                        s['translated_text'] = new_text
                        
        if refinement_updates:
            get_db_service().update_segments_batch(refinement_updates)
            logger.info("Refined translations applied.")
            
    except Exception as e:
        logger.error(f"Refinement failed: {e}")
        # If refinement fails, we proceed. The Gate will verify again (or next step).

    # TMX-A6-2b: record the refinement pass's qualified-supplier consumption in
    # the immutable chain (A6/A1). Per-job total = sum of all usage events
    # (translate + each refinement). A3-wrapped: never blocks the pipeline.
    job_id = state.get('job_id')
    if job_id and (ref_in or ref_out):
        try:
            from app.services.llm_usage import emit_usage_event
            emit_usage_event(
                job_id, resolve_model(task="refine", budget_posture=_posture), ref_in, ref_out,
                actor_node="refiner",
                extra={"pass": "refinement", "iteration": state.get('iteration_count')},
            )
        except Exception as e:  # noqa: BLE001 — telemetry never blocks the pipeline (A3)
            logger.warning(f"Failed to emit refinement LLM_USAGE_RECORDED: {e}")

    return state

def decide_next_step(state: TransMaxState):
    """
    Routing logic.
    """
    report = state.get('quality_report', {})
    status = report.get('status', 'PASS')
    iterations = state.get('iteration_count', 0)
    
    logger.info(f"Decision Point: Status={status}, Iterations={iterations}")

    # TMX-3211: an explicit force_finalize (set on a safety regression during
    # refine) short-circuits the refinement loop — no magic iteration sentinel.
    if state.get('force_finalize'):
        logger.info("force_finalize set — routing straight to finalize")
        return "finalize"

    if status == "BLOCKED":
        # Critical Safety Failure -> End immediately (or Finalize with BLOCKED status)
        return "finalize" # Finalize will mark document done (but segments are blocked)
        
    if status == "REVIEW_REQUIRED":
        if iterations < 3: # Max 3 loops
            return "refine"
        else:
            logger.info("Max iterations reached. Proceeding with REVIEW_REQUIRED.")
            return "finalize"
            
    return "finalize"

def _compute_output_hash(segments: List[Dict[str, object]]) -> str:
    """Deterministic SHA-256 over the ordered translated output (TMX-3213).

    The terminal ``JOB_FINALIZED`` audit event must anchor the actual artefact
    it certifies, not a placeholder (CLAUDE.md A1 — the audit chain's last link
    must be evidential). We canonicalise the ordered
    ``(order_index, segment_id, translated_text)`` triples and hash them with the
    same idiom ``audit_service`` already uses (sha256 over ``sort_keys`` JSON),
    so the hash is order-stable and reproducible from the stored segments.

    Pure + total: a zero-segment job hashes the empty canonical form rather than
    raising.
    """
    triples = sorted(
        (
            (s.get("order_index", idx), str(s.get("segment_id", "")), s.get("translated_text") or "")
            for idx, s in enumerate(segments)
        ),
        key=lambda t: (t[0], t[1]),
    )
    canonical = json.dumps(
        [{"order": o, "id": sid, "text": text} for o, sid, text in triples],
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@traced("graph.node.finalize")
async def finalize_job(state: TransMaxState) -> TransMaxState:
    """
    Marks document as TRANSLATED.
    """
    logger.info(f"Finalizing document {state['doc_id']}...")
    
    # Determining Final Status
    report = state.get('quality_report', {})
    status = report.get('status', 'PASS')
    
    final_status = DocumentStatus.TRANSLATED
    if status in ["BLOCKED", "REVIEW_REQUIRED"]:
        # If there are blocked segments or unresolved issues, send to REVIEW
        final_status = DocumentStatus.IN_REVIEW

    # TMX-DRIFT-GATE: low back-translation fidelity holds the job for a human
    # even when the deterministic gates passed. One-directional (only escalates
    # TRANSLATED -> IN_REVIEW, never downgrades a held status) — A3 fail-toward-review.
    if state.get('reflexion_review_required') and final_status == DocumentStatus.TRANSLATED:
        logger.info(
            "Reflexion drift gate: holding job for review "
            f"(min back-translation score {state.get('reflexion_min_score')})"
        )
        final_status = DocumentStatus.IN_REVIEW
        
    try:
        get_db_service().update_document_status(state['doc_id'], final_status.value)
    except Exception as e:
        logger.warning(f"Failed to update finalize status: {e}")
    
    # AUDIT LOGGING (Sprint 6.5 -> Wave 1 Update)
    # Persist the final state and decision to the immutable audit log
    try:
        if state.get('audit_id'):
            # Log Final Event
            final_payload = {
                "final_status": str(final_status),
                "decision": "PASS" if final_status == DocumentStatus.TRANSLATED else "HELD",
                "output_hash": _compute_output_hash(state.get('segments', [])),
            }
            # TMX-DRIFT-GATE: record why the job was held when back-translation
            # fidelity triggered the review escalation (audit-visible reason).
            if state.get('reflexion_review_required'):
                final_payload["reflexion_review_required"] = True
                final_payload["reflexion_min_score"] = state.get('reflexion_min_score')
            get_audit_service().log_event(state['audit_id'], "JOB_FINALIZED", final_payload)
            logger.info(f"Finalized Audit Trail {state['audit_id']}")

            # TMX-3110 Phase 1: also emit to v2 chain. finalize_job node IS
            # the agent making the final decision — actor_kind=agent. See the
            # quality_gate emit above for why actor_id stays None and the node
            # name lives in payload['_actor_node'] (GUID schema constraint).
            if state.get('job_id'):
                _emit_v2_audit_event(
                    job_id=state['job_id'],
                    event_type="JOB_FINALIZED",
                    actor_id=None,
                    actor_kind="agent",
                    payload={**final_payload, "_actor_node": "finalizer"},
                )

    except Exception as e:
        logger.error(f"Warning: Failed to save audit log: {e}")

    return state

# ---------------------------------------------------------
# GRAPH CONSTRUCTION
# ---------------------------------------------------------

# Import the production-grade translation engine
from app.agents.nodes.translation_engine_node import translation_engine_node

workflow = StateGraph(TransMaxState)

workflow.add_node("validate", validate_request)
workflow.add_node("load_segments", load_segments)
workflow.add_node("constraints", compile_constraints)
workflow.add_node("translate", translation_engine_node)  # Production-grade concurrent engine
workflow.add_node("gates", run_quality_gates)
workflow.add_node("refine", refine_translation)
workflow.add_node("reflexion", reverse_translate_node)
workflow.add_node("finalize", finalize_job)

# Flow with Refinement Loop
workflow.set_entry_point("validate")
workflow.add_edge("validate", "load_segments")
workflow.add_edge("load_segments", "constraints")
workflow.add_edge("constraints", "translate")
workflow.add_edge("translate", "gates")

workflow.add_conditional_edges(
    "gates",
    decide_next_step,
    {
        "refine": "refine",
        "finalize": "reflexion"
    }
)

workflow.add_edge("reflexion", "finalize")

workflow.add_edge("refine", "gates")  # Loop back to gates
workflow.add_edge("finalize", END)

# Compile
app = workflow.compile()

