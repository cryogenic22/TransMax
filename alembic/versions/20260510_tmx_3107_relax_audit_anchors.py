"""TMX-3107 relax audit_anchors NOT-NULL columns to support empty-day anchors

Revision ID: e5f3107_relax_anchors
Revises: d4f3100_audit_v2
Create Date: 2026-05-10

The fresh ``audit_anchors`` table from TMX-3100 had four NOT-NULL columns
that don't survive legitimate operating states:

  - ``first_event_id`` — empty-day anchors have no first event.
  - ``last_event_id``  — empty-day anchors have no last event.
  - ``s3_version_id``  — local-filesystem backend has no version id.
  - ``s3_object_lock_until`` — retention horizon is backend-dependent.

A3 (no silent fallbacks): an empty day is a positive assertion that no
events occurred. Sentinel-padding the columns to satisfy NOT NULL would
be a textbook silent-fallback (storing all-zeros UUIDs as if an event
existed). The honest schema lets the column be NULL.

This migration is safe because no production rows exist in
``audit_anchors`` yet — TMX-3100 created the table; TMX-3107 is the
first writer. Idempotent on re-runs via column introspection.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e5f3107_relax_anchors"
down_revision: Union[str, None] = "d4f3100_audit_v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_RELAXED_COLUMNS = (
    ("first_event_id", "GUID"),
    ("last_event_id", "GUID"),
    ("s3_version_id", "String"),
    ("s3_object_lock_until", "DateTime"),
)


def _id_type(dialect_name: str):
    if dialect_name == "postgresql":
        return sa.dialects.postgresql.UUID(as_uuid=False)
    return sa.CHAR(36)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "audit_anchors" not in inspector.get_table_names():
        return  # Table doesn't exist yet; TMX-3100's migration will create it correctly.

    cols = {c["name"]: c for c in inspector.get_columns("audit_anchors")}
    id_type = _id_type(bind.dialect.name)

    type_map = {
        "GUID": id_type,
        "String": sa.String(),
        "DateTime": sa.DateTime(timezone=True),
    }

    with op.batch_alter_table("audit_anchors") as batch:
        for col_name, type_name in _RELAXED_COLUMNS:
            if col_name in cols and cols[col_name].get("nullable") is False:
                batch.alter_column(
                    col_name,
                    existing_type=type_map[type_name],
                    nullable=True,
                )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "audit_anchors" not in inspector.get_table_names():
        return

    cols = {c["name"]: c for c in inspector.get_columns("audit_anchors")}
    id_type = _id_type(bind.dialect.name)

    type_map = {
        "GUID": id_type,
        "String": sa.String(),
        "DateTime": sa.DateTime(timezone=True),
    }

    with op.batch_alter_table("audit_anchors") as batch:
        for col_name, type_name in _RELAXED_COLUMNS:
            if col_name in cols and cols[col_name].get("nullable") is True:
                batch.alter_column(
                    col_name,
                    existing_type=type_map[type_name],
                    nullable=False,
                )
