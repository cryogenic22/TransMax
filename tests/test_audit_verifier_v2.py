"""
TMX-3104 — Audit Ledger v2 independent re-compute verifier tests.

10 tests + boundary tests covering:
  1. Spec-binding — verifier's recompute_event_hash matches the writer's
     hardcoded hex digest for the canonical fixed input.
  2. Clean single event — writer writes one event; verifier reports OK.
  3. Clean 5-event chain — all events OK.
  4. Cross-tenant isolation — org B's verifier sees zero of org A's events.
  5. Tampered payload — TAMPERED_PAYLOAD on mutated event; chain still walkable.
  6. Tampered event_hash — TAMPERED_EVENT_HASH on event N + BROKEN_CHAIN on N+1.
  7. Broken previous_hash — TAMPERED_EVENT_HASH + BROKEN_CHAIN on mutated event.
  8. Sequence gap — SEQUENCE_GAP on the event after the deletion.
  9. Genesis violation — raw INSERT seq=0 with non-zero prev_hash flags it.
 10. Two-implementation agreement — writer.compute_X == verifier.recompute_X
     for the same input. The byte-for-byte agreement IS the verification.

Tests are RED before `app/services/audit_verifier_v2.py` exists; GREEN after.

The cascade semantics for tests #5/#6/#7 are documented in TMX-3104 worksheet
stage 3 — they were thought-through before implementation.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker


# ---------------------------------------------------------------------------
# Fixtures (mirror tests/test_audit_writer_v2.py for consistency)
# ---------------------------------------------------------------------------


@pytest.fixture
def fresh_db(fresh_engine_for_db):
    """Fresh SQLite + an active org context wrapping the yield."""
    core_db = fresh_engine_for_db
    from app.core.tenant_context import org_context
    from app.models.database import DEFAULT_ORG_ID

    Session = sessionmaker(bind=core_db.engine)
    session = Session()
    with org_context(DEFAULT_ORG_ID):
        yield core_db, session
    session.close()


def _seed_org(engine, org_id: str) -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT OR IGNORE INTO organizations "
                "(id, name, slug, org_kind, is_active, created_at, updated_at) "
                "VALUES (:id, :name, :slug, 'customer', 1, :ts, :ts)"
            ).bindparams(id=org_id, name=f"org-{org_id[:8]}", slug=f"org-{org_id[:8]}", ts=now_iso)
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


def _make_writer(core_db):
    from app.services.audit_writer_v2 import AuditWriterV2
    return AuditWriterV2(session_factory=core_db.SessionLocal)


def _make_verifier(core_db):
    from app.services.audit_verifier_v2 import AuditVerifierV2
    return AuditVerifierV2(session_factory=core_db.SessionLocal)


def _write_chain(writer, job_id: str, count: int) -> list:
    """Write a chain of `count` events under the current org context."""
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
# Test 1 — Spec-binding fixture (load-bearing)
# ---------------------------------------------------------------------------


def test_spec_binding_verifier_recompute_matches_writer_hardcoded_hex():
    """The verifier's recompute_event_hash, run on the canonical fixed input
    (seq=0, prev=zeros, payload={"foo":"bar"}), produces the SAME hardcoded
    hex digest pinned in tests/test_audit_writer_v2.py.

    This test is the load-bearing spec-binding check: if EITHER the writer
    or the verifier drifts from the spec, this fails.
    """
    from app.services.audit_verifier_v2 import AuditVerifierV2
    from tests.test_audit_writer_v2 import SPEC_EXPECTED_HEX_FOR_FOO_BAR

    payload = {"foo": "bar"}
    payload_hash = AuditVerifierV2.recompute_payload_hash(payload)
    event_hash = AuditVerifierV2.recompute_event_hash(0, b"\x00" * 32, payload_hash)

    assert event_hash.hex() == SPEC_EXPECTED_HEX_FOR_FOO_BAR
    assert len(event_hash) == 32


# ---------------------------------------------------------------------------
# Test 2 — Clean single event
# ---------------------------------------------------------------------------


def test_clean_single_event_reports_ok(fresh_db):
    """One event written by the writer; verifier reports is_valid=True, no findings."""
    core_db, _ = fresh_db
    from app.models.database import DEFAULT_ORG_ID

    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    job_id = _seed_job(core_db.engine, DEFAULT_ORG_ID)
    writer = _make_writer(core_db)
    verifier = _make_verifier(core_db)

    writer.record_event(
        job_id=job_id, event_type="GENESIS", actor_id=None,
        actor_kind="system", payload={"k": "v"},
    )

    report = verifier.verify_job_chain(job_id)
    assert report.is_valid, f"expected valid, got findings: {report.findings}"
    assert report.event_count == 1
    assert report.ok_count == 1
    assert report.findings == []


# ---------------------------------------------------------------------------
# Test 3 — Clean 5-event chain
# ---------------------------------------------------------------------------


def test_clean_five_event_chain_reports_all_ok(fresh_db):
    """5-event chain via writer; verifier reports is_valid=True."""
    core_db, _ = fresh_db
    from app.models.database import DEFAULT_ORG_ID

    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    job_id = _seed_job(core_db.engine, DEFAULT_ORG_ID)
    writer = _make_writer(core_db)
    verifier = _make_verifier(core_db)

    _write_chain(writer, job_id, 5)

    report = verifier.verify_job_chain(job_id)
    assert report.is_valid, f"findings: {report.findings}"
    assert report.event_count == 5
    assert report.ok_count == 5
    assert report.findings == []


# ---------------------------------------------------------------------------
# Test 4 — Cross-tenant isolation
# ---------------------------------------------------------------------------


def test_cross_tenant_isolation_org_b_sees_no_events(fresh_engine_for_db):
    """Events written under org A are invisible to a verifier running under org B."""
    from app.core.tenant_context import org_context
    from app.services.audit_verifier_v2 import AuditVerifierV2

    core_db = fresh_engine_for_db
    org_a = "11111111-1111-1111-1111-111111111111"
    org_b = "22222222-2222-2222-2222-222222222222"
    _seed_org(core_db.engine, org_a)
    _seed_org(core_db.engine, org_b)

    writer = _make_writer(core_db)
    verifier = AuditVerifierV2(session_factory=core_db.SessionLocal)

    with org_context(org_a):
        job_a = _seed_job(core_db.engine, org_a)
        writer.record_event(
            job_id=job_a, event_type="A_EVENT", actor_id=None,
            actor_kind="system", payload={"src": "A"},
        )

    with org_context(org_b):
        reports = verifier.verify_org_chain()
        assert reports == [], f"org B saw org A's events: {reports}"


# ---------------------------------------------------------------------------
# Test 5 — Tampered payload (most common attack)
# ---------------------------------------------------------------------------


def test_tampered_payload_surfaces_finding(fresh_db):
    """Write 5 events. Mutate event[2].payload via direct UPDATE.

    Expected cascade (documented in worksheet stage 3):
      - TAMPERED_PAYLOAD on event 2 (stored payload_hash no longer matches
        SHA256(canonical_json(stored payload))).
      - NO TAMPERED_EVENT_HASH: event_hash was computed from the ORIGINAL
        payload_hash, which is still stored. Recompute uses stored payload_hash
        not recomputed-from-payload payload_hash.
      - NO BROKEN_CHAIN: event 3's stored prev_hash still matches event 2's
        stored event_hash (neither hash column was touched).

    So only one finding: TAMPERED_PAYLOAD on event 2.
    """
    from app.models.audit_v2 import AuditEventV2
    from app.services.audit_verifier_v2 import EventFinding

    core_db, session = fresh_db
    from app.models.database import DEFAULT_ORG_ID

    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    job_id = _seed_job(core_db.engine, DEFAULT_ORG_ID)
    writer = _make_writer(core_db)
    verifier = _make_verifier(core_db)

    events = _write_chain(writer, job_id, 5)
    target_event_id = events[2].event_id

    # Mutate event 2's payload directly. SQLAlchemy session.update.
    session.query(AuditEventV2).filter_by(event_id=target_event_id).update(
        {AuditEventV2.payload: {"i": 999, "msg": "TAMPERED"}}
    )
    session.commit()
    session.expire_all()

    report = verifier.verify_job_chain(job_id)
    assert not report.is_valid
    assert report.event_count == 5
    assert report.ok_count == 4

    findings_by_event = {f.event_id: f for f in report.findings}
    assert target_event_id in findings_by_event, (
        f"expected finding on event[2] (id={target_event_id}); got {report.findings}"
    )
    assert findings_by_event[target_event_id].finding == EventFinding.TAMPERED_PAYLOAD
    assert findings_by_event[target_event_id].sequence_index == 2

    # All other events still OK — only one finding total.
    assert len(report.findings) == 1, (
        f"expected exactly 1 finding (TAMPERED_PAYLOAD on event 2); got {report.findings}"
    )


# ---------------------------------------------------------------------------
# Test 6 — Tampered event_hash (cascades to next event's BROKEN_CHAIN)
# ---------------------------------------------------------------------------


def test_tampered_event_hash_cascades_to_next_event(fresh_db):
    """Mutate event 2's event_hash column. Expected:
      - TAMPERED_EVENT_HASH on event 2 (recomputed != stored).
      - BROKEN_CHAIN on event 3 (event 3's stored prev_hash != event 2's
        NEW stored event_hash).
    """
    from app.models.audit_v2 import AuditEventV2
    from app.services.audit_verifier_v2 import EventFinding

    core_db, session = fresh_db
    from app.models.database import DEFAULT_ORG_ID

    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    job_id = _seed_job(core_db.engine, DEFAULT_ORG_ID)
    writer = _make_writer(core_db)
    verifier = _make_verifier(core_db)

    events = _write_chain(writer, job_id, 5)
    e2_id = events[2].event_id
    e3_id = events[3].event_id

    # Mutate event 2's event_hash to a different valid-length 32-byte value.
    bogus_hash = b"\xff" * 32
    session.query(AuditEventV2).filter_by(event_id=e2_id).update(
        {AuditEventV2.event_hash: bogus_hash}
    )
    session.commit()
    session.expire_all()

    report = verifier.verify_job_chain(job_id)
    assert not report.is_valid

    findings_by_event: dict[str, list] = {}
    for f in report.findings:
        findings_by_event.setdefault(f.event_id, []).append(f.finding)

    assert e2_id in findings_by_event, f"expected finding on event 2; got {report.findings}"
    assert EventFinding.TAMPERED_EVENT_HASH in findings_by_event[e2_id]

    assert e3_id in findings_by_event, (
        f"expected BROKEN_CHAIN on event 3 (cascade); got {report.findings}"
    )
    assert EventFinding.BROKEN_CHAIN in findings_by_event[e3_id]


# ---------------------------------------------------------------------------
# Test 7 — Tampered previous_hash (event N integrity broken)
# ---------------------------------------------------------------------------


def test_tampered_previous_hash_breaks_event_integrity(fresh_db):
    """Mutate event 3's previous_hash column.

    Cascade:
      - Event 3's recomputed event_hash (uses stored prev + stored payload_hash)
        will use the NEW (tampered) prev_hash, producing a different recomputed
        event_hash than stored → TAMPERED_EVENT_HASH on event 3.
      - Event 3's stored prev_hash (now tampered) != event 2's stored
        event_hash → BROKEN_CHAIN on event 3.
      - Event 4 is unaffected: event 4's stored prev_hash still matches
        event 3's STORED event_hash (which we didn't touch).
    """
    from app.models.audit_v2 import AuditEventV2
    from app.services.audit_verifier_v2 import EventFinding

    core_db, session = fresh_db
    from app.models.database import DEFAULT_ORG_ID

    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    job_id = _seed_job(core_db.engine, DEFAULT_ORG_ID)
    writer = _make_writer(core_db)
    verifier = _make_verifier(core_db)

    events = _write_chain(writer, job_id, 5)
    e3_id = events[3].event_id
    e4_id = events[4].event_id

    bogus_prev = b"\xaa" * 32
    session.query(AuditEventV2).filter_by(event_id=e3_id).update(
        {AuditEventV2.previous_hash: bogus_prev}
    )
    session.commit()
    session.expire_all()

    report = verifier.verify_job_chain(job_id)
    assert not report.is_valid

    findings_by_event: dict[str, list] = {}
    for f in report.findings:
        findings_by_event.setdefault(f.event_id, []).append(f.finding)

    # Event 3 has BOTH findings (worksheet design choice — surface all).
    assert e3_id in findings_by_event, f"expected findings on event 3; got {report.findings}"
    assert EventFinding.TAMPERED_EVENT_HASH in findings_by_event[e3_id]
    assert EventFinding.BROKEN_CHAIN in findings_by_event[e3_id]

    # Event 4 unaffected — stored chain is intact downstream.
    assert e4_id not in findings_by_event, (
        f"event 4 should be OK; got findings: {findings_by_event.get(e4_id)}"
    )


# ---------------------------------------------------------------------------
# Test 8 — Sequence gap (event 2 deleted)
# ---------------------------------------------------------------------------


def test_sequence_gap_when_middle_event_deleted(fresh_db):
    """Delete event 2 entirely. Verifier reports SEQUENCE_GAP."""
    from app.models.audit_v2 import AuditEventV2
    from app.services.audit_verifier_v2 import EventFinding

    core_db, session = fresh_db
    from app.models.database import DEFAULT_ORG_ID

    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    job_id = _seed_job(core_db.engine, DEFAULT_ORG_ID)
    writer = _make_writer(core_db)
    verifier = _make_verifier(core_db)

    events = _write_chain(writer, job_id, 5)
    e2_id = events[2].event_id

    # Raw DELETE — bypasses any soft-delete machinery (audit_events_v2 has no
    # soft delete by regulatory design, but we use direct execute to be sure).
    session.query(AuditEventV2).filter_by(event_id=e2_id).delete()
    session.commit()
    session.expire_all()

    report = verifier.verify_job_chain(job_id)
    assert not report.is_valid
    assert report.event_count == 4  # event 2 is gone

    findings = [f.finding for f in report.findings]
    assert EventFinding.SEQUENCE_GAP in findings, (
        f"expected SEQUENCE_GAP after deletion; got {findings}"
    )


# ---------------------------------------------------------------------------
# Test 9 — Genesis violation (raw INSERT with non-zero prev_hash)
# ---------------------------------------------------------------------------


def test_genesis_violation_when_seq_zero_has_nonzero_prev(fresh_engine_for_db):
    """Raw INSERT event seq=0 with previous_hash != GENESIS_HASH. Verifier flags it."""
    from app.core.tenant_context import org_context
    from app.models.database import DEFAULT_ORG_ID
    from app.services.audit_verifier_v2 import EventFinding

    core_db = fresh_engine_for_db
    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    with org_context(DEFAULT_ORG_ID):
        job_id = _seed_job(core_db.engine, DEFAULT_ORG_ID)
    verifier = _make_verifier(core_db)

    # Raw INSERT bypassing the writer — synthetic chain-corruption.
    event_id = str(uuid.uuid4())
    bogus_prev = b"\x01" * 32  # non-zero, valid length
    payload_bytes = b'{"k":"v"}'  # canonical-json of {"k":"v"}
    import hashlib
    payload_hash = hashlib.sha256(payload_bytes).digest()
    # event_hash computed correctly for the (bogus prev, payload_hash) pair so
    # that we ONLY trip GENESIS_VIOLATION, not TAMPERED_EVENT_HASH.
    h = hashlib.sha256()
    h.update(b"transmax.audit.v1\0")
    h.update((0).to_bytes(8, "little", signed=False))
    h.update(bogus_prev)
    h.update(payload_hash)
    event_hash = h.digest()

    now_iso = datetime.now(timezone.utc).isoformat()
    with core_db.engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO audit_events_v2 "
                "(event_id, organization_id, job_id, sequence_index, domain_tag, "
                "event_type, actor_id, actor_kind, payload, payload_hash, "
                "previous_hash, event_hash, event_ts_utc, created_at) "
                "VALUES (:eid, :org, :job, 0, 'transmax.audit.v1', 'BOGUS', "
                "NULL, 'system', :payload, :ph, :prev, :eh, :ts, :ts)"
            ).bindparams(
                eid=event_id, org=DEFAULT_ORG_ID, job=job_id,
                payload='{"k":"v"}',
                ph=payload_hash, prev=bogus_prev, eh=event_hash,
                ts=now_iso,
            )
        )

    with org_context(DEFAULT_ORG_ID):
        report = verifier.verify_job_chain(job_id)

    assert not report.is_valid
    findings = [f.finding for f in report.findings]
    assert EventFinding.GENESIS_VIOLATION in findings, (
        f"expected GENESIS_VIOLATION; got {findings}"
    )


# ---------------------------------------------------------------------------
# Test 10 — Two-implementation agreement (writer + verifier produce same bytes)
# ---------------------------------------------------------------------------


def test_two_implementation_agreement_writer_and_verifier_match():
    """For the same input, writer.compute_X and verifier.recompute_X return
    byte-identical results.

    This is the DRY-without-losing-independence check. The two
    implementations live in different modules, are written independently,
    and must agree byte-for-byte for the spec to hold. If they ever diverge,
    THIS test fails before any user sees the disagreement.
    """
    from app.services.audit_verifier_v2 import AuditVerifierV2
    from app.services.audit_writer_v2 import AuditWriterV2

    # Sample payloads — diverse to exercise the canonical JSON paths.
    payloads: list[dict[str, Any]] = [
        {"foo": "bar"},
        {},
        {"i": 0, "msg": "event-0"},
        {"unicode": "ümlaut + 中文 + 🎉"},
        {"nested": {"a": 1, "b": [1, 2, 3]}, "k": "v"},
        {"z_last_key": 1, "a_first_key": 2},  # sort_keys
        {"bool": True, "null": None, "int": 42, "float": 3.14},
    ]

    for p in payloads:
        writer_hash = AuditWriterV2.compute_payload_hash(p)
        verifier_hash = AuditVerifierV2.recompute_payload_hash(p)
        assert writer_hash == verifier_hash, (
            f"payload-hash disagreement on {p!r}: "
            f"writer={writer_hash.hex()} verifier={verifier_hash.hex()}"
        )

    # And event-hash agreement across several (seq, prev, ph) tuples.
    sample_payload_hash = AuditWriterV2.compute_payload_hash({"foo": "bar"})
    cases = [
        (0, b"\x00" * 32, sample_payload_hash),
        (1, b"\xff" * 32, sample_payload_hash),
        (999, bytes(range(32)), sample_payload_hash),
        (2**40, b"\xaa" * 32, sample_payload_hash),
    ]
    for seq, prev, ph in cases:
        writer_eh = AuditWriterV2.compute_event_hash(seq, prev, ph)
        verifier_eh = AuditVerifierV2.recompute_event_hash(seq, prev, ph)
        assert writer_eh == verifier_eh, (
            f"event-hash disagreement on (seq={seq}, prev={prev.hex()[:8]}..., "
            f"ph={ph.hex()[:8]}...): writer={writer_eh.hex()} verifier={verifier_eh.hex()}"
        )


# ---------------------------------------------------------------------------
# Boundary tests (Tier 2 item #4)
# ---------------------------------------------------------------------------


def test_empty_job_returns_valid_empty_report(fresh_db):
    """A job with zero events returns is_valid=True (worksheet stage 3 choice)."""
    core_db, _ = fresh_db
    from app.models.database import DEFAULT_ORG_ID

    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    job_id = _seed_job(core_db.engine, DEFAULT_ORG_ID)
    verifier = _make_verifier(core_db)

    report = verifier.verify_job_chain(job_id)
    assert report.is_valid
    assert report.event_count == 0
    assert report.ok_count == 0
    assert report.findings == []


def test_verify_org_chain_returns_one_report_per_job(fresh_db):
    """Org with 3 distinct jobs → verify_org_chain returns 3 reports."""
    core_db, _ = fresh_db
    from app.models.database import DEFAULT_ORG_ID

    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    jobs = [_seed_job(core_db.engine, DEFAULT_ORG_ID) for _ in range(3)]
    writer = _make_writer(core_db)
    verifier = _make_verifier(core_db)

    for j in jobs:
        _write_chain(writer, j, 2)

    reports = verifier.verify_org_chain()
    assert len(reports) == 3
    assert all(r.is_valid for r in reports)
    assert sorted(r.job_id for r in reports if r.job_id) == sorted(jobs)


def test_verify_org_chain_no_context_raises(fresh_engine_for_db):
    """verify_org_chain(None) outside tenant context → TenantContextMissing."""
    from app.core.tenant_context import TenantContextMissing
    from app.services.audit_verifier_v2 import AuditVerifierV2

    core_db = fresh_engine_for_db
    verifier = AuditVerifierV2(session_factory=core_db.SessionLocal)

    with pytest.raises(TenantContextMissing):
        verifier.verify_org_chain()
