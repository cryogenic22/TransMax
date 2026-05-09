import asyncio
from typing import List, Optional
from app.agents.graph import app as graph_app
from app.core.tenant_context import org_context
from app.models.database import SessionLocal, Document # For error handling updates

async def run_pipeline_wrapper(
    doc_id: str,
    target_lang: str,
    segment_ids: Optional[List[str]] = None,
    *,
    org_id: str,
):
    """Execute the LangGraph pipeline for a specific document.

    TMX-3012c: caller MUST provide `org_id`. The wrapper enters
    `org_context(org_id)` so every DB write inside the pipeline (segments,
    audit records, scorecards, DLQ entries) is correctly tenanted via the
    auto-inject mixin. A3 forbids silent fallbacks; we never default here.
    """
    print(f"[Runner] Starting job {doc_id} for {target_lang}")
    if segment_ids:
        print(f"[Runner] Filtering to {len(segment_ids)} selected segments")

    initial_state = {
        "doc_id": doc_id,
        "job_id": doc_id, # TMX-020: Required for Audit Logging
        "target_language": target_lang,
        "segment_ids_filter": segment_ids,  # NEW: Optional filter for specific segments
        "constraint_pack": {},
        "segments": [],
        "iteration_count": 0,
        "quality_report": {},
        "error": None
    }

    with org_context(org_id):
        try:
            # Ainvoke the graph
            final_state = await graph_app.ainvoke(initial_state)

            if final_state.get("error"):
                print(f"[Runner] Job {doc_id} failed logic: {final_state['error']}")
                # Update DB to error if not handled inside

            print(f"[Runner] Job {doc_id} completed.")

        except Exception as e:
            print(f"[Runner] CRITICAL FAILURE for {doc_id}: {e}")
            # Fail-safe DB update
            with SessionLocal() as db:
                doc = db.query(Document).filter(Document.id == doc_id).first()
                if doc:
                    doc.status = "error" # Add to Enum later if needed, or stick to PROCESSING?
                    db.commit()


def run_pipeline_background(
    doc_id: str,
    target_lang: str,
    segment_ids: Optional[List[str]] = None,
    *,
    org_id: str,
):
    """Synchronous entry point for FastAPI BackgroundTasks to run async loop.

    TMX-3012c: `org_id` is required and threaded into `run_pipeline_wrapper`
    so the fresh asyncio loop spawned by `asyncio.run(...)` carries the
    correct tenant context. Without this, every DB write inside the pipeline
    would raise `TenantContextMissing` once the explicit `DEFAULT_ORG_ID`
    literals are removed from the service layer.
    """
    asyncio.run(run_pipeline_wrapper(doc_id, target_lang, segment_ids, org_id=org_id))
