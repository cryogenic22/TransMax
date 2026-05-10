"""
TMX-3100 — Audit Ledger v2 schema.

Per plan §6.A. Domain-separated chained-hash audit trail with daily Merkle-root
anchoring to S3 Object Lock. The v3.0 regulator-defensible audit trail.

This module defines the SCHEMA only (TMX-3100). The hashing implementation
(TMX-3101), per-event timestamp wiring (TMX-3102), FreeTSA integration
(TMX-3103), verification API (TMX-3104), daily Merkle anchor (TMX-3107) and
v1→v2 migration script (TMX-3109) are separate Sprint 2 tickets.

A1 / A9 note: AuditEventV2 is **append-only by regulatory design** and
intentionally does NOT inherit SoftDeleteMixin. Two reasons:
  1. The auto-filter would silently exclude rows where `is_deleted=True` —
     a regulator-facing tampering vector. Audit rows must always be visible.
  2. The chained-hash invariant means deleting any event breaks every
     subsequent event's hash; the data structure itself enforces append-only.
The legacy `app/models/audit.py:AuditRecord` (v1) and `app/models/models.py:
AuditRecord` (queue) stay in place for back-compat reads until TMX-3109
migrates them.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    LargeBinary,
    String,
    UniqueConstraint,
)

from app.models.database import Base
from app.models.types import GUID
from app.models.tenant_scoped import TenantScopedMixin


class AuditEventV2(TenantScopedMixin, Base):
    """
    A single chained audit event. Append-only.

    `sequence_index = 0` is the per-job genesis row, with `previous_hash` set
    to 32 zero bytes (no hardcoded GENESIS_HASH constant — closes C-04).
    `event_hash` is computed per the plan §6.A canonical-bytes layout
    (TMX-3101). Until TMX-3101 lands, writers must compute hashes externally.

    `tsa_token` is the optional RFC 3161 timestamp-token blob (FreeTSA or
    DigiCert). Populated for `actor_kind = 'user'` and any e-signature event;
    NULL for high-volume system events (those rely on the daily Merkle
    anchor's TSA token instead).
    """

    __tablename__ = "audit_events_v2"

    event_id = Column(GUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(GUID, ForeignKey("organizations.id"), nullable=False)
    # FK to translation_jobs (the regulatory-layer Postgres+UUID jobs table),
    # NOT translation_jobs_queue. v2 audit is for the regulatory pipeline.
    job_id = Column(GUID, ForeignKey("translation_jobs.id"), nullable=False)
    sequence_index = Column(BigInteger, nullable=False)
    domain_tag = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    actor_id = Column(GUID, nullable=True)
    actor_kind = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    payload_hash = Column(LargeBinary(32), nullable=False)
    previous_hash = Column(LargeBinary(32), nullable=False)
    event_hash = Column(LargeBinary(32), nullable=False)
    event_ts_utc = Column(DateTime(timezone=True), nullable=False)
    tsa_token = Column(LargeBinary, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("job_id", "sequence_index", name="uq_audit_events_v2_job_seq"),
        CheckConstraint("length(event_hash) = 32", name="ck_audit_events_v2_event_hash_len"),
        CheckConstraint("length(payload_hash) = 32", name="ck_audit_events_v2_payload_hash_len"),
        CheckConstraint("length(previous_hash) = 32", name="ck_audit_events_v2_previous_hash_len"),
        Index(
            "ix_audit_events_v2_org_job_seq",
            "organization_id",
            "job_id",
            "sequence_index",
        ),
        Index("ix_audit_events_v2_event_ts_utc", "event_ts_utc"),
    )

    def __repr__(self):
        return (
            f"<AuditEventV2(job={self.job_id}, seq={self.sequence_index}, "
            f"type={self.event_type})>"
        )


class AuditAnchor(TenantScopedMixin, Base):
    """
    Daily Merkle-root anchor per organization.

    A scheduled job at 00:05 UTC per organization (TMX-3107) builds the Merkle
    tree over the previous day's events, writes the root + event-count + first/
    last event-id to S3 Object Lock with compliance-mode retention (default
    10 years), and inserts a row here. The daily anchor itself becomes an
    `AuditEventV2` of type `DAILY_ANCHOR` chained into the v2 ledger.
    """

    __tablename__ = "audit_anchors"

    anchor_id = Column(GUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(GUID, ForeignKey("organizations.id"), nullable=False)
    anchor_date = Column(Date, nullable=False)
    merkle_root = Column(LargeBinary(32), nullable=False)
    event_count = Column(BigInteger, nullable=False)
    # TMX-3107: first/last event ids and S3 retention metadata are NULL for
    # empty-day anchors (an org with zero events on a given date) and for
    # backends that don't expose a version id (e.g. LocalFilesystemObjectStore).
    # A3: empty-day anchors are an honest "no events occurred" assertion, not
    # a sentinel-padded silent fallback.
    first_event_id = Column(GUID, nullable=True)
    last_event_id = Column(GUID, nullable=True)
    s3_object_uri = Column(String, nullable=False)
    s3_version_id = Column(String, nullable=True)
    s3_object_lock_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "anchor_date", name="uq_audit_anchors_org_date"),
        CheckConstraint("length(merkle_root) = 32", name="ck_audit_anchors_merkle_root_len"),
    )

    def __repr__(self):
        return (
            f"<AuditAnchor(org={self.organization_id}, date={self.anchor_date}, "
            f"events={self.event_count})>"
        )
