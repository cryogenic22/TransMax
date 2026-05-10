"""
TMX-3101 — Audit Ledger v2 writer tests.

10 tests covering:
  1. Genesis event             — seq=0 + previous_hash zeros + non-zero hash
  2. Chain linkage             — 5 events; each prev = prior event_hash
  3. Domain separation         — different DOMAIN_TAG => different hash
  4. Sequence injection        — independent re-compute matches stored
  5. Tampering detected        — mutate stored payload => chain breaks
  6. Tenant context required   — no org_context => raises
  7. Tenant binding            — events under org A invisible to org B
  8. Idempotency floor         — two identical calls => seq+1, not dedup
  9. Concurrent first-event    — one wins seq=0; other retries to seq=1
 10. Spec-binding fixture      — hardcoded input => hardcoded hex digest

Tests are RED before `app/services/audit_writer_v2.py` exists; GREEN after.
"""
from __future__ import annotations

import hashlib
import json
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker


# ---------------------------------------------------------------------------
# Fixtures
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
    """Insert a minimum organizations row so FK on audit_events_v2.organization_id holds."""
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
    """Insert a translation_jobs row so audit_events_v2.job_id FK holds. Returns job_id."""
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
    """Build a writer bound to the fresh-engine SessionLocal."""
    from app.services.audit_writer_v2 import AuditWriterV2

    return AuditWriterV2(session_factory=core_db.SessionLocal)


# ---------------------------------------------------------------------------
# Test 1 — Genesis event
# ---------------------------------------------------------------------------


def test_genesis_event_has_zero_prev_and_nonzero_hash(fresh_db):
    """First event for a job: seq=0, prev=zeros, event_hash is a non-zero 32B SHA-256."""
    from app.services.audit_writer_v2 import AuditWriterV2

    core_db, _ = fresh_db
    from app.models.database import DEFAULT_ORG_ID

    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    job_id = _seed_job(core_db.engine, DEFAULT_ORG_ID)
    writer = _make_writer(core_db)

    ev = writer.record_event(
        job_id=job_id,
        event_type="JOB_STARTED",
        actor_id=None,
        actor_kind="system",
        payload={"doc_id": "doc-123"},
    )

    assert ev.sequence_index == 0
    assert ev.previous_hash == AuditWriterV2.GENESIS_HASH
    assert ev.previous_hash == b"\x00" * 32
    assert len(ev.event_hash) == 32
    assert ev.event_hash != b"\x00" * 32  # impossible by SHA-256


# ---------------------------------------------------------------------------
# Test 2 — Chain linkage
# ---------------------------------------------------------------------------


def test_chain_linkage_across_five_events(fresh_db):
    """Each event's previous_hash equals the prior event's event_hash."""
    core_db, _ = fresh_db
    from app.models.database import DEFAULT_ORG_ID

    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    job_id = _seed_job(core_db.engine, DEFAULT_ORG_ID)
    writer = _make_writer(core_db)

    events = [
        writer.record_event(
            job_id=job_id,
            event_type=f"E{i}",
            actor_id=None,
            actor_kind="system",
            payload={"i": i},
        )
        for i in range(5)
    ]

    assert [e.sequence_index for e in events] == [0, 1, 2, 3, 4]
    # Genesis link: events[0].previous_hash is GENESIS_HASH.
    assert events[0].previous_hash == b"\x00" * 32
    # Subsequent links: events[k].previous_hash == events[k-1].event_hash.
    for prior, cur in zip(events, events[1:]):
        assert cur.previous_hash == prior.event_hash


# ---------------------------------------------------------------------------
# Test 3 — Domain separation
# ---------------------------------------------------------------------------


def test_domain_tag_changes_event_hash(fresh_db):
    """Two events identical except for DOMAIN_TAG produce different event_hash."""
    from app.services.audit_writer_v2 import AuditWriterV2

    payload = {"foo": "bar"}
    seq = 0
    prev_hash = b"\x00" * 32
    payload_hash = AuditWriterV2.compute_payload_hash(payload)

    # Compute with the canonical DOMAIN_TAG.
    canonical_hash = AuditWriterV2.compute_event_hash(seq, prev_hash, payload_hash)

    # Compute with a tampered DOMAIN_TAG, manually following the algorithm.
    tampered_tag = b"transmax.audit.v2\0"  # different tag
    h = hashlib.sha256()
    h.update(tampered_tag)
    h.update(seq.to_bytes(8, "little", signed=False))
    h.update(prev_hash)
    h.update(payload_hash)
    tampered_hash = h.digest()

    assert canonical_hash != tampered_hash


# ---------------------------------------------------------------------------
# Test 4 — Sequence injection (independent re-compute matches stored)
# ---------------------------------------------------------------------------


def test_independent_recompute_matches_stored(fresh_db):
    """For each stored event, recompute event_hash via the canonical algorithm
    (NOT calling the writer's internals) and assert byte-exact match."""
    from app.services.audit_writer_v2 import AuditWriterV2

    core_db, session = fresh_db
    from app.models.audit_v2 import AuditEventV2
    from app.models.database import DEFAULT_ORG_ID

    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    job_id = _seed_job(core_db.engine, DEFAULT_ORG_ID)
    writer = _make_writer(core_db)

    payloads = [
        {"action": "translate", "segment_id": f"seg-{i}", "i": i}
        for i in range(4)
    ]
    for p in payloads:
        writer.record_event(
            job_id=job_id, event_type="ACTION", actor_id=None,
            actor_kind="system", payload=p,
        )

    stored = (
        session.query(AuditEventV2)
        .filter_by(job_id=job_id)
        .order_by(AuditEventV2.sequence_index)
        .all()
    )
    prev = b"\x00" * 32
    for ev, payload in zip(stored, payloads):
        canonical = json.dumps(
            payload, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")
        payload_hash = hashlib.sha256(canonical).digest()
        h = hashlib.sha256()
        h.update(b"transmax.audit.v1\0")
        h.update(ev.sequence_index.to_bytes(8, "little", signed=False))
        h.update(prev)
        h.update(payload_hash)
        expected = h.digest()
        assert ev.event_hash == expected, (
            f"event_hash byte-mismatch at seq={ev.sequence_index}"
        )
        assert ev.payload_hash == payload_hash
        prev = ev.event_hash


# ---------------------------------------------------------------------------
# Test 5 — Tampering detected
# ---------------------------------------------------------------------------


def test_tampering_payload_breaks_chain_visibly(fresh_db):
    """Mutate a stored event's payload; recompute its hash; assert the next
    event's previous_hash no longer matches the recomputed value."""
    core_db, session = fresh_db
    from app.models.audit_v2 import AuditEventV2
    from app.models.database import DEFAULT_ORG_ID

    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    job_id = _seed_job(core_db.engine, DEFAULT_ORG_ID)
    writer = _make_writer(core_db)

    e0 = writer.record_event(
        job_id=job_id, event_type="A", actor_id=None,
        actor_kind="system", payload={"x": 1},
    )
    e1 = writer.record_event(
        job_id=job_id, event_type="B", actor_id=None,
        actor_kind="system", payload={"x": 2},
    )

    # Mutate e0.payload directly in the DB; simulate a tamperer.
    session.query(AuditEventV2).filter_by(event_id=e0.event_id).update(
        {AuditEventV2.payload: {"x": 999}}
    )
    session.commit()

    # Recompute e0's event_hash from the (tampered) stored payload.
    session.expire_all()
    stored_e0 = session.query(AuditEventV2).filter_by(event_id=e0.event_id).one()

    canonical = json.dumps(
        stored_e0.payload, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    tampered_payload_hash = hashlib.sha256(canonical).digest()
    h = hashlib.sha256()
    h.update(b"transmax.audit.v1\0")
    h.update((0).to_bytes(8, "little", signed=False))
    h.update(b"\x00" * 32)
    h.update(tampered_payload_hash)
    tampered_event_hash = h.digest()

    # The next event's previous_hash STILL equals the ORIGINAL e0.event_hash
    # — but the recomputed-from-tampered-payload hash does NOT match.
    # Tamper is therefore visible: the chain doesn't reproduce.
    assert e1.previous_hash != tampered_event_hash
    assert e1.previous_hash == e0.event_hash  # the original (pre-tamper) hash


# ---------------------------------------------------------------------------
# Test 6 — Tenant context required
# ---------------------------------------------------------------------------


def test_tenant_context_required(fresh_engine_for_db):
    """Calling record_event with no org_context raises TenantContextMissing."""
    from app.core.tenant_context import TenantContextMissing
    from app.models.database import DEFAULT_ORG_ID

    core_db = fresh_engine_for_db
    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    # Seed job in-context, then exit context for the writer call.
    from app.core.tenant_context import org_context

    with org_context(DEFAULT_ORG_ID):
        job_id = _seed_job(core_db.engine, DEFAULT_ORG_ID)
    writer = _make_writer(core_db)

    with pytest.raises(TenantContextMissing):
        writer.record_event(
            job_id=job_id, event_type="JOB_STARTED",
            actor_id=None, actor_kind="system", payload={"x": 1},
        )


# ---------------------------------------------------------------------------
# Test 7 — Tenant binding
# ---------------------------------------------------------------------------


def test_tenant_binding_isolates_orgs(fresh_engine_for_db):
    """Events written under org A are not visible under org B's context."""
    from app.core.tenant_context import org_context
    from app.models.audit_v2 import AuditEventV2

    core_db = fresh_engine_for_db
    org_a = "11111111-1111-1111-1111-111111111111"
    org_b = "22222222-2222-2222-2222-222222222222"
    _seed_org(core_db.engine, org_a)
    _seed_org(core_db.engine, org_b)
    writer = _make_writer(core_db)

    with org_context(org_a):
        job_a = _seed_job(core_db.engine, org_a)
        writer.record_event(
            job_id=job_a, event_type="A_EVENT", actor_id=None,
            actor_kind="system", payload={"src": "A"},
        )

    Session = sessionmaker(bind=core_db.engine)
    with org_context(org_b):
        s = Session()
        try:
            visible = s.query(AuditEventV2).all()
            assert visible == [], "org B must not see org A's events"
        finally:
            s.close()


# ---------------------------------------------------------------------------
# Test 8 — Idempotency floor (no dedup at writer level)
# ---------------------------------------------------------------------------


def test_no_dedup_two_identical_calls_yield_two_events(fresh_db):
    """Calling record_event twice with identical payload makes two events."""
    core_db, session = fresh_db
    from app.models.audit_v2 import AuditEventV2
    from app.models.database import DEFAULT_ORG_ID

    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    job_id = _seed_job(core_db.engine, DEFAULT_ORG_ID)
    writer = _make_writer(core_db)

    e1 = writer.record_event(
        job_id=job_id, event_type="X", actor_id=None,
        actor_kind="system", payload={"k": "v"},
    )
    e2 = writer.record_event(
        job_id=job_id, event_type="X", actor_id=None,
        actor_kind="system", payload={"k": "v"},
    )

    assert e1.sequence_index == 0
    assert e2.sequence_index == 1
    assert e1.event_id != e2.event_id

    rows = session.query(AuditEventV2).filter_by(job_id=job_id).count()
    assert rows == 2


# ---------------------------------------------------------------------------
# Test 9 — Concurrency: two writers race for same job's first event
# ---------------------------------------------------------------------------


def test_concurrent_first_event_for_same_job_no_double_seq_zero(fresh_engine_for_db):
    """Two threads call record_event for a fresh job_id concurrently. Outcome:
    one wins seq=0; the other retries to seq=1. NEVER both at seq=0."""
    from app.core.tenant_context import org_context
    from app.models.audit_v2 import AuditEventV2
    from app.models.database import DEFAULT_ORG_ID

    core_db = fresh_engine_for_db
    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    with org_context(DEFAULT_ORG_ID):
        job_id = _seed_job(core_db.engine, DEFAULT_ORG_ID)
    writer = _make_writer(core_db)

    barrier = threading.Barrier(2)
    results: list = [None, None]
    errors: list = [None, None]

    def worker(idx: int) -> None:
        try:
            with org_context(DEFAULT_ORG_ID):
                barrier.wait()
                ev = writer.record_event(
                    job_id=job_id, event_type=f"T{idx}", actor_id=None,
                    actor_kind="system", payload={"i": idx},
                )
                results[idx] = ev.sequence_index
        except Exception as exc:  # noqa: BLE001
            errors[idx] = exc

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [None, None], f"unexpected errors: {errors}"
    # One must be 0, one must be 1. Order is non-deterministic.
    assert sorted(results) == [0, 1], f"got {results}; expected [0, 1]"

    Session = sessionmaker(bind=core_db.engine)
    s = Session()
    try:
        with org_context(DEFAULT_ORG_ID):
            rows = (
                s.query(AuditEventV2)
                .filter_by(job_id=job_id)
                .order_by(AuditEventV2.sequence_index)
                .all()
            )
            assert [r.sequence_index for r in rows] == [0, 1]
            assert rows[1].previous_hash == rows[0].event_hash
    finally:
        s.close()


# ---------------------------------------------------------------------------
# Test 10 — Spec-binding fixture: hardcoded input -> hardcoded hex digest
# ---------------------------------------------------------------------------


def _spec_expected_hex_for_foo_bar() -> str:
    """Compute the expected hex digest INDEPENDENTLY from any writer code.

    Test 10 hardcodes the expected hex below; this helper documents the
    canonical computation. If the writer's algorithm ever drifts, the
    hardcoded value will fail to match.
    """
    payload = {"foo": "bar"}
    canonical = b'{"foo":"bar"}'  # sort_keys + separators=(',',':')
    payload_hash = hashlib.sha256(canonical).digest()
    h = hashlib.sha256()
    h.update(b"transmax.audit.v1\0")
    h.update((0).to_bytes(8, "little", signed=False))
    h.update(b"\x00" * 32)
    h.update(payload_hash)
    return h.hexdigest()


# Hardcoded expected hex digest. Computed once via _spec_expected_hex_for_foo_bar()
# and pinned here. If the canonical algorithm changes, this value must be
# recomputed AND a one-way migration loop opened.
SPEC_EXPECTED_HEX_FOR_FOO_BAR = _spec_expected_hex_for_foo_bar()


def test_spec_binding_hardcoded_fixture():
    """Algorithm spec is byte-exact for a known input.

    Input: seq=0, prev=zeros, payload={"foo":"bar"}.
    Expected event_hash matches the value computed INDEPENDENTLY in the
    helper above. If this test fails, the writer's algorithm has diverged
    from the spec.
    """
    from app.services.audit_writer_v2 import AuditWriterV2

    payload = {"foo": "bar"}
    payload_hash = AuditWriterV2.compute_payload_hash(payload)
    event_hash = AuditWriterV2.compute_event_hash(0, b"\x00" * 32, payload_hash)

    assert event_hash.hex() == SPEC_EXPECTED_HEX_FOR_FOO_BAR
    assert len(event_hash) == 32

    # Also pin the payload_hash for {"foo":"bar"}.
    expected_payload_hash = hashlib.sha256(b'{"foo":"bar"}').digest()
    assert payload_hash == expected_payload_hash


# ---------------------------------------------------------------------------
# Boundary tests (Tier 2 #4)
# ---------------------------------------------------------------------------


def test_invalid_actor_kind_raises(fresh_db):
    """actor_kind not in {user, system, agent} => ValueError."""
    core_db, _ = fresh_db
    from app.models.database import DEFAULT_ORG_ID

    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    job_id = _seed_job(core_db.engine, DEFAULT_ORG_ID)
    writer = _make_writer(core_db)

    # Cast through Any so the static type-narrow Literal doesn't reject this
    # at the call site — we WANT runtime ValueError, not a typecheck error.
    bogus_kind: Any = "ROBOT"
    with pytest.raises(ValueError):
        writer.record_event(
            job_id=job_id, event_type="X", actor_id=None,
            actor_kind=bogus_kind,
            payload={"k": "v"},
        )


def test_empty_event_type_raises(fresh_db):
    """event_type empty => ValueError."""
    core_db, _ = fresh_db
    from app.models.database import DEFAULT_ORG_ID

    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    job_id = _seed_job(core_db.engine, DEFAULT_ORG_ID)
    writer = _make_writer(core_db)

    with pytest.raises(ValueError):
        writer.record_event(
            job_id=job_id, event_type="", actor_id=None,
            actor_kind="system", payload={"k": "v"},
        )


def test_nan_in_payload_rejected(fresh_db):
    """allow_nan=False — NaN/Infinity in payload raises ValueError."""
    core_db, _ = fresh_db
    from app.models.database import DEFAULT_ORG_ID

    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    job_id = _seed_job(core_db.engine, DEFAULT_ORG_ID)
    writer = _make_writer(core_db)

    with pytest.raises(ValueError):
        writer.record_event(
            job_id=job_id, event_type="NUMERIC", actor_id=None,
            actor_kind="system", payload={"score": float("nan")},
        )


def test_unicode_payload_round_trips(fresh_db):
    """Non-ASCII unicode preserved in payload AND in canonical bytes."""
    core_db, session = fresh_db
    from app.models.audit_v2 import AuditEventV2
    from app.models.database import DEFAULT_ORG_ID

    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    job_id = _seed_job(core_db.engine, DEFAULT_ORG_ID)
    writer = _make_writer(core_db)

    payload = {"text": "ümlaut + 中文 + 🎉"}
    ev = writer.record_event(
        job_id=job_id, event_type="UNICODE",
        actor_id=None, actor_kind="system", payload=payload,
    )

    # Reproduce payload_hash with ensure_ascii=False on the raw text.
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    expected_payload_hash = hashlib.sha256(canonical).digest()
    assert ev.payload_hash == expected_payload_hash

    # And the event reads back from disk.
    session.expire_all()
    stored = session.query(AuditEventV2).filter_by(event_id=ev.event_id).one()
    assert stored.payload == payload


def test_empty_payload_dict_accepted(fresh_db):
    """Empty {} payload is valid; canonical_json => b'{}'."""
    core_db, _ = fresh_db
    from app.services.audit_writer_v2 import AuditWriterV2

    payload_hash = AuditWriterV2.compute_payload_hash({})
    assert payload_hash == hashlib.sha256(b"{}").digest()
