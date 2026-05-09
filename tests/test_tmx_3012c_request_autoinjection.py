"""
TMX-3012c — end-to-end auto-injection through the API request layer.

These tests prove that with the explicit `organization_id=DEFAULT_ORG_ID`
literals removed from request handlers, the resulting DB rows still carry
`organization_id == DEFAULT_ORG_ID` — sourced from the
`TenantContextMiddleware` → `TenantScopedMixin.before_insert` listener path,
NOT from a hard-coded literal in handler code.

Failure mode this test prevents: someone re-introduces a literal as part
of a refactor, and the row is double-tenanted (handler literal wins over
mixin context). Or: someone removes the middleware and every API write
silently writes to org "00…01" via a forgotten literal somewhere upstream.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def app_with_fresh_db(fresh_engine_for_db):
    """Spin up the FastAPI app against a freshly-initialised SQLite DB.

    The TenantContextMiddleware is mounted at app construction time, so it
    runs for every request through TestClient, exactly as in production.
    """
    core_db = fresh_engine_for_db
    from app.main import app

    # The default get_db dependency reads SessionLocal at call time —
    # conftest's in-place swap means each request gets the test session.
    Session = sessionmaker(bind=core_db.engine)
    return app, core_db, Session


def test_create_translation_job_autoinjects_default_org(app_with_fresh_db):
    """POST /api/v1/translations/ with no organization_id → row carries
    DEFAULT_ORG_ID via middleware → mixin auto-inject."""
    app, core_db, Session = app_with_fresh_db
    from app.core.tenant_context import org_context
    from app.models.database import DEFAULT_ORG_ID, Document

    client = TestClient(app)
    request_id = f"req-{uuid.uuid4()}"
    payload = {
        "request_id": request_id,
        "source_language": "en",
        "target_language": "es",
        "text_content": "Hello world.",
        "document_name": "tmx-3012c-test.txt",
        "profile": {
            "archetype": "INFORMATIONAL",
            "tier": "TIER_C",
            "modality": "NARRATIVE",
        },
    }

    resp = client.post("/api/v1/translations/", json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    job_id = body["job_id"]

    # Read back the document directly. Wrap in org_context so the auto-filter
    # lets the SELECT through.
    s = Session()
    try:
        with org_context(DEFAULT_ORG_ID):
            doc = s.query(Document).filter(Document.id == job_id).one()
            assert doc.organization_id == DEFAULT_ORG_ID, (
                "Document was created without an explicit organization_id "
                "argument — the row's organization_id should have been set "
                "by the TenantContextMiddleware via the mixin's before_insert "
                "listener. If this fails, either the middleware no longer "
                "wraps the request OR the mixin no longer auto-injects."
            )
    finally:
        s.close()


def test_request_handler_does_not_pass_explicit_org_id(app_with_fresh_db, monkeypatch):
    """Verify that handler code does NOT pass `organization_id` to model
    constructors — the middleware/mixin path is the only writer.

    We patch the Document __init__ to capture kwargs and assert the
    handler did not include `organization_id`.
    """
    app, core_db, Session = app_with_fresh_db
    from app.models.database import Document

    captured_kwargs = {}
    original_init = Document.__init__

    def spy_init(self, *args, **kwargs):
        # Only record the FIRST construction (the API handler's own call).
        # Subsequent inserts (mixin's before_insert sets organization_id at
        # flush time, AFTER __init__) don't go through __init__ again.
        if "first_call" not in captured_kwargs:
            captured_kwargs["first_call"] = dict(kwargs)
        return original_init(self, *args, **kwargs)

    monkeypatch.setattr(Document, "__init__", spy_init)

    client = TestClient(app)
    payload = {
        "request_id": f"req-{uuid.uuid4()}",
        "source_language": "en",
        "target_language": "es",
        "text_content": "ping.",
        "document_name": "spy.txt",
        "profile": {
            "archetype": "INFORMATIONAL",
            "tier": "TIER_C",
            "modality": "NARRATIVE",
        },
    }

    resp = client.post("/api/v1/translations/", json=payload)
    assert resp.status_code == 201, resp.text

    assert "first_call" in captured_kwargs, "Document was never constructed"
    assert "organization_id" not in captured_kwargs["first_call"], (
        f"Handler passed organization_id explicitly: "
        f"{captured_kwargs['first_call'].get('organization_id')!r}. "
        f"TMX-3012c removed every such literal — re-introducing one is a "
        f"regression of the A3 invariant (tenancy must come from context, "
        f"not from a hardcoded fallback)."
    )
