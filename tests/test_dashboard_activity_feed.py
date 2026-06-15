"""
TMX-3603-wire — backend contract tests for `/api/dashboard/activity-feed`
and `/api/dashboard/agent-activity/{audit_id}`.

These tests pin the wire shape consumed by the frontend
`<ActivityFeed>` and `<AgentLanes>` components. If a backend change
drifts the shape, the test fires before any frontend regression lands.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import SessionLocal
from app.core.tenant_context import org_context
from app.models.database import DEFAULT_ORG_ID, Document
from app.models.models import AuditRecord, AuditLogEntry, TranslationJobQueue


client = TestClient(app)


@pytest.fixture
def seeded_audit():
    """Seed one AuditRecord + 3 AuditLogEntry rows; clean up after."""
    audit_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    session = SessionLocal()
    try:
        # AuditRecord.job_id is an enforced FK to translation_jobs_queue on
        # Postgres (SQLite skips FK checks) — seed the parent job first.
        session.add(TranslationJobQueue(
            job_id=job_id,
            organization_id=DEFAULT_ORG_ID,
            request_id=str(uuid.uuid4()),
            source_language="en",
            target_language="de",
            request_json={},
        ))
        session.flush()
        rec = AuditRecord(
            audit_id=audit_id,
            organization_id=DEFAULT_ORG_ID,
            job_id=job_id,
            created_at=now,
        )
        session.add(rec)
        session.flush()
        entries = [
            AuditLogEntry(
                entry_id=str(uuid.uuid4()),
                organization_id=DEFAULT_ORG_ID,
                audit_id=audit_id,
                sequence_index=i,
                event_type=evt,
                payload={"k": "v"},
                entry_hash=f"hash-{i}",
                timestamp=now + timedelta(seconds=i),
            )
            for i, evt in enumerate([
                "JOB_STARTED",
                "TRANSLATION_GENERATED",
                "GATE_CHECK",
            ])
        ]
        for e in entries:
            session.add(e)
        session.commit()
        yield {"audit_id": audit_id, "entry_count": 3}
    finally:
        # Tenant context: the bulk .delete() resolves matching rows via a SELECT
        # against tenant-scoped tables, which Postgres' tenant guard rejects
        # without an org context (SQLite tolerates it).
        with org_context(DEFAULT_ORG_ID):
            session.query(AuditLogEntry).filter(AuditLogEntry.audit_id == audit_id).delete()
            session.query(AuditRecord).filter(AuditRecord.audit_id == audit_id).delete()
            session.query(TranslationJobQueue).filter(TranslationJobQueue.job_id == job_id).delete()
            session.commit()
        session.close()


# ── activity-feed shape ────────────────────────────────────────────────


def test_activity_feed_returns_items_array(seeded_audit):
    res = client.get("/api/dashboard/activity-feed?limit=50")
    assert res.status_code == 200
    body = res.json()
    assert "items" in body
    assert "total" in body
    assert isinstance(body["items"], list)


def test_activity_feed_item_has_wire_shape(seeded_audit):
    res = client.get("/api/dashboard/activity-feed?limit=50")
    items = res.json()["items"]
    assert items, "expected at least one entry from the seeded audit"
    item = items[0]
    # Every key the frontend expects.
    assert set(item.keys()) >= {"id", "actor", "action", "target", "occurredAt"}
    assert set(item["actor"].keys()) >= {"type", "id", "name"}
    assert item["actor"]["type"] in {"agent", "user", "system"}


def test_activity_feed_translator_agent_mapped_correctly(seeded_audit):
    res = client.get("/api/dashboard/activity-feed?limit=50")
    items = res.json()["items"]
    translator_events = [i for i in items if i["actor"]["id"] == "translator"]
    assert translator_events, "TRANSLATION_GENERATED should map to translator agent"
    ev = translator_events[0]
    assert ev["actor"]["type"] == "agent"
    assert ev["actor"]["name"] == "Translator agent"
    assert ev["action"] == "translated"


def test_activity_feed_limit_param_is_clamped():
    # Negative / zero / huge → clamped to [1, 100].
    assert client.get("/api/dashboard/activity-feed?limit=0").status_code == 200
    assert client.get("/api/dashboard/activity-feed?limit=-5").status_code == 200
    assert client.get("/api/dashboard/activity-feed?limit=10000").status_code == 200


# ── agent-activity shape ────────────────────────────────────────────────


def test_agent_activity_returns_activities_array(seeded_audit):
    res = client.get(f"/api/dashboard/agent-activity/{seeded_audit['audit_id']}")
    assert res.status_code == 200
    body = res.json()
    assert "activities" in body
    assert isinstance(body["activities"], list)


def test_agent_activity_only_includes_canonical_four_agents(seeded_audit):
    res = client.get(f"/api/dashboard/agent-activity/{seeded_audit['audit_id']}")
    activities = res.json()["activities"]
    canonical = {"translator", "reviewer", "fixer", "auditor"}
    for a in activities:
        assert a["agent"] in canonical, f"non-canonical agent: {a['agent']!r}"


def test_agent_activity_each_item_has_wire_shape(seeded_audit):
    res = client.get(f"/api/dashboard/agent-activity/{seeded_audit['audit_id']}")
    activities = res.json()["activities"]
    assert activities, "expected translator + reviewer activities"
    for a in activities:
        assert set(a.keys()) >= {"id", "agent", "label", "startedAt", "status"}


def test_agent_activity_unknown_audit_returns_empty():
    res = client.get(f"/api/dashboard/agent-activity/{uuid.uuid4()}")
    assert res.status_code == 200
    assert res.json()["activities"] == []


# ── target resolution: audit_id → document name (TMX-3603-wire-deeper) ──


@pytest.fixture
def seeded_audit_with_doc():
    """Seed: 1 Document + 1 AuditRecord + JOB_STARTED entry referencing it."""
    audit_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())  # must fit VARCHAR(36) — Postgres enforces the length
    now = datetime.now(timezone.utc)
    session = SessionLocal()
    try:
        session.add(TranslationJobQueue(
            job_id=job_id,
            organization_id=DEFAULT_ORG_ID,
            request_id=str(uuid.uuid4()),
            source_language="en",
            target_language="de",
            request_json={},
        ))
        session.flush()
        doc = Document(
            id=doc_id,
            organization_id=DEFAULT_ORG_ID,
            name="Cardivex SmPC v2.1",
            file_type="docx",
            status="translated",
            source_language="en",
            target_language="de",
            created_at=now,
            updated_at=now,
        )
        rec = AuditRecord(
            audit_id=audit_id,
            organization_id=DEFAULT_ORG_ID,
            job_id=job_id,
            created_at=now,
        )
        session.add_all([doc, rec])
        session.flush()
        session.add(AuditLogEntry(
            entry_id=str(uuid.uuid4()),
            organization_id=DEFAULT_ORG_ID,
            audit_id=audit_id,
            sequence_index=0,
            event_type="JOB_STARTED",
            payload={"doc_id": doc_id, "timestamp": now.isoformat()},
            entry_hash="hash-0",
            timestamp=now,
        ))
        session.add(AuditLogEntry(
            entry_id=str(uuid.uuid4()),
            organization_id=DEFAULT_ORG_ID,
            audit_id=audit_id,
            sequence_index=1,
            event_type="TRANSLATION_GENERATED",
            payload={},
            entry_hash="hash-1",
            timestamp=now + timedelta(seconds=1),
        ))
        session.commit()
        yield {"audit_id": audit_id, "doc_id": doc_id, "doc_name": "Cardivex SmPC v2.1"}
    finally:
        with org_context(DEFAULT_ORG_ID):
            session.query(AuditLogEntry).filter(AuditLogEntry.audit_id == audit_id).delete()
            session.query(AuditRecord).filter(AuditRecord.audit_id == audit_id).delete()
            session.query(Document).filter(Document.id == doc_id).delete()
            session.query(TranslationJobQueue).filter(TranslationJobQueue.job_id == job_id).delete()
            session.commit()
        session.close()


def test_activity_feed_resolves_audit_to_doc_name(seeded_audit_with_doc):
    """The TRANSLATION_GENERATED entry should have target = doc name, not 'audit <8>'."""
    res = client.get("/api/dashboard/activity-feed?limit=50")
    items = res.json()["items"]
    translator_events = [
        i for i in items
        if i["actor"]["id"] == "translator"
    ]
    # The seeded TRANSLATION_GENERATED event should now name the doc.
    matching = [
        e for e in translator_events
        if e["target"] == seeded_audit_with_doc["doc_name"]
    ]
    assert matching, (
        f"expected target='{seeded_audit_with_doc['doc_name']}' on translator event; "
        f"got: {[e['target'] for e in translator_events]!r}"
    )


def test_agent_activity_by_job_resolves_to_chain(seeded_audit_with_doc):
    """job_id → audit_id resolution returns the matching agent activities."""
    # The fixture seeds AuditRecord with a deterministic job_id; we re-read
    # it inside the same tenant context as the seed so the TMX-3012
    # session middleware doesn't trip a TenantContextMissing.
    from app.core.tenant_context import org_context
    session = SessionLocal()
    try:
        with org_context(DEFAULT_ORG_ID):
            rec = session.query(AuditRecord).filter(
                AuditRecord.audit_id == seeded_audit_with_doc["audit_id"]
            ).first()
        assert rec is not None
        job_id = rec.job_id
    finally:
        session.close()
    res = client.get(f"/api/dashboard/agent-activity-by-job/{job_id}")
    assert res.status_code == 200
    body = res.json()
    assert "activities" in body
    assert "audit_id" in body
    assert body["audit_id"] == seeded_audit_with_doc["audit_id"]
    canonical = {"translator", "reviewer", "fixer", "auditor"}
    for a in body["activities"]:
        assert a["agent"] in canonical


def test_agent_activity_by_job_unknown_returns_empty():
    res = client.get(f"/api/dashboard/agent-activity-by-job/{uuid.uuid4()}")
    assert res.status_code == 200
    body = res.json()
    assert body["activities"] == []
    assert body["audit_id"] is None


def test_activity_feed_falls_back_to_short_audit_id_when_no_doc(seeded_audit):
    """seeded_audit has NO Document — feed should fall back to 'audit <8-char>'."""
    res = client.get("/api/dashboard/activity-feed?limit=50")
    items = res.json()["items"]
    short_id = seeded_audit["audit_id"][:8]
    matching = [i for i in items if i["target"] == f"audit {short_id}"]
    assert matching, (
        f"expected target='audit {short_id}' fallback on un-doc'd audit chain; "
        f"got: {[i['target'] for i in items]!r}"
    )
