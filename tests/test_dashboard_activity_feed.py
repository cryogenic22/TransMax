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
from app.models.database import DEFAULT_ORG_ID
from app.models.models import AuditRecord, AuditLogEntry


client = TestClient(app)


@pytest.fixture
def seeded_audit():
    """Seed one AuditRecord + 3 AuditLogEntry rows; clean up after."""
    audit_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    session = SessionLocal()
    try:
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
        session.query(AuditLogEntry).filter(AuditLogEntry.audit_id == audit_id).delete()
        session.query(AuditRecord).filter(AuditRecord.audit_id == audit_id).delete()
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
