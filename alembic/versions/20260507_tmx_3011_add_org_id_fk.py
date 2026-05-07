"""TMX-3011 add organization_id FK to all tenant-scoped tables

Revision ID: b2f3011_org_fk
Revises: a1f3010_orgs
Create Date: 2026-05-07

For every tenant-scoped table:
  1. Add `organization_id` as nullable (existing rows survive).
  2. Backfill all NULL values to the seeded system default-org id.
  3. ALTER to NOT NULL + add FK constraint to organizations.id + index.

`language_packs` is intentionally excluded — system-level config, not tenant-scoped.
`organizations` is the FK target; no self-reference needed.

Some tables already had a bare `organization_id UUID(as_uuid=True)` column
(translation_jobs, translation_glossaries, translation_memory, audit_records).
For those we run the backfill + FK add steps but skip the add_column step.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b2f3011_org_fk"
down_revision: Union[str, None] = "a1f3010_orgs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DEFAULT_ORG_ID = "00000000-0000-0000-0000-000000000001"

# Tables that need a NEW organization_id column added.
NEW_ORG_TABLES: list[str] = [
    "documents",
    "segments",
    "change_logs",
    "deletion_records",
    "users",
    "chunk_translations",
    "quality_reports",
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

# Tables that already have a bare organization_id UUID column — only need backfill + FK.
EXISTING_ORG_TABLES: list[str] = [
    "audit_records",
    "translation_jobs",
    "translation_glossaries",
    "translation_memory",
]


def _id_type(dialect_name: str):
    if dialect_name == "postgresql":
        return sa.dialects.postgresql.UUID(as_uuid=False)
    return sa.CHAR(36)


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    id_type = _id_type(dialect)
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # Defensive introspection: the migration must run cleanly on three states:
    # (1) clean DB just stamped at 430291da76c3 — column doesn't exist anywhere;
    # (2) hybrid dev DB built via runtime init_db() before alembic — column may
    #     already exist on tables defined in the model;
    # (3) some tables don't exist at all because the C-06 mega-migration is
    #     incomplete — TMX-3017 will rationalise. Skip them here.
    target_tables = NEW_ORG_TABLES + EXISTING_ORG_TABLES
    present_tables = [t for t in target_tables if t in existing_tables]
    skipped = set(target_tables) - set(present_tables)
    if skipped:
        print(f"TMX-3011: skipping absent tables (TMX-3017 will pick up): {sorted(skipped)}")

    for table in present_tables:
        cols = {c["name"]: c for c in inspector.get_columns(table)}
        fks = inspector.get_foreign_keys(table)
        indexes = {ix["name"] for ix in inspector.get_indexes(table)}

        # ---- Step 1: add column nullable if missing. ----
        if "organization_id" not in cols:
            op.add_column(table, sa.Column("organization_id", id_type, nullable=True))

        # ---- Step 2: backfill NULL rows to default-org. ----
        op.execute(
            sa.text(
                f"UPDATE {table} SET organization_id = :id WHERE organization_id IS NULL"
            ).bindparams(id=DEFAULT_ORG_ID)
        )

        # ---- Step 3: NOT NULL + FK + index, skipping anything already in place. ----
        already_not_null = (
            "organization_id" in cols and cols["organization_id"]["nullable"] is False
        )
        already_has_fk = any(
            fk["referred_table"] == "organizations"
            and "organization_id" in fk["constrained_columns"]
            for fk in fks
        )
        ix_name = f"ix_{table}_organization_id"
        already_has_index = ix_name in indexes

        with op.batch_alter_table(table) as batch:
            if not already_not_null:
                batch.alter_column("organization_id", existing_type=id_type, nullable=False)
            if not already_has_fk:
                batch.create_foreign_key(
                    f"fk_{table}_organization_id",
                    "organizations",
                    ["organization_id"],
                    ["id"],
                )
            if not already_has_index:
                batch.create_index(ix_name, ["organization_id"])


def downgrade() -> None:
    all_tables = NEW_ORG_TABLES + EXISTING_ORG_TABLES
    for table in all_tables:
        with op.batch_alter_table(table) as batch:
            batch.drop_index(f"ix_{table}_organization_id")
            batch.drop_constraint(f"fk_{table}_organization_id", type_="foreignkey")
    for table in NEW_ORG_TABLES:
        op.drop_column(table, "organization_id")
    # For EXISTING_ORG_TABLES we leave the column in place (it pre-dated this revision).
