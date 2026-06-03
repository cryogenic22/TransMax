"""TMX-BUDGET-1 — per-job token/cost budget with cooperative fail-loud halt.

Seams under test:
  * JobBudget — pure ceiling logic (enabled/disabled, token + cost, boundary).
  * TranslationEngine._maybe_trip_budget — trips the shared flag from the
    A6-2 accumulators.
  * TranslationEngine._process_batch — skips the LLM + BLOCKs segments once
    tripped (spend prevention).
  * translation_engine_node — emits one BUDGET_EXCEEDED v2 audit event from
    the report's budget block.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import text

from app.services.budget_guard import JobBudget

ORG = "00000000-0000-0000-0000-0000000000b1"


# ---------------------------------------------------------------------------
# Seam 1 — pure guard
# ---------------------------------------------------------------------------


def test_disabled_budget_never_trips():
    """AC-1: both limits None ⇒ disabled ⇒ never exceeded."""
    b = JobBudget()
    assert b.is_enabled is False
    assert b.is_exceeded(tokens=10**9, cost_usd=10**6) is False


def test_token_limit_boundary():
    """AC-2: strictly-greater-than trips; exactly-at is within budget."""
    b = JobBudget(max_tokens=1000)
    assert b.is_enabled is True
    assert b.is_exceeded(tokens=1000, cost_usd=0.0) is False
    assert b.is_exceeded(tokens=1001, cost_usd=0.0) is True


def test_cost_limit_trips_independently():
    """AC-3: either dimension independently trips the budget."""
    b = JobBudget(max_cost_usd=0.01)
    assert b.is_exceeded(tokens=0, cost_usd=0.0101) is True
    assert b.is_exceeded(tokens=0, cost_usd=0.01) is False


# ---------------------------------------------------------------------------
# Seam 2 — engine trips the flag
# ---------------------------------------------------------------------------


def test_maybe_trip_budget_sets_flag(monkeypatch):
    """AC-4: accumulated usage over budget sets _budget_exceeded; idempotent."""
    from app.agents.nodes.translation_engine import TranslationEngine

    eng = TranslationEngine()
    eng._reset_usage_counters()
    eng._job_budget = JobBudget(max_tokens=100)
    eng._total_input_tokens = 80
    eng._total_output_tokens = 80  # 160 > 100
    assert eng._budget_exceeded is False
    eng._maybe_trip_budget()
    assert eng._budget_exceeded is True
    eng._maybe_trip_budget()  # idempotent
    assert eng._budget_exceeded is True


def test_maybe_trip_budget_disabled_never_trips():
    """AC-7: default-off budget never trips regardless of usage."""
    from app.agents.nodes.translation_engine import TranslationEngine

    eng = TranslationEngine()
    eng._reset_usage_counters()
    eng._job_budget = JobBudget()  # disabled
    eng._total_input_tokens = 10**9
    eng._maybe_trip_budget()
    assert eng._budget_exceeded is False


# ---------------------------------------------------------------------------
# Seam 3 — process_batch skips LLM + BLOCKs when tripped
# ---------------------------------------------------------------------------


class _FakeProgress:
    """Minimal ProgressTracker stand-in with an async update."""

    def __init__(self):
        self.updates = []

    async def update(self, state, count):
        self.updates.append((state, count))


async def test_process_batch_skips_llm_when_budget_tripped(monkeypatch):
    """AC-5: a batch entered with _budget_exceeded set never calls the LLM and
    marks its segments BLOCKED (spend prevention)."""
    from app.agents.nodes.translation_engine import (
        TranslationEngine,
        SegmentUnit,
        SegmentState,
    )

    eng = TranslationEngine()
    eng._reset_usage_counters()
    eng._budget_exceeded = True

    async def _boom(*a, **k):
        raise AssertionError("LLM must not be called once budget is tripped")

    monkeypatch.setattr(eng, "_call_llm", _boom)

    batch = [SegmentUnit(segment_id="1", source_text="Hi", order_index=1)]
    progress = _FakeProgress()
    await eng._process_batch(
        batch=batch, batch_idx=0, target_language="es",
        constraint_pack={}, progress=progress,
    )

    assert batch[0].state == SegmentState.BLOCKED
    assert batch[0].error_message == "budget_exceeded"
    assert progress.updates  # progress was notified of the block


# ---------------------------------------------------------------------------
# Seam 4 — node emits BUDGET_EXCEEDED into the chain
# ---------------------------------------------------------------------------


def _seed_org_and_job(core_db, org_id: str, job_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    src_id = str(uuid.uuid4())
    with core_db.engine.begin() as conn:
        conn.execute(text(
            "INSERT OR IGNORE INTO organizations "
            "(id, name, slug, org_kind, is_active, created_at, updated_at) "
            "VALUES (:id, :n, :s, 'customer', 1, :ts, :ts)"
        ).bindparams(id=org_id, n="org-b1", s="org-b1", ts=now))
        conn.execute(text(
            "INSERT OR IGNORE INTO translation_jobs "
            "(id, source_document_id, organization_id, source_language, "
            "target_language, provider, is_deleted, created_at) "
            "VALUES (:id, :src, :org, 'en', 'es', 'OPENAI', 0, :ts)"
        ).bindparams(id=job_id, src=src_id, org=org_id, ts=now))


def _query_events(core_db, job_id: str, event_type: str) -> list:
    from app.models.audit_v2 import AuditEventV2
    session = core_db.SessionLocal()
    try:
        return (
            session.query(AuditEventV2)
            .filter(AuditEventV2.job_id == job_id, AuditEventV2.event_type == event_type)
            .all()
        )
    finally:
        session.close()


class _FakeEngineBudget:
    async def translate_document(self, doc_id, segments, target_language, constraint_pack):
        report = {
            "status": "REVIEW_REQUIRED",
            "usage": {
                "model": "gpt-4-turbo-preview", "pricing_model": "gpt-4o-mini",
                "input_tokens": 900, "output_tokens": 200, "total_tokens": 1100,
                "estimated_cost_usd": 0.000255, "currency": "USD",
                "pricing_source": "app.core.model_pricing",
            },
            "budget": {
                "exceeded": True, "limit_tokens": 1000, "limit_cost_usd": None,
                "tokens_used": 1100, "cost_used_usd": 0.000255,
            },
        }
        return ([{**s} for s in segments], report)


async def test_node_emits_budget_exceeded_event(fresh_engine_for_db, monkeypatch):
    """AC-6: when the report flags a budget breach, the node records one
    BUDGET_EXCEEDED v2 audit event for the job."""
    import app.agents.nodes.translation_engine_node as te
    from app.agents import _audit_v2_emit
    from app.core.tenant_context import org_context

    core_db = fresh_engine_for_db
    job_id = str(uuid.uuid4())
    _seed_org_and_job(core_db, ORG, job_id)
    _audit_v2_emit.reset_writer_singleton_for_test()
    monkeypatch.setattr(te, "get_engine", lambda: _FakeEngineBudget())

    state = {
        "doc_id": "doc-1", "job_id": job_id, "target_language": "es",
        "segments": [{"segment_id": "1", "source_text": "Hello", "order_index": 1}],
        "constraint_pack": {},
    }

    with org_context(ORG):
        result = await te.translation_engine_node(state)
        events = _query_events(core_db, job_id, "BUDGET_EXCEEDED")

    assert "error" not in result
    assert len(events) == 1
    payload = events[0].payload
    assert payload["exceeded"] is True
    assert payload["tokens_used"] == 1100
    assert payload["limit_tokens"] == 1000
    assert payload["_actor_node"] == "translator"
