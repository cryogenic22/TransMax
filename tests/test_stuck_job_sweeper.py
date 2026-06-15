"""TMX-ORCH-CHECKPOINT (Loop A) — stuck-PROCESSING sweeper.

Reproduce-the-failure: a doc orphaned in `processing` with no recent activity is
the failure mode; the sweep must recover it to IN_REVIEW with an audit event,
while never touching a fresh `processing` doc, a long-but-alive job (Segments
still being written), or any terminal doc.

The audit emit is captured (records the tenant context at emit time) so the test
proves the per-doc org_context + the JOB_SWEPT_STUCK wiring without needing a
translation_jobs row.
"""

from datetime import datetime, timedelta, timezone

import scripts.stuck_job_sweeper as sweeper


def _bind_db_service(core_db, monkeypatch):
    monkeypatch.setattr(
        "app.services.db_service.SessionLocal", core_db.SessionLocal, raising=True
    )


def _make_org(core_db, slug):
    from app.models.database import Organization

    s = core_db.SessionLocal()
    org = Organization(name=slug, slug=slug, org_kind="customer")
    s.add(org)
    s.commit()
    oid = str(org.id)
    s.close()
    return oid


def _make_doc(core_db, org_id, status, minutes_ago):
    from app.core.tenant_context import org_context
    from app.models.database import Document

    ts = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    s = core_db.SessionLocal()
    with org_context(org_id):
        doc = Document(
            name="x.pdf",
            source_language="en",
            target_language="es",
            status=status,
            organization_id=org_id,
            created_at=ts,
            updated_at=ts,
        )
        s.add(doc)
        s.commit()
        did = doc.id
    s.close()
    return did


def _add_segment(core_db, org_id, doc_id, minutes_ago):
    from app.core.tenant_context import org_context
    from app.models.database import Segment

    ts = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    s = core_db.SessionLocal()
    with org_context(org_id):
        s.add(
            Segment(
                document_id=doc_id,
                organization_id=org_id,
                order_index=0,
                source_text="src",
                translated_text="tgt",
                status="translated",
                created_at=ts,
                updated_at=ts,
            )
        )
        s.commit()
    s.close()


def _status(core_db, doc_id):
    from app.models.database import Document

    s = core_db.SessionLocal()
    try:
        d = (
            s.query(Document)
            .filter(Document.id == doc_id)
            .execution_options(include_other_tenants=True)
            .first()
        )
        return d.status if d else None
    finally:
        s.close()


def _capture_emits(monkeypatch):
    """Capture emit_v2_audit_event calls + the org context active at emit time."""
    calls = []

    def cap(**kw):
        from app.core.tenant_context import current_org_id

        calls.append({**kw, "_org_at_emit": current_org_id()})

    monkeypatch.setattr("app.agents._audit_v2_emit.emit_v2_audit_event", cap)
    return calls


def test_sweeps_stale_processing_doc_to_in_review(fresh_engine_for_db, monkeypatch):
    core_db = fresh_engine_for_db
    _bind_db_service(core_db, monkeypatch)
    calls = _capture_emits(monkeypatch)

    org = _make_org(core_db, "acme-stuck")
    doc = _make_doc(core_db, org, "processing", minutes_ago=40)

    report = sweeper.sweep(timeout_seconds=1200, enabled=True)

    assert report["swept"] == [doc]
    assert _status(core_db, doc) == "in_review"
    assert len(calls) == 1
    c = calls[0]
    assert c["event_type"] == "JOB_SWEPT_STUCK"
    assert c["actor_kind"] == "system"
    assert c["job_id"] == doc
    assert c["payload"]["reason"] == "stuck_processing_timeout"
    assert c["_org_at_emit"] == org  # AC-7: emitted under the doc's own tenant


def test_fresh_segment_protects_long_running_job(fresh_engine_for_db, monkeypatch):
    # A live-but-slow translate: the Document row is frozen at validate-time
    # (40min old) but Segments are still being written (1min ago) — the engine
    # does not heartbeat the Document row, so anchoring on Document.updated_at
    # alone would WRONGLY sweep this live job. Segment activity protects it.
    core_db = fresh_engine_for_db
    _bind_db_service(core_db, monkeypatch)
    calls = _capture_emits(monkeypatch)

    org = _make_org(core_db, "acme-slow")
    doc = _make_doc(core_db, org, "processing", minutes_ago=40)
    _add_segment(core_db, org, doc, minutes_ago=1)

    report = sweeper.sweep(timeout_seconds=1200, enabled=True)

    assert report["candidates"] == 0
    assert _status(core_db, doc) == "processing"
    assert calls == []


def test_genuinely_stuck_doc_with_old_segments_is_swept(
    fresh_engine_for_db, monkeypatch
):
    # Died mid-translate: some Segments were written, then the worker died — all
    # activity (Document + Segments) is older than the timeout, so it IS stuck.
    core_db = fresh_engine_for_db
    _bind_db_service(core_db, monkeypatch)
    _capture_emits(monkeypatch)

    org = _make_org(core_db, "acme-died-mid")
    doc = _make_doc(core_db, org, "processing", minutes_ago=40)
    _add_segment(core_db, org, doc, minutes_ago=35)

    report = sweeper.sweep(timeout_seconds=1200, enabled=True)

    assert report["swept"] == [doc]
    assert _status(core_db, doc) == "in_review"


def test_ignores_fresh_processing_doc(fresh_engine_for_db, monkeypatch):
    core_db = fresh_engine_for_db
    _bind_db_service(core_db, monkeypatch)
    calls = _capture_emits(monkeypatch)

    org = _make_org(core_db, "acme-fresh")
    doc = _make_doc(core_db, org, "processing", minutes_ago=0)

    report = sweeper.sweep(timeout_seconds=1200, enabled=True)

    assert report["candidates"] == 0
    assert _status(core_db, doc) == "processing"  # happy path untouched
    assert calls == []


def test_ignores_terminal_docs(fresh_engine_for_db, monkeypatch):
    core_db = fresh_engine_for_db
    _bind_db_service(core_db, monkeypatch)
    calls = _capture_emits(monkeypatch)

    org = _make_org(core_db, "acme-terminal")
    for st in ("translated", "in_review", "approved"):
        _make_doc(core_db, org, st, minutes_ago=120)

    report = sweeper.sweep(timeout_seconds=1200, enabled=True)

    assert report["candidates"] == 0
    assert calls == []


def test_disabled_finds_but_does_not_mutate(fresh_engine_for_db, monkeypatch):
    # The default-OFF gate lives in sweep(), not just the CLI: a programmatic
    # caller cannot bypass it.
    core_db = fresh_engine_for_db
    _bind_db_service(core_db, monkeypatch)
    calls = _capture_emits(monkeypatch)

    org = _make_org(core_db, "acme-off")
    doc = _make_doc(core_db, org, "processing", minutes_ago=40)

    report = sweeper.sweep(timeout_seconds=1200, enabled=False)

    assert report["candidates"] == 1
    assert report["mutated"] is False
    assert _status(core_db, doc) == "processing"  # found but not touched
    assert calls == []


def test_idempotent_second_run_is_a_noop(fresh_engine_for_db, monkeypatch):
    core_db = fresh_engine_for_db
    _bind_db_service(core_db, monkeypatch)
    calls = _capture_emits(monkeypatch)

    org = _make_org(core_db, "acme-idem")
    _make_doc(core_db, org, "processing", minutes_ago=40)

    first = sweeper.sweep(timeout_seconds=1200, enabled=True)
    second = sweeper.sweep(timeout_seconds=1200, enabled=True)

    assert first["swept_count"] == 1
    assert second["candidates"] == 0
    assert len(calls) == 1  # only the first run emitted


def test_dry_run_writes_nothing(fresh_engine_for_db, monkeypatch):
    core_db = fresh_engine_for_db
    _bind_db_service(core_db, monkeypatch)
    calls = _capture_emits(monkeypatch)

    org = _make_org(core_db, "acme-dry")
    doc = _make_doc(core_db, org, "processing", minutes_ago=40)

    report = sweeper.sweep(timeout_seconds=1200, enabled=True, dry_run=True)

    assert report["candidates"] == 1
    assert _status(core_db, doc) == "processing"  # not mutated
    assert calls == []


def test_one_bad_doc_does_not_abort_the_batch(fresh_engine_for_db, monkeypatch):
    core_db = fresh_engine_for_db
    _bind_db_service(core_db, monkeypatch)
    _capture_emits(monkeypatch)

    org = _make_org(core_db, "acme-isolate")
    bad = _make_doc(core_db, org, "processing", minutes_ago=40)
    good = _make_doc(core_db, org, "processing", minutes_ago=40)

    from app.services.db_service import get_db_service

    db = get_db_service()
    real = db.update_document_status

    def flaky(doc_id, status):
        if doc_id == bad:
            raise RuntimeError("boom")
        return real(doc_id, status)

    monkeypatch.setattr(db, "update_document_status", flaky)

    report = sweeper.sweep(timeout_seconds=1200, enabled=True)

    assert good in report["swept"]
    assert _status(core_db, good) == "in_review"
    assert [e["doc_id"] for e in report["errors"]] == [bad]
    assert (
        _status(core_db, bad) == "processing"
    )  # the failed one is left for the next run
