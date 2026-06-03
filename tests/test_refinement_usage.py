"""TMX-A6-2b — refinement-pass tokens in the usage telemetry.

A6-2 records the initial translate pass only; the graph refiner makes its own
LLM call whose tokens were never captured, so refined jobs under-reported
consumption. This loop extracts a shared usage helper and has the refiner emit
its own LLM_USAGE_RECORDED event (_actor_node='refiner'), so per-job
consumption is the sum of all usage events.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import text

from app.core.model_pricing import cost_for
from app.services.llm_usage import build_usage_record, extract_token_usage

ORG = "00000000-0000-0000-0000-0000000000b6"


# --- pure helpers ---------------------------------------------------------


def test_build_usage_record_shape_and_cost():
    u = build_usage_record("gpt-4o", 1000, 500)
    assert u["model"] == "gpt-4o"
    assert u["pricing_model"] == "gpt-4o-mini"
    assert u["input_tokens"] == 1000
    assert u["output_tokens"] == 500
    assert u["total_tokens"] == 1500
    assert u["currency"] == "USD"
    assert u["estimated_cost_usd"] == round(cost_for("gpt-4o-mini", 1000, 500), 6)


def test_extract_token_usage_response_metadata():
    class R:
        response_metadata = {"token_usage": {"prompt_tokens": 12, "completion_tokens": 7}}
    assert extract_token_usage(R()) == (12, 7)


def test_extract_token_usage_usage_metadata():
    class Meta:
        input_tokens = 5
        output_tokens = 3

    class R:
        usage_metadata = Meta()
    assert extract_token_usage(R()) == (5, 3)


def test_extract_token_usage_missing_is_zero():
    class R:
        pass
    assert extract_token_usage(R()) == (0, 0)


# --- refiner emits its own usage event ------------------------------------


def _seed_org_and_job(core_db, org_id: str, job_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    src_id = str(uuid.uuid4())
    with core_db.engine.begin() as conn:
        conn.execute(text(
            "INSERT OR IGNORE INTO organizations "
            "(id, name, slug, org_kind, is_active, created_at, updated_at) "
            "VALUES (:id, :n, :s, 'customer', 1, :ts, :ts)"
        ).bindparams(id=org_id, n="org-a6b", s="org-a6b", ts=now))
        conn.execute(text(
            "INSERT OR IGNORE INTO translation_jobs "
            "(id, source_document_id, organization_id, source_language, "
            "target_language, provider, is_deleted, created_at) "
            "VALUES (:id, :src, :org, 'en', 'es', 'OPENAI', 0, :ts)"
        ).bindparams(id=job_id, src=src_id, org=org_id, ts=now))


def _query_usage(core_db, job_id: str) -> list:
    from app.models.audit_v2 import AuditEventV2
    session = core_db.SessionLocal()
    try:
        return (
            session.query(AuditEventV2)
            .filter(
                AuditEventV2.job_id == job_id,
                AuditEventV2.event_type == "LLM_USAGE_RECORDED",
            )
            .all()
        )
    finally:
        session.close()


class _FakeRefineResponse:
    content = '{"fixed_segments": [{"segment_id": "1", "target_text": "corrected"}]}'
    response_metadata = {"token_usage": {"prompt_tokens": 300, "completion_tokens": 150}}


class _FakeResilience:
    async def resilient_llm_call(self, fn, messages):
        return _FakeRefineResponse()


async def test_refiner_emits_refinement_usage_event(fresh_engine_for_db, monkeypatch):
    """The refinement pass records its own LLM_USAGE_RECORDED event tagged
    _actor_node='refiner' with the refinement call's token counts."""
    import app.agents.graph as graph
    from app.agents import _audit_v2_emit
    from app.core.tenant_context import org_context

    core_db = fresh_engine_for_db
    job_id = str(uuid.uuid4())
    _seed_org_and_job(core_db, ORG, job_id)
    _audit_v2_emit.reset_writer_singleton_for_test()

    monkeypatch.setattr(graph, "get_resilience_service", lambda: _FakeResilience())

    state = {
        "job_id": job_id,
        "target_language": "es",
        "iteration_count": 0,
        "segments": [{"segment_id": "1", "source_text": "Hi", "translated_text": "Hola"}],
        "quality_report": {"violations": [
            {"segment_id": "1", "severity": "major", "message": "terminology issue"}
        ]},
        "constraint_pack": {},
    }

    with org_context(ORG):
        await graph.refine_translation(state)
        events = _query_usage(core_db, job_id)

    refiner = [e for e in events if e.payload.get("_actor_node") == "refiner"]
    assert len(refiner) == 1
    assert refiner[0].payload["input_tokens"] == 300
    assert refiner[0].payload["output_tokens"] == 150
    assert refiner[0].payload["pass"] == "refinement"
