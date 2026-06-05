"""TMX-FEEDBACK-1 — backend contract tests for the in-app feedback API.

Covers AC-1..AC-7 of `.context/loops/TMX-FEEDBACK-1.md`. All requests go
through `TestClient`, so the TenantContextMiddleware sets DEFAULT_ORG_ID
for each call (the feedback table is tenant-scoped).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.core.database import SessionLocal
from app.core.tenant_context import org_context
from app.models.database import DEFAULT_ORG_ID, Feedback

client = TestClient(app)


def _create(category="bug", title="Login button does nothing", priority="high", **kw):
    body = {"category": category, "title": title, "priority": priority}
    body.update(kw)
    return client.post("/api/feedback", json=body)


# --- AC-1: create ---------------------------------------------------------


def test_create_returns_new_row():
    r = _create(description="Click login, nothing happens", page_url="/login")
    assert r.status_code == 200, r.text
    fb = r.json()["feedback"]
    assert fb["id"]
    assert fb["category"] == "bug"
    assert fb["title"] == "Login button does nothing"
    assert fb["status"] == "new"
    assert fb["priority"] == "high"
    assert fb["created_at"]


def test_create_scopes_to_default_org():
    r = _create(title="org-scope check")
    fb_id = r.json()["feedback"]["id"]
    with org_context(DEFAULT_ORG_ID):
        session = SessionLocal()
        try:
            row = session.query(Feedback).filter(Feedback.id == fb_id).first()
            assert row is not None
            assert row.organization_id == DEFAULT_ORG_ID
        finally:
            session.close()


# --- AC-2: validation (fail loud, A3) -------------------------------------


def test_invalid_category_400():
    r = _create(category="nonsense")
    assert r.status_code == 400
    assert "Invalid category" in r.text


def test_invalid_priority_400():
    r = _create(priority="urgent")
    assert r.status_code == 400
    assert "Invalid priority" in r.text


# --- AC-3: list -----------------------------------------------------------


def test_list_filters_and_shape():
    _create(category="bug", title="list-bug-1")
    _create(category="feature", title="list-feature-1")

    r = client.get(
        "/api/feedback", params={"status": "new", "category": "bug", "limit": 50}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body.keys()) == {"items", "total", "limit", "offset"}
    assert all(
        it["category"] == "bug" and it["status"] == "new" for it in body["items"]
    )
    titles = [it["title"] for it in body["items"]]
    assert "list-bug-1" in titles
    assert "list-feature-1" not in titles


def test_list_invalid_status_400():
    r = client.get("/api/feedback", params={"status": "bogus"})
    assert r.status_code == 400


# --- AC-4: patch ----------------------------------------------------------


def test_patch_transitions_status():
    fb_id = _create(title="patch-me").json()["feedback"]["id"]
    r = client.patch(f"/api/feedback/{fb_id}", json={"status": "triaged"})
    assert r.status_code == 200, r.text
    assert r.json()["feedback"]["status"] == "triaged"

    r2 = client.patch(
        f"/api/feedback/{fb_id}",
        json={
            "status": "resolved",
            "resolved_by": "claude",
            "resolution": "fixed in abc123",
        },
    )
    assert r2.status_code == 200
    assert r2.json()["feedback"]["resolved_by"] == "claude"


def test_patch_invalid_status_400():
    fb_id = _create(title="patch-bad").json()["feedback"]["id"]
    r = client.patch(f"/api/feedback/{fb_id}", json={"status": "shipped"})
    assert r.status_code == 400


def test_patch_unknown_id_404():
    r = client.patch("/api/feedback/does-not-exist", json={"status": "triaged"})
    assert r.status_code == 404


# --- AC-5: soft-delete (A9) ----------------------------------------------


def test_delete_soft_deletes_and_hides_row():
    fb_id = _create(title="delete-me").json()["feedback"]["id"]
    r = client.delete(f"/api/feedback/{fb_id}")
    assert r.status_code == 204

    # No longer visible via the API (soft-delete auto-filter)
    listed = client.get("/api/feedback", params={"limit": 100}).json()["items"]
    assert fb_id not in [it["id"] for it in listed]

    # But the row still exists in the DB with is_deleted=True (A9 — not hard-deleted)
    with org_context(DEFAULT_ORG_ID):
        session = SessionLocal()
        try:
            row = (
                session.query(Feedback)
                .execution_options(include_deleted=True)
                .filter(Feedback.id == fb_id)
                .first()
            )
            assert row is not None, "row was hard-deleted — A9 violation"
            assert row.is_deleted is True
        finally:
            session.close()

    # A second delete sees the row as already gone (auto-filtered) -> 404
    assert client.delete(f"/api/feedback/{fb_id}").status_code == 404


# --- AC-7: stats ----------------------------------------------------------


def test_stats_shape():
    _create(category="bug", title="stats-bug")
    r = client.get("/api/feedback/stats")
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body.keys()) == {"total", "by_category", "by_status"}
    assert body["total"] >= 1
    assert "bug" in body["by_category"]
