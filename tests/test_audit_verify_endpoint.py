"""
TMX-3105 — HTTP endpoint that exposes the v2 audit verifier.

Tests the route ``GET /api/v1/audit/{job_id}/verify_v2``. Mirrors the
ACs in `.context/loops/TMX-3105.md`:

  AC-1: clean 5-event chain → 200 + ok:true + event_count=5 + ok_count=5.
  AC-2: no events for job → 404 (A3 — loud "no chain" signal).
  AC-3: tampered payload → 200 + ok:false + TAMPERED_PAYLOAD finding.
  AC-4: tampered event_hash → 200 + ok:false + TAMPERED_EVENT_HASH +
        BROKEN_CHAIN cascade on next event.
  AC-5: cross-tenant — event written under org_b is invisible to a
        request that runs under the middleware's DEFAULT_ORG_ID; 404.
  AC-6: response JSON < 100 KB for a clean 50-event chain (sanity).
  AC-7: response_model is in OpenAPI under
        /api/v1/openapi.json or accessible via app.openapi().

Test order (G2): file lands BEFORE the route. Initial pytest run should
record 7 failures (404 because the route doesn't exist yet). Then the
route is added and all 7 turn green.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fresh_app_client(fresh_engine_for_db):
    """A TestClient against `app.main:app` with `app.core.database`
    swapped to a fresh tmp SQLite DB.

    Returns (client, core_db, session) where ``session`` is a SQLAlchemy
    session against the fresh engine (used by tests that need to mutate
    audit rows directly).
    """
    from app.main import app
    core_db = fresh_engine_for_db
    Session = sessionmaker(bind=core_db.engine)
    session = Session()
    client = TestClient(app)
    try:
        yield client, core_db, session
    finally:
        session.close()


def _seed_org(engine, org_id: str) -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT OR IGNORE INTO organizations "
                "(id, name, slug, org_kind, is_active, created_at, updated_at) "
                "VALUES (:id, :name, :slug, 'customer', 1, :ts, :ts)"
            ).bindparams(
                id=org_id, name=f"org-{org_id[:8]}",
                slug=f"org-{org_id[:8]}", ts=now_iso,
            )
        )


def _seed_job(engine, org_id: str) -> str:
    job_id = str(uuid.uuid4())
    src_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO translation_jobs "
                "(id, source_document_id, organization_id, source_language, "
                "target_language, provider, is_deleted, created_at) "
                "VALUES (:id, :src, :org, 'en', 'es', 'OPENAI', 0, :ts)"
            ).bindparams(id=job_id, src=src_id, org=org_id, ts=now_iso)
        )
    return job_id


def _write_chain(core_db, job_id: str, count: int) -> list:
    """Write `count` events using AuditWriterV2 under the current org context."""
    from app.services.audit_writer_v2 import AuditWriterV2
    writer = AuditWriterV2(session_factory=core_db.SessionLocal)
    return [
        writer.record_event(
            job_id=job_id,
            event_type=f"E{i}",
            actor_id=None,
            actor_kind="system",
            payload={"i": i, "msg": f"event-{i}"},
        )
        for i in range(count)
    ]


# ---------------------------------------------------------------------------
# AC-1: clean chain → 200 ok:true
# ---------------------------------------------------------------------------


def test_ac1_clean_chain_returns_200_ok_true(fresh_app_client):
    """5-event clean chain returns 200 with ok:true and event_count=5."""
    client, core_db, _ = fresh_app_client
    from app.core.tenant_context import org_context
    from app.models.database import DEFAULT_ORG_ID

    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    with org_context(DEFAULT_ORG_ID):
        job_id = _seed_job(core_db.engine, DEFAULT_ORG_ID)
        _write_chain(core_db, job_id, 5)

    resp = client.get(f"/api/v1/audit/{job_id}/verify_v2")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["ok"] is True
    assert data["event_count"] == 5
    assert data["ok_count"] == 5
    assert data["findings"] == []
    assert data["job_id"] == job_id
    assert data["organization_id"] == DEFAULT_ORG_ID


# ---------------------------------------------------------------------------
# AC-2: no chain → 404
# ---------------------------------------------------------------------------


def test_ac2_no_events_returns_404(fresh_app_client):
    """A job with zero v2 events returns 404 (A3 — loud, never silent ok:true)."""
    client, core_db, _ = fresh_app_client
    from app.core.tenant_context import org_context
    from app.models.database import DEFAULT_ORG_ID

    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    with org_context(DEFAULT_ORG_ID):
        job_id = _seed_job(core_db.engine, DEFAULT_ORG_ID)
        # Deliberately write NO events.

    resp = client.get(f"/api/v1/audit/{job_id}/verify_v2")
    assert resp.status_code == 404, resp.text
    assert "No v2 audit chain" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# AC-3: tampered payload → 200 ok:false + TAMPERED_PAYLOAD
# ---------------------------------------------------------------------------


def test_ac3_tampered_payload_returns_200_ok_false(fresh_app_client):
    """Mutate event[2].payload directly. Endpoint should return 200 ok:false
    with one TAMPERED_PAYLOAD finding (per TMX-3104 cascade semantics)."""
    import json as _json
    from app.core.tenant_context import org_context
    from app.models.database import DEFAULT_ORG_ID

    client, core_db, _ = fresh_app_client
    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    with org_context(DEFAULT_ORG_ID):
        job_id = _seed_job(core_db.engine, DEFAULT_ORG_ID)
        events = _write_chain(core_db, job_id, 5)

    target_event_id = events[2].event_id
    # Use raw SQL (not ORM) so the mutation bypasses any tenant-scoped
    # ORM behaviours and is unambiguously committed at the DB layer.
    with core_db.engine.begin() as conn:
        conn.execute(
            text("UPDATE audit_events_v2 SET payload = :p WHERE event_id = :id")
            .bindparams(p=_json.dumps({"i": 999, "msg": "TAMPERED"}), id=target_event_id)
        )

    resp = client.get(f"/api/v1/audit/{job_id}/verify_v2")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["ok"] is False
    assert data["event_count"] == 5
    assert data["ok_count"] == 4

    findings = data["findings"]
    assert len(findings) == 1, f"expected exactly 1 finding, got {findings}"
    assert findings[0]["finding"] == "tampered_payload"
    assert findings[0]["sequence_index"] == 2
    assert findings[0]["event_id"] == target_event_id


# ---------------------------------------------------------------------------
# AC-4: tampered event_hash → cascade
# ---------------------------------------------------------------------------


def test_ac4_tampered_event_hash_cascades(fresh_app_client):
    """Mutate event[2].event_hash. Expect TAMPERED_EVENT_HASH on event 2 +
    BROKEN_CHAIN on event 3."""
    from app.core.tenant_context import org_context
    from app.models.database import DEFAULT_ORG_ID

    client, core_db, _ = fresh_app_client
    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    with org_context(DEFAULT_ORG_ID):
        job_id = _seed_job(core_db.engine, DEFAULT_ORG_ID)
        events = _write_chain(core_db, job_id, 5)

    e2_id = events[2].event_id
    e3_id = events[3].event_id
    # Raw SQL UPDATE — unambiguous commit at the DB layer.
    with core_db.engine.begin() as conn:
        conn.execute(
            text("UPDATE audit_events_v2 SET event_hash = :h WHERE event_id = :id")
            .bindparams(h=b"\xff" * 32, id=e2_id)
        )

    resp = client.get(f"/api/v1/audit/{job_id}/verify_v2")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["ok"] is False

    findings_by_event: dict[str, list[str]] = {}
    for f in data["findings"]:
        findings_by_event.setdefault(f["event_id"], []).append(f["finding"])

    assert "tampered_event_hash" in findings_by_event.get(e2_id, []), (
        f"expected TAMPERED_EVENT_HASH on event 2; got {data['findings']}"
    )
    assert "broken_chain" in findings_by_event.get(e3_id, []), (
        f"expected BROKEN_CHAIN on event 3 (cascade); got {data['findings']}"
    )


# ---------------------------------------------------------------------------
# AC-5: cross-tenant isolation → 404
# ---------------------------------------------------------------------------


def test_ac5_cross_tenant_returns_404(fresh_app_client):
    """Write events under org B. Hit the endpoint — middleware sets context
    to DEFAULT_ORG_ID, which CANNOT see org B's events. Expect 404 (NOT 403,
    to avoid leaking existence of org B's job_id)."""
    from app.core.tenant_context import org_context

    client, core_db, _ = fresh_app_client
    org_b = "22222222-2222-2222-2222-222222222222"
    _seed_org(core_db.engine, org_b)

    with org_context(org_b):
        job_b = _seed_job(core_db.engine, org_b)
        _write_chain(core_db, job_b, 3)

    # TestClient hits go through TenantContextMiddleware → context becomes
    # DEFAULT_ORG_ID, which has no row matching (org_id=DEFAULT, job_id=job_b).
    resp = client.get(f"/api/v1/audit/{job_b}/verify_v2")
    assert resp.status_code == 404, (
        f"cross-tenant access leaked: got {resp.status_code} {resp.text}"
    )


# ---------------------------------------------------------------------------
# AC-6: response < 100 KB for a 50-event clean chain
# ---------------------------------------------------------------------------


def test_ac6_response_size_under_100kb_for_clean_chain(fresh_app_client):
    """OK events do NOT appear in findings (only defects do), so a 50-event
    clean chain returns a near-constant-size response. Sanity-check < 100 KB."""
    from app.core.tenant_context import org_context
    from app.models.database import DEFAULT_ORG_ID

    client, core_db, _ = fresh_app_client
    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    with org_context(DEFAULT_ORG_ID):
        job_id = _seed_job(core_db.engine, DEFAULT_ORG_ID)
        _write_chain(core_db, job_id, 50)

    resp = client.get(f"/api/v1/audit/{job_id}/verify_v2")
    assert resp.status_code == 200
    assert len(resp.content) < 100_000, (
        f"response was {len(resp.content)} bytes; expected < 100 KB"
    )
    data = resp.json()
    assert data["ok"] is True
    assert data["event_count"] == 50
    assert data["findings"] == []  # no defects → no findings rows


# ---------------------------------------------------------------------------
# AC-7: OpenAPI exposes the response_model
# ---------------------------------------------------------------------------


def test_ac7_openapi_documents_verify_v2_route(fresh_app_client):
    """The route is in the OpenAPI schema and references the response model."""
    from app.main import app

    schema = app.openapi()
    paths = schema.get("paths", {})
    route_path = "/api/v1/audit/{job_id}/verify_v2"
    assert route_path in paths, (
        f"expected {route_path} in OpenAPI paths; have {sorted(paths.keys())[:20]}"
    )
    get_op = paths[route_path].get("get", {})
    assert get_op, f"no GET op documented at {route_path}"
    # Response 200 should reference a schema (the response_model).
    response_200 = get_op.get("responses", {}).get("200", {})
    content_json = response_200.get("content", {}).get("application/json", {})
    assert content_json.get("schema"), (
        f"no response schema at 200 for {route_path}: {response_200}"
    )
