"""TMX-A6-2b-reflexion — capture reflexion-pass tokens in usage telemetry.

The reverse_translate (reflexion) node makes a back-translation LLM call per
segment whose tokens were never captured. This loop accumulates them and emits
an LLM_USAGE_RECORDED event (_actor_node='reflexion'), completing per-job
consumption (translate + refine + reflexion).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import text

ORG = "00000000-0000-0000-0000-0000000000c1"


def _seed_org_and_job(core_db, org_id: str, job_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    src_id = str(uuid.uuid4())
    with core_db.engine.begin() as conn:
        conn.execute(text(
            "INSERT OR IGNORE INTO organizations "
            "(id, name, slug, org_kind, is_active, created_at, updated_at) "
            "VALUES (:id, :n, :s, 'customer', 1, :ts, :ts)"
        ).bindparams(id=org_id, n="org-rfx", s="org-rfx", ts=now))
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


class _FakeReflexionResponse:
    def __init__(self, in_tok, out_tok):
        self.content = "back-translated text"
        self.response_metadata = {"token_usage": {"prompt_tokens": in_tok, "completion_tokens": out_tok}}


class _FakeLLM:
    async def ainvoke(self, messages):
        # 50/25 tokens per segment call
        return _FakeReflexionResponse(50, 25)


async def test_reflexion_emits_aggregated_usage_event(fresh_engine_for_db, monkeypatch):
    """Two segments back-translated ⇒ one LLM_USAGE_RECORDED (_actor_node=
    'reflexion') summing both calls' tokens (2×50 in, 2×25 out)."""
    import app.agents.nodes.reverse_translate as rt
    from app.agents import _audit_v2_emit
    from app.core.tenant_context import org_context

    core_db = fresh_engine_for_db
    job_id = str(uuid.uuid4())
    _seed_org_and_job(core_db, ORG, job_id)
    _audit_v2_emit.reset_writer_singleton_for_test()

    monkeypatch.setattr(rt, "get_llm", lambda *a, **k: _FakeLLM())

    state = {
        "job_id": job_id,
        "target_language": "es",
        "source_language": "en",
        "segments": [
            {"segment_id": "1", "source_text": "Hello", "translated_text": "Hola"},
            {"segment_id": "2", "source_text": "World", "translated_text": "Mundo"},
        ],
    }

    with org_context(ORG):
        await rt.reverse_translate_node(state)
        events = _query_usage(core_db, job_id)

    reflexion = [e for e in events if e.payload.get("_actor_node") == "reflexion"]
    assert len(reflexion) == 1
    assert reflexion[0].payload["input_tokens"] == 100   # 2 × 50
    assert reflexion[0].payload["output_tokens"] == 50    # 2 × 25
    assert reflexion[0].payload["pass"] == "reflexion"


async def test_reflexion_no_tokens_no_event(fresh_engine_for_db, monkeypatch):
    """If the back-translation yields no token usage, no event is emitted."""
    import app.agents.nodes.reverse_translate as rt
    from app.agents import _audit_v2_emit
    from app.core.tenant_context import org_context

    core_db = fresh_engine_for_db
    job_id = str(uuid.uuid4())
    _seed_org_and_job(core_db, ORG, job_id)
    _audit_v2_emit.reset_writer_singleton_for_test()

    class _ZeroLLM:
        async def ainvoke(self, messages):
            r = _FakeReflexionResponse(0, 0)
            r.response_metadata = {}
            return r

    monkeypatch.setattr(rt, "get_llm", lambda *a, **k: _ZeroLLM())

    state = {
        "job_id": job_id, "target_language": "es", "source_language": "en",
        "segments": [{"segment_id": "1", "source_text": "Hi", "translated_text": "Hola"}],
    }
    with org_context(ORG):
        await rt.reverse_translate_node(state)
        events = _query_usage(core_db, job_id)

    assert [e for e in events if e.payload.get("_actor_node") == "reflexion"] == []
