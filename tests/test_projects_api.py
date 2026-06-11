"""
TMX-PROJECTS-API / TMX-JOBS-FILTER — HTTP contract smoke.

Requests go through TestClient, so TenantContextMiddleware sets DEFAULT_ORG_ID
(projects + project_documents are tenant-scoped). Mirrors the feedback-API test
style. Requires the local dev DB to carry the new tables (rebuild with init_db).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.core.tenant_context import org_context
from app.main import app
from app.models.database import DEFAULT_ORG_ID, Document

client = TestClient(app)


def _seed_document() -> str:
    with org_context(DEFAULT_ORG_ID):
        session = SessionLocal()
        try:
            doc = Document(
                name="api-test.pdf",
                source_language="en",
                target_language="de",
                status="uploaded",
                organization_id=DEFAULT_ORG_ID,
            )
            session.add(doc)
            session.commit()
            return doc.id
        finally:
            session.close()


def test_create_list_and_get_project():
    r = client.post("/api/projects", json={"name": "API Project", "client_name": "X"})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert r.json()["status"] == "active"

    r2 = client.get("/api/projects")
    assert r2.status_code == 200
    assert any(p["id"] == pid for p in r2.json())

    r3 = client.get(f"/api/projects/{pid}")
    assert r3.status_code == 200
    assert r3.json()["name"] == "API Project"


def test_add_and_list_documents_and_filter():
    doc_id = _seed_document()
    pid = client.post("/api/projects", json={"name": "Grouping"}).json()["id"]

    add = client.post(f"/api/projects/{pid}/documents", json={"document_id": doc_id})
    assert add.status_code == 201, add.text

    docs = client.get(f"/api/projects/{pid}/documents")
    assert docs.status_code == 200
    assert any(d["id"] == doc_id for d in docs.json())

    # TMX-JOBS-FILTER: documents list filtered to a project.
    filtered = client.get("/api/documents", params={"project_id": pid})
    assert filtered.status_code == 200
    assert any(d["id"] == doc_id for d in filtered.json()["items"])


def test_metrics_endpoint_shape():
    r = client.get("/api/documents/metrics")
    assert r.status_code == 200
    body = r.json()
    assert "total" in body and "by_status" in body and "by_target_language" in body


def test_get_missing_project_404():
    assert client.get("/api/projects/no-such-id").status_code == 404
