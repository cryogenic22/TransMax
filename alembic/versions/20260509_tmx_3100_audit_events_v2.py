"""TMX-3100 audit_events_v2 + audit_anchors schema

Revision ID: d4f3100_audit_v2
Revises: c3f3015_softdel
Create Date: 2026-05-09

Per plan §6.A. Schema-only — the writer (TMX-3101), timestamps integration
(TMX-3102), FreeTSA (TMX-3103), verification API (TMX-3104), daily Merkle
anchor (TMX-3107) and v1→v2 migration (TMX-3109) are separate Sprint 2
tickets. This revision only creates the tables, indexes, and constraints.

Idempotent on re-runs via introspection — same defensive shape as TMX-3011/3015.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d4f3100_audit_v2"
down_revision: Union[str, None] = "c3f3015_softdel"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _id_type(dialect_name: str):
    if dialect_name == "postgresql":
        return sa.dialects.postgresql.UUID(as_uuid=False)
    return sa.CHAR(36)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())
    id_type = _id_type(bind.dialect.name)

    if "audit_events_v2" not in existing:
        op.create_table(
            "audit_events_v2",
            sa.Column("event_id", id_type, primary_key=True, nullable=False),
            sa.Column("organization_id", id_type, nullable=False),
            sa.Column("job_id", id_type, nullable=False),
            sa.Column("sequence_index", sa.BigInteger(), nullable=False),
            sa.Column("domain_tag", sa.String(), nullable=False),
            sa.Column("event_type", sa.String(), nullable=False),
            sa.Column("actor_id", id_type, nullable=True),
            sa.Column("actor_kind", sa.String(), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("payload_hash", sa.LargeBinary(length=32), nullable=False),
            sa.Column("previous_hash", sa.LargeBinary(length=32), nullable=False),
            sa.Column("event_hash", sa.LargeBinary(length=32), nullable=False),
            sa.Column("event_ts_utc", sa.DateTime(timezone=True), nullable=False),
            sa.Column("tsa_token", sa.LargeBinary(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["organization_id"], ["organizations.id"],
                name="fk_audit_events_v2_organization_id",
            ),
            # FK to translation_jobs (regulatory-layer Postgres+UUID jobs).
            # Skipped on dialects where translation_jobs may not exist (TMX-3017
            # will close); safe because the column is still NOT NULL.
            *(
                [sa.ForeignKeyConstraint(
                    ["job_id"], ["translation_jobs.id"],
                    name="fk_audit_events_v2_job_id",
                )] if "translation_jobs" in existing else []
            ),
            sa.UniqueConstraint("job_id", "sequence_index", name="uq_audit_events_v2_job_seq"),
            sa.CheckConstraint("length(event_hash) = 32", name="ck_audit_events_v2_event_hash_len"),
            sa.CheckConstraint("length(payload_hash) = 32", name="ck_audit_events_v2_payload_hash_len"),
            sa.CheckConstraint(
                "length(previous_hash) = 32", name="ck_audit_events_v2_previous_hash_len",
            ),
        )
        op.create_index(
            "ix_audit_events_v2_org_job_seq",
            "audit_events_v2",
            ["organization_id", "job_id", "sequence_index"],
        )
        op.create_index(
            "ix_audit_events_v2_event_ts_utc",
            "audit_events_v2",
            ["event_ts_utc"],
        )

    if "audit_anchors" not in existing:
        op.create_table(
            "audit_anchors",
            sa.Column("anchor_id", id_type, primary_key=True, nullable=False),
            sa.Column("organization_id", id_type, nullable=False),
            sa.Column("anchor_date", sa.Date(), nullable=False),
            sa.Column("merkle_root", sa.LargeBinary(length=32), nullable=False),
            sa.Column("event_count", sa.BigInteger(), nullable=False),
            sa.Column("first_event_id", id_type, nullable=False),
            sa.Column("last_event_id", id_type, nullable=False),
            sa.Column("s3_object_uri", sa.String(), nullable=False),
            sa.Column("s3_version_id", sa.String(), nullable=False),
            sa.Column("s3_object_lock_until", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["organization_id"], ["organizations.id"],
                name="fk_audit_anchors_organization_id",
            ),
            sa.UniqueConstraint(
                "organization_id", "anchor_date", name="uq_audit_anchors_org_date",
            ),
            sa.CheckConstraint(
                "length(merkle_root) = 32", name="ck_audit_anchors_merkle_root_len",
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    if "audit_anchors" in existing:
        op.drop_table("audit_anchors")
    if "audit_events_v2" in existing:
        op.drop_index("ix_audit_events_v2_event_ts_utc", table_name="audit_events_v2")
        op.drop_index("ix_audit_events_v2_org_job_seq", table_name="audit_events_v2")
        op.drop_table("audit_events_v2")
