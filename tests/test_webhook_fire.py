"""
TMX-WEBHOOK-FIRE — the accepted webhook either fires or fails loud (A3 + A1).

Red-test provenance (G2): before the fix, `JobCreateRequest.webhook_url`
(`app/schemas/api_v1.py`) was the ONLY occurrence of webhook_url in `app/` —
accepted, dispatched never, no error returned. Five of the six tests below
fail against that tree; verbatim red output lives in
`.context/loops/TMX-WEBHOOK-FIRE.md` stage 5.

All imports of `app.services.webhook_dispatch` are lazy (inside helpers /
test bodies) so that on the PRE-fix tree the file still collects and each
test goes red on its own behavioural assertion, not on a collection error.
"""

from __future__ import annotations

import json
import uuid
from types import ModuleType
from typing import Callable, Optional

import httpx
import pytest
from fastapi.testclient import TestClient


def _payload(request_id: str, webhook_url: Optional[str] = None) -> dict[str, object]:
    body: dict[str, object] = {
        "request_id": request_id,
        "source_language": "en",
        "target_language": "es",
        "text_content": "Take 10mg daily.",
        "document_name": "webhook-fire-test.txt",
        "profile": {
            "archetype": "INFORMATIONAL",
            "tier": "TIER_C",
            "modality": "NARRATIVE",
        },
    }
    if webhook_url is not None:
        body["webhook_url"] = webhook_url
    return body


def _install_transport(
    monkeypatch: pytest.MonkeyPatch,
    handler: Callable[[httpx.Request], httpx.Response],
) -> None:
    """Route the dispatcher's outbound HTTP through an httpx.MockTransport.

    On the pre-fix tree the dispatch module does not exist; this becomes a
    no-op so the red run fails on the behavioural assertion ("the callback
    never fired"), which is exactly the reported failure mode.
    """
    try:
        import app.services.webhook_dispatch as wd
    except ImportError:
        return
    monkeypatch.setattr(
        wd,
        "_build_client",
        lambda: httpx.Client(transport=httpx.MockTransport(handler)),
    )
    # No real sleeping between retry attempts in tests.
    monkeypatch.setattr(wd, "WEBHOOK_BACKOFF_BASE_SECONDS", 0.0)


def _allow_private_targets(monkeypatch: pytest.MonkeyPatch) -> None:
    """Enable webhook_allow_private_targets so tests may use loopback URLs.

    Pre-fix the flag does not exist — and neither does the validator it
    bypasses, so a loopback URL passes through anyway; swallowing the
    AttributeError keeps the red failure on the real assertion.
    """
    from app.core import config

    try:
        monkeypatch.setattr(config.settings, "webhook_allow_private_targets", True)
    except (AttributeError, ValueError):
        pass


def _fake_terminal_pipeline(core_db: ModuleType) -> Callable[..., None]:
    """Stand-in for run_pipeline_background: flip the doc to TRANSLATED.

    Matches the runner's call shape exactly: positional (doc_id, target_lang),
    kw-only org_id. Keeps the test deterministic and LLM-free.
    """
    from app.core.tenant_context import org_context
    from app.models.database import Document, DocumentStatus

    def fake(
        doc_id: str,
        target_lang: str,
        segment_ids: Optional[list[str]] = None,
        *,
        org_id: str,
    ) -> None:
        with org_context(org_id):
            session = core_db.SessionLocal()
            try:
                doc = session.query(Document).filter(Document.id == doc_id).first()
                assert doc is not None, "pipeline stub: document row missing"
                doc.status = DocumentStatus.TRANSLATED.value
                session.commit()
            finally:
                session.close()

    return fake


def _audit_events(
    core_db: ModuleType, job_id: str
) -> list[tuple[str, dict[str, object]]]:
    """Return (event_type, payload) for every v2 audit event of this job."""
    from app.core.tenant_context import org_context
    from app.models.audit_v2 import AuditEventV2
    from app.models.database import DEFAULT_ORG_ID

    session = core_db.SessionLocal()
    try:
        with org_context(DEFAULT_ORG_ID):
            events = (
                session.query(AuditEventV2)
                .filter(AuditEventV2.job_id == job_id)
                .order_by(AuditEventV2.sequence_index)
                .all()
            )
            return [(e.event_type, dict(e.payload)) for e in events]
    finally:
        session.close()


@pytest.fixture
def api(
    fresh_engine_for_db: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> tuple[TestClient, ModuleType]:
    """TestClient on a fresh DB with the pipeline stubbed to reach TRANSLATED."""
    core_db = fresh_engine_for_db
    from app.agents._audit_v2_emit import reset_writer_singleton_for_test

    reset_writer_singleton_for_test()
    monkeypatch.setattr(
        "app.api.v1.translations.run_pipeline_background",
        _fake_terminal_pipeline(core_db),
    )
    from app.main import app

    return TestClient(app), core_db


def test_webhook_fires_on_terminal_status(
    api: tuple[TestClient, ModuleType], monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-1 + AC-2: the callback fires once, with the real terminal status,
    and the audit chain records ATTEMPTED before / DELIVERED after."""
    client, core_db = api
    _allow_private_targets(monkeypatch)

    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200)

    _install_transport(monkeypatch, handler)

    request_id = f"req-{uuid.uuid4()}"
    resp = client.post(
        "/api/v1/translations/",
        json=_payload(request_id, "http://127.0.0.1:9099/hooks/tmx"),
    )
    assert resp.status_code == 201, resp.text
    job_id = resp.json()["job_id"]

    assert len(captured) == 1, (
        "The integrator callback never fired: webhook_url was accepted but no "
        "outbound POST was made on job completion — the silent failure "
        "TMX-WEBHOOK-FIRE exists to remove."
    )
    req = captured[0]
    assert str(req.url) == "http://127.0.0.1:9099/hooks/tmx"
    body = json.loads(req.content.decode("utf-8"))
    assert body["job_id"] == job_id
    assert body["status"] == "translated", (
        "callback must carry the ACTUAL terminal status read from the DB "
        "(A3: never a substituted value)"
    )
    assert body["request_id"] == request_id
    assert body["timestamp"], "callback must carry a non-empty UTC timestamp"

    event_types = [t for t, _ in _audit_events(core_db, job_id)]
    assert (
        "WEBHOOK_DISPATCH_ATTEMPTED" in event_types
    ), "A1: an audit event must be emitted BEFORE the outbound side effect"
    assert "WEBHOOK_DELIVERED" in event_types, (
        "success must be asserted positively on the chain, not inferred from "
        "the absence of a failure event"
    )
    assert "WEBHOOK_DELIVERY_FAILED" not in event_types


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8000/cb",
        "http://127.0.0.1/cb",
        "http://10.0.0.5/cb",
        "http://172.16.0.1/cb",
        "http://172.31.255.254/cb",
        "http://192.168.1.10/cb",
        "http://169.254.169.254/latest/meta-data",
    ],
)
def test_private_webhook_target_rejected_422(
    api: tuple[TestClient, ModuleType], url: str
) -> None:
    """AC-3: SSRF guard — private/loopback/link-local targets are rejected
    with a 422 while webhook_allow_private_targets is off (the default)."""
    client, _ = api
    resp = client.post(
        "/api/v1/translations/", json=_payload(f"req-{uuid.uuid4()}", url)
    )
    assert resp.status_code == 422, (
        f"private/loopback webhook target {url!r} must be rejected with 422 "
        f"when webhook_allow_private_targets is off (SSRF guard); got "
        f"{resp.status_code}: {resp.text[:200]}"
    )
    assert (
        "webhook" in resp.text.lower()
    ), "the 422 detail must name the webhook so the integrator can act on it"


def test_public_webhook_target_accepted_and_dispatched(
    api: tuple[TestClient, ModuleType], monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-3 (other half): a public host passes validation with the flag off,
    and the dispatch goes through the client seam (no real network in tests)."""
    client, _ = api

    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(204)

    _install_transport(monkeypatch, handler)

    resp = client.post(
        "/api/v1/translations/",
        json=_payload(f"req-{uuid.uuid4()}", "https://hooks.example.com/tmx"),
    )
    assert resp.status_code == 201, resp.text
    assert (
        len(captured) == 1
    ), "public webhook target must be accepted AND dispatched on completion"


def test_delivery_failure_never_fails_the_job(
    api: tuple[TestClient, ModuleType], monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-4: a receiver that 503s every attempt costs the job nothing; the
    failure is loud — 3 attempts, then WEBHOOK_DELIVERY_FAILED on the chain."""
    client, core_db = api
    _allow_private_targets(monkeypatch)

    attempts: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        return httpx.Response(503)

    _install_transport(monkeypatch, handler)

    request_id = f"req-{uuid.uuid4()}"
    resp = client.post(
        "/api/v1/translations/",
        json=_payload(request_id, "http://127.0.0.1:9099/hooks/down"),
    )
    assert resp.status_code == 201, resp.text
    job_id = resp.json()["job_id"]

    # The job's terminal state is untouched by the failed delivery (A3: the
    # webhook is a notification side-channel, not part of the job outcome).
    status_resp = client.get(f"/api/v1/translations/{job_id}")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "translated"

    assert len(attempts) == 3, (
        f"expected 3 delivery attempts (retry w/ backoff) against a failing "
        f"receiver; got {len(attempts)}"
    )

    events = _audit_events(core_db, job_id)
    event_types = [t for t, _ in events]
    assert "WEBHOOK_DISPATCH_ATTEMPTED" in event_types
    assert "WEBHOOK_DELIVERED" not in event_types
    assert "WEBHOOK_DELIVERY_FAILED" in event_types, (
        "exhausted delivery must be recorded loudly on the audit chain "
        "(A3: fail loud, never silently)"
    )
    failed_payload = next(p for t, p in events if t == "WEBHOOK_DELIVERY_FAILED")
    assert failed_payload["attempts"] == 3
    assert failed_payload["last_error"], "the failure record must carry the cause"


def test_no_webhook_url_schedules_no_dispatch(
    api: tuple[TestClient, ModuleType], monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-5: omitting webhook_url keeps today's behaviour byte-identical."""
    client, core_db = api

    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200)

    _install_transport(monkeypatch, handler)

    resp = client.post("/api/v1/translations/", json=_payload(f"req-{uuid.uuid4()}"))
    assert resp.status_code == 201, resp.text
    job_id = resp.json()["job_id"]

    assert captured == [], "no webhook_url ⇒ no outbound POST"
    event_types = [t for t, _ in _audit_events(core_db, job_id)]
    assert not any(t.startswith("WEBHOOK_") for t in event_types)


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("localhost", True),
        ("LocalHost", True),
        ("sub.localhost", True),
        ("127.0.0.1", True),
        ("10.0.0.5", True),
        ("172.15.255.255", False),
        ("172.16.0.0", True),
        ("172.31.255.255", True),
        ("172.32.0.0", False),
        ("192.168.1.10", True),
        ("169.254.169.254", True),
        ("0.0.0.0", True),
        ("::1", True),
        ("[::1]", True),
        ("fe80::1", True),
        ("fd12:3456::1", True),
        ("8.8.8.8", False),
        ("hooks.example.com", False),
    ],
)
def test_private_host_predicate_boundaries(host: str, expected: bool) -> None:
    """Boundary cases for the single-source-of-truth SSRF host predicate."""
    from app.services.webhook_dispatch import is_private_webhook_host

    assert (
        is_private_webhook_host(host) is expected
    ), f"is_private_webhook_host({host!r}) must be {expected}"
