"""TMX-A6-2 — Per-job LLM usage telemetry in the audit chain.

Closes the A6 (qualified supplier) gap left open by TMX-3202: the config
snapshot records *which* model/prompt was engaged (captured at job start),
but the actual *consumption* — response token usage and resulting cost —
lived only on the mutable ``Document`` row (Feature 5), never in the
immutable audit chain. This loop emits that consumption as a first-class
``LLM_USAGE_RECORDED`` v2 audit event.

Two seams under test:
  * ``TranslationEngine._build_usage()`` — qualified-supplier consumption
    dict: model provenance + token counts + table-derived cost. AC-2/3/4/7.
  * ``translation_engine_node()`` — emits exactly one ``LLM_USAGE_RECORDED``
    v2 event carrying that payload into the chain. AC-1/2/5/6.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import text

from app.core.model_pricing import cost_for

ORG = "00000000-0000-0000-0000-0000000000a6"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_org_and_job(core_db, org_id: str, job_id: str) -> None:
    """Seed the organization + the translation_jobs FK target for job_id."""
    now = datetime.now(timezone.utc).isoformat()
    src_id = str(uuid.uuid4())
    with core_db.engine.begin() as conn:
        conn.execute(
            text(
                "INSERT OR IGNORE INTO organizations "
                "(id, name, slug, org_kind, is_active, created_at, updated_at) "
                "VALUES (:id, :n, :s, 'customer', 1, :ts, :ts)"
            ).bindparams(id=org_id, n="org-a6", s="org-a6", ts=now)
        )
        conn.execute(
            text(
                "INSERT OR IGNORE INTO translation_jobs "
                "(id, source_document_id, organization_id, source_language, "
                "target_language, provider, is_deleted, created_at) "
                "VALUES (:id, :src, :org, 'en', 'es', 'OPENAI', 0, :ts)"
            ).bindparams(id=job_id, src=src_id, org=org_id, ts=now)
        )


def _query_usage_events(core_db, job_id: str) -> list:
    """Return all LLM_USAGE_RECORDED AuditEventV2 rows for job_id."""
    from app.models.audit_v2 import AuditEventV2

    session = core_db.SessionLocal()
    try:
        return (
            session.query(AuditEventV2)
            .filter(
                AuditEventV2.job_id == job_id,
                AuditEventV2.event_type == "LLM_USAGE_RECORDED",
            )
            .order_by(AuditEventV2.sequence_index)
            .all()
        )
    finally:
        session.close()


class _FakeEngine:
    """Stand-in for TranslationEngine.translate_document — returns a report
    with a known usage block, without touching an LLM or DB."""

    def __init__(self, usage):
        self._usage = usage

    async def translate_document(self, doc_id, segments, target_language, constraint_pack):
        report = {"status": "PASSED", "metrics": {}, "violations": []}
        if self._usage is not None:
            report["usage"] = self._usage
        return ([{**s} for s in segments], report)


def _usage(model="gpt-4-turbo-preview", in_tok=1200, out_tok=800):
    return {
        "model": model,
        "pricing_model": "gpt-4o-mini",
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "total_tokens": in_tok + out_tok,
        "estimated_cost_usd": round(cost_for("gpt-4o-mini", in_tok, out_tok), 6),
        "currency": "USD",
        "pricing_source": "app.core.model_pricing",
    }


# ---------------------------------------------------------------------------
# Seam 1 — usage math (pure, no DB)
# ---------------------------------------------------------------------------


def test_build_usage_fields_and_cost_from_table():
    """AC-2/3/4/7: _build_usage returns provenance + token counts + table-derived cost."""
    from app.agents.nodes.translation_engine import TranslationEngine

    eng = TranslationEngine()
    eng._total_input_tokens = 1500
    eng._total_output_tokens = 500
    usage = eng._build_usage("gpt-4o")

    assert usage["model"] == "gpt-4o"  # provenance / supplier model of record (AC-2)
    assert usage["input_tokens"] == 1500
    assert usage["output_tokens"] == 500
    assert usage["total_tokens"] == 2000  # AC-4
    assert usage["currency"] == "USD"
    assert usage["pricing_source"] == "app.core.model_pricing"
    # AC-3: cost is derived from the canonical pricing table, not re-implemented.
    expected = round(cost_for("gpt-4o-mini", 1500, 500), 6)
    assert usage["estimated_cost_usd"] == expected


def test_build_usage_zero_tokens_is_valid():
    """A mocked/0-token run still yields a well-formed (zero-cost) usage record."""
    from app.agents.nodes.translation_engine import TranslationEngine

    eng = TranslationEngine()
    eng._total_input_tokens = 0
    eng._total_output_tokens = 0
    usage = eng._build_usage("gpt-4o-mini")
    assert usage["total_tokens"] == 0
    assert usage["estimated_cost_usd"] == 0.0


def test_engine_resets_usage_counters_between_documents():
    """Red-team fix: the engine is a process singleton, so accumulators MUST
    reset per document — otherwise job N's audit-chain cost includes jobs
    1..N-1 (inflated A6 evidence). _reset_usage_counters zeroes them."""
    from app.agents.nodes.translation_engine import TranslationEngine

    eng = TranslationEngine()
    eng._total_input_tokens = 9999
    eng._total_output_tokens = 7777
    eng._reset_usage_counters()
    assert eng._total_input_tokens == 0
    assert eng._total_output_tokens == 0


# ---------------------------------------------------------------------------
# Seam 2 — node emits the event into the chain
# ---------------------------------------------------------------------------


async def test_node_emits_usage_event_into_chain(fresh_engine_for_db, monkeypatch):
    """AC-1/AC-2: translate node leaves exactly one LLM_USAGE_RECORDED event
    carrying the usage payload in the v2 chain."""
    import app.agents.nodes.translation_engine as te
    from app.agents import _audit_v2_emit
    from app.core.tenant_context import org_context

    core_db = fresh_engine_for_db
    job_id = str(uuid.uuid4())
    _seed_org_and_job(core_db, ORG, job_id)

    # The v2 writer singleton caches a session factory closure; reset it so it
    # picks up the freshly-swapped SessionLocal.
    _audit_v2_emit.reset_writer_singleton_for_test()

    usage = _usage(in_tok=1200, out_tok=800)
    monkeypatch.setattr(te, "get_engine", lambda: _FakeEngine(usage))

    state = {
        "doc_id": "doc-1",
        "job_id": job_id,
        "target_language": "es",
        "segments": [{"segment_id": "1", "source_text": "Hello", "order_index": 1}],
        "constraint_pack": {},
    }

    with org_context(ORG):
        result = await te.translation_engine_node(state)
        events = _query_usage_events(core_db, job_id)

    assert "error" not in result
    assert len(events) == 1, "expected exactly one LLM_USAGE_RECORDED event"
    payload = events[0].payload
    assert payload["model"] == "gpt-4-turbo-preview"
    assert payload["input_tokens"] == 1200
    assert payload["output_tokens"] == 800
    assert payload["total_tokens"] == 2000
    assert payload["estimated_cost_usd"] == usage["estimated_cost_usd"]
    assert payload["currency"] == "USD"
    assert payload["_actor_node"] == "translator"
    assert events[0].actor_kind == "agent"


async def test_node_without_job_id_emits_nothing(fresh_engine_for_db, monkeypatch):
    """AC-6: ad-hoc invocation without job_id emits no event and raises nothing."""
    import app.agents.nodes.translation_engine as te
    from app.agents import _audit_v2_emit
    from app.core.tenant_context import org_context

    _ = fresh_engine_for_db  # fixture sets up the DB; no event queried in this case
    _audit_v2_emit.reset_writer_singleton_for_test()
    monkeypatch.setattr(te, "get_engine", lambda: _FakeEngine(_usage()))

    state = {
        "doc_id": "doc-1",
        # no job_id
        "target_language": "es",
        "segments": [{"segment_id": "1", "source_text": "Hello", "order_index": 1}],
        "constraint_pack": {},
    }

    with org_context(ORG):
        result = await te.translation_engine_node(state)

    assert "error" not in result
    # No job_id ⇒ no event possible; nothing raised.


async def test_node_survives_emit_failure(fresh_engine_for_db, monkeypatch):
    """AC-5: if the audit emit raises at the node boundary, the translate node
    still returns successfully and the quality report is intact (A3 metrics
    carve-out — telemetry must never block a translation)."""
    import app.agents.nodes.translation_engine as te
    from app.agents import _audit_v2_emit
    from app.core.tenant_context import org_context

    core_db = fresh_engine_for_db
    job_id = str(uuid.uuid4())
    _seed_org_and_job(core_db, ORG, job_id)
    _audit_v2_emit.reset_writer_singleton_for_test()

    monkeypatch.setattr(te, "get_engine", lambda: _FakeEngine(_usage()))

    def _boom(**kwargs):
        raise RuntimeError("audit writer down")

    monkeypatch.setattr(te, "emit_v2_audit_event", _boom)

    state = {
        "doc_id": "doc-1",
        "job_id": job_id,
        "target_language": "es",
        "segments": [{"segment_id": "1", "source_text": "Hello", "order_index": 1}],
        "constraint_pack": {},
    }

    with org_context(ORG):
        result = await te.translation_engine_node(state)

    assert "error" not in result
    assert result["quality_report"]["status"] == "PASSED"
