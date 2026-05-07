"""TMX-3010 add organizations table + seed default-org

Revision ID: a1f3010_orgs
Revises: 430291da76c3
Create Date: 2026-05-05

This migration is intentionally narrow: it creates the `organizations` table
and seeds the system default-org row. TMX-3011 will add `organization_id` FKs
to every domain table and backfill them to the default-org id.

Note: TMX-3017 will retroactively split the existing single mega-migration
(430291da76c3) into 8-12 semantic revisions. This new revision is one of those
semantic units, born clean.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1f3010_orgs"
down_revision: Union[str, None] = "430291da76c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DEFAULT_ORG_ID = "00000000-0000-0000-0000-000000000001"
SEED_TIMESTAMP = "2026-05-05T00:00:00+00:00"


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # GUID type compiles to UUID on Postgres / CHAR(36) on SQLite. We use a raw
    # column type spec here (not the Python decorator) so the migration is
    # independent of app code: alembic should be runnable even if model files
    # change later.
    if dialect == "postgresql":
        id_type = sa.dialects.postgresql.UUID(as_uuid=False)
    else:
        id_type = sa.CHAR(36)

    op.create_table(
        "organizations",
        sa.Column("id", id_type, primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("org_kind", sa.String(length=32), nullable=False, server_default="customer"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
        sa.CheckConstraint(
            "org_kind IN ('system','customer','partner')",
            name="ck_organizations_org_kind",
        ),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)

    # Seed the system default-org. Idempotent across dialects.
    if dialect == "postgresql":
        op.execute(
            sa.text(
                "INSERT INTO organizations "
                "(id, name, slug, org_kind, is_active, created_at, updated_at) "
                "VALUES (:id, :name, :slug, :kind, TRUE, :ts, :ts) "
                "ON CONFLICT (id) DO NOTHING"
            ).bindparams(
                id=DEFAULT_ORG_ID, name="default", slug="default", kind="system", ts=SEED_TIMESTAMP
            )
        )
    else:
        # SQLite (and any dialect supporting INSERT OR IGNORE syntax via SQLite).
        op.execute(
            sa.text(
                "INSERT OR IGNORE INTO organizations "
                "(id, name, slug, org_kind, is_active, created_at, updated_at) "
                "VALUES (:id, :name, :slug, :kind, 1, :ts, :ts)"
            ).bindparams(
                id=DEFAULT_ORG_ID, name="default", slug="default", kind="system", ts=SEED_TIMESTAMP
            )
        )


def downgrade() -> None:
    op.drop_index("ix_organizations_slug", table_name="organizations")
    op.drop_table("organizations")
