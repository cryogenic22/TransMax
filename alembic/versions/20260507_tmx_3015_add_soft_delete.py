"""TMX-3015 add soft-delete columns to every tenant-scoped table

Revision ID: c3f3015_softdel
Revises: b2f3011_org_fk
Create Date: 2026-05-07

For every tenant-scoped table AND organizations:
  - add `is_deleted BOOLEAN NOT NULL DEFAULT FALSE`
  - add `deleted_at DATETIME NULL`
  - add `deleted_by VARCHAR(36) NULL`

Idempotent across Postgres + SQLite (uses op.batch_alter_table for SQLite limitations).
Defensive introspection: skips absent tables and columns already present, just like TMX-3011.

`language_packs` is intentionally excluded — system-level config, never deleted (versioned instead).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3f3015_softdel"
down_revision: Union[str, None] = "b2f3011_org_fk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Same set as TMX-3011 NEW_ORG_TABLES + EXISTING_ORG_TABLES, plus organizations itself.
# language_packs is intentionally absent — system-level table.
SOFT_DELETE_TABLES: list[str] = [
    "organizations",
    # database.py
    "documents",
    "segments",
    "change_logs",
    "deletion_records",
    # auth.py
    "users",
    # audit.py
    "audit_records",
    # translation.py
    "translation_jobs",
    "chunk_translations",
    "quality_reports",
    "translation_glossaries",
    "translation_memory",
    # models.py
    "translation_rules",
    "translation_jobs_queue",
    "job_config_snapshots",
    "audit_log_entries",
    "quality_scorecards",
    "scorecard_entries",
    "audit_records_queue",
    "glossaries",
    "glossary_terms",
    "tm_segments",
    "dead_letter_queue",
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    present = [t for t in SOFT_DELETE_TABLES if t in existing_tables]
    skipped = set(SOFT_DELETE_TABLES) - set(present)
    if skipped:
        print(f"TMX-3015: skipping absent tables (TMX-3017 will pick up): {sorted(skipped)}")

    for table in present:
        cols = {c["name"] for c in inspector.get_columns(table)}

        if "is_deleted" not in cols:
            op.add_column(
                table,
                sa.Column(
                    "is_deleted",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                ),
            )
        if "deleted_at" not in cols:
            op.add_column(table, sa.Column("deleted_at", sa.DateTime(), nullable=True))
        if "deleted_by" not in cols:
            op.add_column(table, sa.Column("deleted_by", sa.String(length=36), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    present = [t for t in SOFT_DELETE_TABLES if t in existing_tables]

    for table in present:
        cols = {c["name"] for c in inspector.get_columns(table)}
        with op.batch_alter_table(table) as batch:
            if "deleted_by" in cols:
                batch.drop_column("deleted_by")
            if "deleted_at" in cols:
                batch.drop_column("deleted_at")
            if "is_deleted" in cols:
                batch.drop_column("is_deleted")
