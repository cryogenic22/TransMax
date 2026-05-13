"""
TMX-3110 Phase 1 — v1 → v2 audit double-write tests.

7 tests covering:
  1. v1 emit unchanged (regression)              — AC-1
  2. v2 emit fires alongside v1                  — AC-2
  3. v2 failure is logged but does NOT break v1  — AC-5
  4. actor_id / actor_kind correctly resolved    — AC-2,3,4
  5. quality_gate site emits agent-actor event   — AC-3
  6. finalize_job site emits agent-actor event   — AC-4
  7. idempotency floor: two runs => 2x v2 events — AC-7

These tests are RED before the v2 emits are added to `app/agents/graph.py`,
GREEN after.

Phase 1 contract: v2 emit lives AFTER v1 emit, wrapped in broad-except.
The wrapper is intentional — Phase 1 is double-write; v2 failure must not
break v1. The wrapper has an explicit EOL (Phase 4 / TMX-3110d).
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fresh_db_with_org(fresh_engine_for_db, monkeypatch):
    """Fresh SQLite engine + active org context wrapping the yield.

    Also keeps `app.models.database.SessionLocal` and `app.services.db_service`'s
    `SessionLocal` import in sync with the fresh engine. This is necessary
    because the `fresh_engine_for_db` fixture only swaps `app.core.database`,
    but the v1 path goes through `DatabaseService.get_session()` which
    captures `SessionLocal` via a chain of `from ... import` re-exports
    that froze at first-import time (which was a PRIOR test's swap). The
    monkeypatch path here updates the downstream bindings to the current
    fresh engine for the duration of this test.
    """
    from app.core.tenant_context import org_context
    from app.models.database import DEFAULT_ORG_ID
    import app.models.database as mdb
    import app.services.db_service as dbs

    core_db = fresh_engine_for_db
    # Re-point downstream SessionLocal bindings to the fresh sessionmaker.
    monkeypatch.setattr(mdb, "SessionLocal", core_db.SessionLocal, raising=True)
    monkeypatch.setattr(mdb, "engine", core_db.engine, raising=True)
    monkeypatch.setattr(dbs, "SessionLocal", core_db.SessionLocal, raising=True)
    monkeypatch.setattr(dbs, "engine", core_db.engine, raising=True)

    # Reset the DatabaseService singleton so it doesn't carry over stale
    # state (e.g. metadata cached from a prior test's engine).
    dbs.DatabaseService._instance = None
    dbs.DatabaseService._initialized = False

    Session = sessionmaker(bind=core_db.engine)
    session = Session()
    with org_context(DEFAULT_ORG_ID):
        yield core_db, session
    session.close()


def _seed_org(engine, org_id: str) -> None:
    """Minimum organizations row so FKs hold."""
    now_iso = datetime.now(timezone.utc).isoformat()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT OR IGNORE INTO organizations "
                "(id, name, slug, org_kind, is_active, created_at, updated_at) "
                "VALUES (:id, :name, :slug, 'customer', 1, :ts, :ts)"
            ).bindparams(
                id=org_id,
                name=f"org-{org_id[:8]}",
                slug=f"org-{org_id[:8]}",
                ts=now_iso,
            )
        )


def _seed_both_job_rows(engine, org_id: str) -> str:
    """Seed BOTH `translation_jobs_queue` (operational; FK target for v1 AuditRecord)
    AND `translation_jobs` (regulatory; FK target for v2 AuditEventV2).

    The graph uses one job_id across both layers — TMX-3017 will rationalise
    them. For Phase 1's tests, we mirror the same id into both tables so
    both FKs are satisfiable.
    """
    job_id = str(uuid.uuid4())
    src_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()
    with engine.begin() as conn:
        # Operational queue (v1 AuditRecord FK target)
        conn.execute(
            text(
                "INSERT INTO translation_jobs_queue "
                "(job_id, organization_id, request_id, status, "
                "source_language, target_language, request_json, "
                "is_deleted, created_at) "
                "VALUES (:job, :org, :req, 'PENDING', 'en', 'es', "
                "'{}', 0, :ts)"
            ).bindparams(
                job=job_id, org=org_id, req=f"req-{job_id[:8]}", ts=now_iso
            )
        )
        # Regulatory (v2 AuditEventV2 FK target)
        conn.execute(
            text(
                "INSERT INTO translation_jobs "
                "(id, source_document_id, organization_id, source_language, "
                "target_language, provider, is_deleted, created_at) "
                "VALUES (:id, :src, :org, 'en', 'es', 'OPENAI', 0, :ts)"
            ).bindparams(id=job_id, src=src_id, org=org_id, ts=now_iso)
        )
    return job_id


def _seed_document(engine, doc_id: str, org_id: str) -> None:
    """Seed a Document row so graph.validate_request's lookup succeeds."""
    now_iso = datetime.now(timezone.utc).isoformat()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO documents (id, organization_id, name, "
                "source_language, status, is_deleted, created_at, "
                "updated_at) "
                "VALUES (:id, :org, 'test.txt', 'en', 'UPLOADED', 0, "
                ":ts, :ts)"
            ).bindparams(id=doc_id, org=org_id, ts=now_iso)
        )


# ---------------------------------------------------------------------------
# Test 1 — v1 emit unchanged (regression)
# ---------------------------------------------------------------------------


def test_v1_emit_creates_audit_record_unchanged(fresh_db_with_org):
    """Calling AuditService.create_audit_trail + log_event creates v1 rows
    EXACTLY as before — this is the regression assertion against Phase 1's
    changes."""
    from app.models.models import AuditLogEntry, AuditRecord
    from app.services.audit_service import AuditService
    from app.models.database import DEFAULT_ORG_ID

    core_db, session = fresh_db_with_org
    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    job_id = _seed_both_job_rows(core_db.engine, DEFAULT_ORG_ID)

    svc = AuditService()
    audit_id = svc.create_audit_trail(job_id)
    svc.log_event(audit_id, "JOB_STARTED", {"doc_id": "doc-x"})

    # AuditRecord exists
    rec = session.query(AuditRecord).filter_by(audit_id=audit_id).one()
    assert rec.job_id == job_id

    # Exactly one v1 log entry exists for this audit_id
    entries = session.query(AuditLogEntry).filter_by(audit_id=audit_id).all()
    assert len(entries) == 1
    assert entries[0].event_type == "JOB_STARTED"
    assert entries[0].sequence_index == 0


# ---------------------------------------------------------------------------
# Test 2 — v2 emit fires alongside v1 (validate_request path)
# ---------------------------------------------------------------------------


def test_validate_request_emits_to_v2_alongside_v1(fresh_db_with_org):
    """Run the graph's validate_request node end-to-end. Assert both v1
    AuditRecord/AuditLogEntry rows AND three v2 AuditEventV2 rows exist
    (AUDIT_TRAIL_INITIALIZED, CONFIG_SNAPSHOT_CAPTURED, JOB_STARTED)."""
    from app.agents import graph as graph_mod
    from app.models.audit_v2 import AuditEventV2
    from app.models.database import DEFAULT_ORG_ID

    core_db, session = fresh_db_with_org
    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    job_id = _seed_both_job_rows(core_db.engine, DEFAULT_ORG_ID)
    doc_id = str(uuid.uuid4())
    _seed_document(core_db.engine, doc_id, DEFAULT_ORG_ID)

    # Reset the writer singleton so it picks up the fresh engine.
    from app.agents import _audit_v2_emit as v2_emit_mod
    v2_emit_mod.reset_writer_singleton_for_test()
    # Also reset other singletons so they don't reference a stale engine.
    graph_mod._db_service = None
    graph_mod._audit_service = None

    state: dict = {
        "doc_id": doc_id,
        "job_id": job_id,
        "target_language": "es",
        "source_language": "en",
        "iteration_count": 0,
        "segments": [],
        "constraint_pack": {},
        "quality_report": {},
        "error": None,
    }

    asyncio.run(graph_mod.validate_request(state))

    # v2 events: 3 events for this job
    events = (
        session.query(AuditEventV2)
        .filter_by(job_id=job_id)
        .order_by(AuditEventV2.sequence_index)
        .all()
    )
    event_types = [e.event_type for e in events]
    assert "AUDIT_TRAIL_INITIALIZED" in event_types
    assert "CONFIG_SNAPSHOT_CAPTURED" in event_types
    assert "JOB_STARTED" in event_types
    assert len(events) == 3

    # Sequence indexes are contiguous starting at 0
    assert [e.sequence_index for e in events] == [0, 1, 2]

    # Chain linkage: each event's previous_hash == prior event_hash
    assert events[0].previous_hash == b"\x00" * 32
    for prior, cur in zip(events, events[1:]):
        assert cur.previous_hash == prior.event_hash


# ---------------------------------------------------------------------------
# Test 3 — v2 failure logged but does NOT break v1
# ---------------------------------------------------------------------------


def test_v2_failure_does_not_break_v1(fresh_db_with_org, monkeypatch, caplog):
    """Monkeypatch the v2 writer to raise. Assert v1 still succeeded
    (AuditRecord + AuditLogEntry rows exist) AND a WARNING was logged with
    the event_type + job_id."""
    from app.agents import graph as graph_mod
    from app.models.audit_v2 import AuditEventV2
    from app.models.models import AuditLogEntry, AuditRecord
    from app.models.database import DEFAULT_ORG_ID

    core_db, session = fresh_db_with_org
    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    job_id = _seed_both_job_rows(core_db.engine, DEFAULT_ORG_ID)
    doc_id = str(uuid.uuid4())
    _seed_document(core_db.engine, doc_id, DEFAULT_ORG_ID)

    from app.agents import _audit_v2_emit as v2_emit_mod
    v2_emit_mod.reset_writer_singleton_for_test()
    graph_mod._db_service = None
    graph_mod._audit_service = None

    # Force the writer to explode on every call.
    class _BoomWriter:
        def record_event(self, **kwargs):
            raise RuntimeError("v2 simulated failure")

    monkeypatch.setattr(v2_emit_mod, "_get_audit_writer_v2", lambda: _BoomWriter())

    state: dict = {
        "doc_id": doc_id,
        "job_id": job_id,
        "target_language": "es",
        "source_language": "en",
        "iteration_count": 0,
        "segments": [],
        "constraint_pack": {},
        "quality_report": {},
        "error": None,
    }

    with caplog.at_level(logging.WARNING, logger="app.agents._audit_v2_emit"):
        asyncio.run(graph_mod.validate_request(state))

    # v1 chain is intact
    rec = session.query(AuditRecord).filter_by(job_id=job_id).one()
    v1_entries = session.query(AuditLogEntry).filter_by(audit_id=rec.audit_id).all()
    assert len(v1_entries) == 1  # JOB_STARTED
    assert v1_entries[0].event_type == "JOB_STARTED"

    # v2 chain is empty for this job (writer raised every time)
    v2_count = session.query(AuditEventV2).filter_by(job_id=job_id).count()
    assert v2_count == 0

    # WARNING logged with structured context
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("v2 audit emit failed" in r.getMessage() for r in warnings), (
        f"Expected 'v2 audit emit failed' WARNING; got: {[r.getMessage() for r in warnings]}"
    )
    # At least one warning must reference the job_id (so SREs can find the gap)
    assert any(job_id in r.getMessage() for r in warnings), (
        f"Expected job_id={job_id} in a warning; got: {[r.getMessage() for r in warnings]}"
    )


# ---------------------------------------------------------------------------
# Test 4 — actor_id/actor_kind for validate_request site is system/None
# ---------------------------------------------------------------------------


def test_validate_request_v2_events_have_system_actor(fresh_db_with_org):
    """All 3 v2 events emitted from validate_request use actor_kind='system'
    and actor_id=None (the pipeline boot is system-initiated, no human, no
    specific agent)."""
    from app.agents import graph as graph_mod
    from app.models.audit_v2 import AuditEventV2
    from app.models.database import DEFAULT_ORG_ID

    core_db, session = fresh_db_with_org
    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    job_id = _seed_both_job_rows(core_db.engine, DEFAULT_ORG_ID)
    doc_id = str(uuid.uuid4())
    _seed_document(core_db.engine, doc_id, DEFAULT_ORG_ID)

    from app.agents import _audit_v2_emit as v2_emit_mod
    v2_emit_mod.reset_writer_singleton_for_test()
    graph_mod._db_service = None
    graph_mod._audit_service = None

    state: dict = {
        "doc_id": doc_id,
        "job_id": job_id,
        "target_language": "es",
        "source_language": "en",
        "iteration_count": 0,
        "segments": [],
        "constraint_pack": {},
        "quality_report": {},
        "error": None,
    }
    asyncio.run(graph_mod.validate_request(state))

    events = session.query(AuditEventV2).filter_by(job_id=job_id).all()
    assert events, "expected v2 events from validate_request"
    for ev in events:
        assert ev.actor_kind == "system", (
            f"event {ev.event_type}: expected actor_kind='system', got {ev.actor_kind!r}"
        )
        assert ev.actor_id is None, (
            f"event {ev.event_type}: expected actor_id=None, got {ev.actor_id!r}"
        )

    # AUDIT_TRAIL_INITIALIZED payload preserves the v1 audit_id for x-ref.
    init_ev = next(e for e in events if e.event_type == "AUDIT_TRAIL_INITIALIZED")
    assert "audit_id_v1" in init_ev.payload, (
        f"AUDIT_TRAIL_INITIALIZED payload must carry the v1 audit_id for "
        f"cross-referencing; got payload={init_ev.payload!r}"
    )


# ---------------------------------------------------------------------------
# Test 5 — quality_gate site emits agent-actor SCORECARD_GENERATED to v2
# ---------------------------------------------------------------------------


def test_quality_gate_emit_uses_agent_actor(fresh_db_with_org):
    """Directly exercise the quality_gate v1+v2 emit pair (without running
    the full LLM pipeline). The simplest reproduction is to call the v2
    emit shim the same way the production node does.

    Note: actor_id stays None because v2 schema types actor_id as GUID
    (FK target) — node-name "quality_gate" isn't a UUID. The node name
    is preserved in payload['_actor_node']. See TMX-3110-actor-id-schema
    spawn for the long-term fix."""
    from app.agents import graph as graph_mod
    from app.models.audit_v2 import AuditEventV2
    from app.models.database import DEFAULT_ORG_ID

    core_db, session = fresh_db_with_org
    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    job_id = _seed_both_job_rows(core_db.engine, DEFAULT_ORG_ID)

    from app.agents import _audit_v2_emit as v2_emit_mod
    v2_emit_mod.reset_writer_singleton_for_test()

    # The production code uses a single private helper to dispatch the v2
    # emit. We exercise it via the same path the quality_gate node uses.
    graph_mod._emit_v2_audit_event(
        job_id=job_id,
        event_type="SCORECARD_GENERATED",
        actor_id=None,
        actor_kind="agent",
        payload={
            "status": "PASS",
            "metrics": {"score": 100},
            "_actor_node": "quality_gate",
        },
    )

    ev = (
        session.query(AuditEventV2)
        .filter_by(job_id=job_id, event_type="SCORECARD_GENERATED")
        .one()
    )
    assert ev.actor_kind == "agent"
    assert ev.actor_id is None
    assert ev.payload["_actor_node"] == "quality_gate"
    assert ev.payload["status"] == "PASS"


# ---------------------------------------------------------------------------
# Test 6 — finalize_job emit uses agent-actor "finalizer"
# ---------------------------------------------------------------------------


def test_finalize_job_emit_uses_agent_actor(fresh_db_with_org):
    """Same shape as test 5 but for the finalize_job site."""
    from app.agents import graph as graph_mod
    from app.models.audit_v2 import AuditEventV2
    from app.models.database import DEFAULT_ORG_ID

    core_db, session = fresh_db_with_org
    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    job_id = _seed_both_job_rows(core_db.engine, DEFAULT_ORG_ID)

    from app.agents import _audit_v2_emit as v2_emit_mod
    v2_emit_mod.reset_writer_singleton_for_test()

    graph_mod._emit_v2_audit_event(
        job_id=job_id,
        event_type="JOB_FINALIZED",
        actor_id=None,
        actor_kind="agent",
        payload={
            "final_status": "TRANSLATED",
            "decision": "PASS",
            "_actor_node": "finalizer",
        },
    )

    ev = (
        session.query(AuditEventV2)
        .filter_by(job_id=job_id, event_type="JOB_FINALIZED")
        .one()
    )
    assert ev.actor_kind == "agent"
    assert ev.actor_id is None
    assert ev.payload["_actor_node"] == "finalizer"
    assert ev.payload["final_status"] == "TRANSLATED"


# ---------------------------------------------------------------------------
# Test 7 — idempotency floor: two runs => 2x v2 events (append-only)
# ---------------------------------------------------------------------------


def test_idempotency_floor_no_dedup_at_v2_emit(fresh_db_with_org):
    """v2 writer is append-only: calling the shim twice with the same
    payload yields two events with different sequence_indexes. No dedup
    at the writer level — Phase 1's emit shim does not magically de-dupe.

    (Note: end-to-end idempotency of the graph itself is a different
    concern — `capture_config_snapshot` has a UNIQUE(job_id) constraint,
    so calling validate_request twice raises in v1's path. Phase 1 does
    NOT change that. This test pins the writer-level append-only floor
    that v2 relies on; the verifier sees two distinct events, both well-
    formed.)"""
    from app.agents import graph as graph_mod
    from app.models.audit_v2 import AuditEventV2
    from app.models.database import DEFAULT_ORG_ID

    core_db, session = fresh_db_with_org
    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    job_id = _seed_both_job_rows(core_db.engine, DEFAULT_ORG_ID)

    from app.agents import _audit_v2_emit as v2_emit_mod
    v2_emit_mod.reset_writer_singleton_for_test()

    payload = {"doc_id": "doc-x", "timestamp": "2026-05-11T00:00:00+00:00"}
    graph_mod._emit_v2_audit_event(
        job_id=job_id,
        event_type="JOB_STARTED",
        actor_id=None,
        actor_kind="system",
        payload=payload,
    )
    graph_mod._emit_v2_audit_event(
        job_id=job_id,
        event_type="JOB_STARTED",
        actor_id=None,
        actor_kind="system",
        payload=payload,
    )

    events = (
        session.query(AuditEventV2)
        .filter_by(job_id=job_id, event_type="JOB_STARTED")
        .order_by(AuditEventV2.sequence_index)
        .all()
    )
    assert [e.sequence_index for e in events] == [0, 1]
    assert events[0].event_id != events[1].event_id
    # Chain linkage: second's previous_hash equals first's event_hash
    assert events[1].previous_hash == events[0].event_hash
