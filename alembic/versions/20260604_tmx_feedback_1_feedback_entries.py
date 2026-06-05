"""TMX-FEEDBACK-1: create feedback_entries table.

In-app user feedback intake (bug / issue / enhancement / feature /
data_quality / data_request). Tenant-scoped (TMX-3011/3012) + soft-delete
(A9). Status lifecycle: new -> triaged -> in_progress -> resolved | rejected.

NOTE: the live Railway DB is built by `init_db()` create_all (no
alembic_version present — see TMX-DEPLOY-MIGRATE), so this table will be
created there by create_all regardless. This revision exists for
convention + local/CI parity and for environments that DO run Alembic.

Revision ID: tmx_feedback_1
Revises: c96c8b36799b
Create Date: 2026-06-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.models.types import GUID

revision: str = "tmx_feedback_1"
down_revision: Union[str, None] = "c96c8b36799b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "feedback_entries",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "organization_id", GUID(), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("user_id", sa.String(length=255), nullable=True),
        sa.Column("session_id", sa.String(length=255), nullable=True),
        sa.Column("page_url", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "priority", sa.String(length=20), nullable=True, server_default="medium"
        ),
        sa.Column("status", sa.String(length=20), nullable=True, server_default="new"),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("resolved_by", sa.String(length=20), nullable=True),
        sa.Column("entity_context", sa.JSON(), nullable=True),
        sa.Column("diagnostic_context", sa.JSON(), nullable=True),
        sa.Column("attachments", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        # Soft-delete columns (SoftDeleteMixin)
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_by", sa.String(length=36), nullable=True),
    )
    op.create_index(
        "ix_feedback_entries_organization_id", "feedback_entries", ["organization_id"]
    )
    op.create_index("ix_feedback_entries_category", "feedback_entries", ["category"])
    op.create_index("ix_feedback_entries_status", "feedback_entries", ["status"])
    op.create_index(
        "ix_feedback_entries_created_at", "feedback_entries", ["created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_feedback_entries_created_at", table_name="feedback_entries")
    op.drop_index("ix_feedback_entries_status", table_name="feedback_entries")
    op.drop_index("ix_feedback_entries_category", table_name="feedback_entries")
    op.drop_index("ix_feedback_entries_organization_id", table_name="feedback_entries")
    op.drop_table("feedback_entries")
