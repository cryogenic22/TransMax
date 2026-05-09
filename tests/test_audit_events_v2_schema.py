"""
TMX-3100 — schema tests for audit_events_v2 + audit_anchors.

Schema-only validation. The hashing implementation, timestamp wiring,
verification API and migration script are tested in their own ticket loops
(TMX-3101 onwards).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def fresh_db(fresh_engine_for_db):
    """TMX-AUDIT-CLEANUP-ROUTES: delegates to shared conftest fixture."""
    core_db = fresh_engine_for_db
    from app.core.tenant_context import org_context
    from app.models.database import DEFAULT_ORG_ID
    Session = sessionmaker(bind=core_db.engine)
    session = Session()
    with org_context(DEFAULT_ORG_ID):
        yield core_db.engine, session
    session.close()


def test_tables_created_on_fresh_init(fresh_db):
    """Both audit_events_v2 and audit_anchors are created by init_db()."""
    engine, _ = fresh_db
    ins = inspect(engine)
    assert "audit_events_v2" in ins.get_table_names()
    assert "audit_anchors" in ins.get_table_names()


def test_audit_events_v2_columns_match_spec(fresh_db):
    """Column set matches plan §6.A."""
    engine, _ = fresh_db
    ins = inspect(engine)
    cols = {c["name"] for c in ins.get_columns("audit_events_v2")}
    expected = {
        "event_id", "organization_id", "job_id", "sequence_index", "domain_tag",
        "event_type", "actor_id", "actor_kind", "payload", "payload_hash",
        "previous_hash", "event_hash", "event_ts_utc", "tsa_token", "created_at",
    }
    assert expected.issubset(cols), f"missing: {expected - cols}"


def test_audit_anchors_columns_match_spec(fresh_db):
    """Column set matches plan §6.A."""
    engine, _ = fresh_db
    ins = inspect(engine)
    cols = {c["name"] for c in ins.get_columns("audit_anchors")}
    expected = {
        "anchor_id", "organization_id", "anchor_date", "merkle_root", "event_count",
        "first_event_id", "last_event_id", "s3_object_uri", "s3_version_id",
        "s3_object_lock_until", "created_at",
    }
    assert expected.issubset(cols), f"missing: {expected - cols}"


def test_audit_events_v2_indexes_present(fresh_db):
    """Plan §6.A requires (org, job, seq) and (event_ts_utc) indexes."""
    engine, _ = fresh_db
    ins = inspect(engine)
    indexes = {ix["name"] for ix in ins.get_indexes("audit_events_v2")}
    assert "ix_audit_events_v2_org_job_seq" in indexes
    assert "ix_audit_events_v2_event_ts_utc" in indexes


def test_audit_events_v2_does_not_inherit_soft_delete(fresh_db):
    """A1/A9: audit rows are append-only — must NOT carry soft-delete columns."""
    engine, _ = fresh_db
    ins = inspect(engine)
    cols = {c["name"] for c in ins.get_columns("audit_events_v2")}
    for col in ("is_deleted", "deleted_at", "deleted_by"):
        assert col not in cols, f"audit_events_v2 must not have {col} (A1/A9 violation)"


def _genesis_event_kwargs(*, sequence_index: int = 0, organization_id: str, job_id: str):
    """Helper: construct a valid AuditEventV2 with all required fields."""
    return {
        "organization_id": organization_id,
        "job_id": job_id,
        "sequence_index": sequence_index,
        "domain_tag": "audit:event:v2",
        "event_type": "JOB_STARTED",
        "actor_kind": "system",
        "payload": {"doc_id": "test"},
        "payload_hash": b"\x00" * 32,
        "previous_hash": b"\x00" * 32 if sequence_index == 0 else b"\xaa" * 32,
        "event_hash": b"\xff" * 32,
        "event_ts_utc": datetime.now(timezone.utc),
    }


def _seed_parent_job(engine, organization_id: str) -> str:
    """Insert a translation_jobs row so audit_events_v2.job_id FK is satisfied."""
    job_id = str(uuid.uuid4())
    with engine.begin() as conn:
        # Minimal insert — translation_jobs has many nullable columns.
        conn.execute(
            text(
                "INSERT INTO translation_jobs "
                "(id, source_document_id, organization_id, source_language, "
                "target_language, provider, is_deleted, created_at) "
                "VALUES (:id, :src, :org, 'en', 'es', 'OPENAI', 0, :ts)"
            ).bindparams(
                id=job_id,
                src=str(uuid.uuid4()),
                org=organization_id,
                ts=datetime.now(timezone.utc).isoformat(),
            )
        )
    return job_id


def test_audit_events_v2_round_trip(fresh_db):
    """A genesis event with all required fields inserts cleanly."""
    engine, session = fresh_db
    from app.models.audit_v2 import AuditEventV2
    from app.models.database import DEFAULT_ORG_ID

    job_id = _seed_parent_job(engine, DEFAULT_ORG_ID)
    ev = AuditEventV2(**_genesis_event_kwargs(
        organization_id=DEFAULT_ORG_ID, job_id=job_id, sequence_index=0,
    ))
    session.add(ev)
    session.commit()

    fetched = session.query(AuditEventV2).filter_by(job_id=job_id).one()
    assert fetched.sequence_index == 0
    assert fetched.domain_tag == "audit:event:v2"
    assert len(fetched.event_hash) == 32
    assert len(fetched.previous_hash) == 32
    assert fetched.previous_hash == b"\x00" * 32  # genesis


def test_unique_job_sequence_constraint(fresh_db):
    """Two events with the same (job_id, sequence_index) raise IntegrityError."""
    engine, session = fresh_db
    from app.models.audit_v2 import AuditEventV2
    from app.models.database import DEFAULT_ORG_ID

    job_id = _seed_parent_job(engine, DEFAULT_ORG_ID)
    session.add(AuditEventV2(**_genesis_event_kwargs(
        organization_id=DEFAULT_ORG_ID, job_id=job_id, sequence_index=0,
    )))
    session.commit()

    session.add(AuditEventV2(**_genesis_event_kwargs(
        organization_id=DEFAULT_ORG_ID, job_id=job_id, sequence_index=0,
    )))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_event_hash_check_constraint_rejects_short_hash(fresh_db):
    """A 31-byte event_hash violates the length constraint."""
    engine, session = fresh_db
    from app.models.audit_v2 import AuditEventV2
    from app.models.database import DEFAULT_ORG_ID

    job_id = _seed_parent_job(engine, DEFAULT_ORG_ID)
    kwargs = _genesis_event_kwargs(
        organization_id=DEFAULT_ORG_ID, job_id=job_id, sequence_index=0,
    )
    kwargs["event_hash"] = b"\xff" * 31  # too short
    session.add(AuditEventV2(**kwargs))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_payload_hash_check_constraint_rejects_short_hash(fresh_db):
    engine, session = fresh_db
    from app.models.audit_v2 import AuditEventV2
    from app.models.database import DEFAULT_ORG_ID

    job_id = _seed_parent_job(engine, DEFAULT_ORG_ID)
    kwargs = _genesis_event_kwargs(
        organization_id=DEFAULT_ORG_ID, job_id=job_id, sequence_index=0,
    )
    kwargs["payload_hash"] = b"\xff" * 31
    session.add(AuditEventV2(**kwargs))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_audit_anchors_unique_per_org_per_day(fresh_db):
    """One anchor row per (organization_id, anchor_date)."""
    engine, session = fresh_db
    from app.models.audit_v2 import AuditAnchor
    from app.models.database import DEFAULT_ORG_ID

    today = date.today()

    def _anchor():
        return AuditAnchor(
            organization_id=DEFAULT_ORG_ID,
            anchor_date=today,
            merkle_root=b"\xaa" * 32,
            event_count=10,
            first_event_id=str(uuid.uuid4()),
            last_event_id=str(uuid.uuid4()),
            s3_object_uri="s3://transmax-audit/test.bin",
            s3_version_id="v0",
            s3_object_lock_until=datetime.now(timezone.utc),
        )

    session.add(_anchor())
    session.commit()

    session.add(_anchor())
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
