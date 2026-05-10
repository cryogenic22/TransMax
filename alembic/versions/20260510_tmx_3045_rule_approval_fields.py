"""TMX-3045 add approval fields to translation_rules

Revision ID: e5f3045_rule_approval
Revises: d4f3100_audit_v2
Create Date: 2026-05-10

Pillar 1 / A3 — every learned rule promoted to `ACTIVE` MUST carry a
signed human approval. This revision adds the three columns that
`app.services.rule_promotion.promote_rule()` stamps on each promotion:

  - approved_by      : String, nullable. User id of the approver.
  - approved_at      : DateTime(timezone=True), nullable. UTC instant
                       of the approval signature.
  - approval_reason  : Text, nullable. Free-text justification.

All nullable so existing rows from before TMX-3045 survive (TMX-3045a
will backfill canonical signatures for the historical auto-promoted
rules). Idempotent on re-runs via `Inspector` introspection — same
defensive shape as TMX-3011, TMX-3015, TMX-3100.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e5f3045_rule_approval"
down_revision: Union[str, None] = "d4f3100_audit_v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TARGET_TABLE = "translation_rules"
NEW_COLUMNS = (
    ("approved_by", lambda: sa.Column("approved_by", sa.String(), nullable=True)),
    ("approved_at", lambda: sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True)),
    ("approval_reason", lambda: sa.Column("approval_reason", sa.Text(), nullable=True)),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if TARGET_TABLE not in set(inspector.get_table_names()):
        # Defensive: the C-06 mega-migration may not have created this table
        # in every CI / dev environment. Match TMX-3011 / TMX-3100 behaviour
        # of skipping cleanly so a fresh-DB stamp doesn't crash.
        print(f"TMX-3045: skipping; {TARGET_TABLE} table not present (TMX-3017 will resolve).")
        return

    existing_cols = {c["name"] for c in inspector.get_columns(TARGET_TABLE)}
    for col_name, col_factory in NEW_COLUMNS:
        if col_name not in existing_cols:
            op.add_column(TARGET_TABLE, col_factory())
        else:
            print(f"TMX-3045: column {TARGET_TABLE}.{col_name} already present; skipping.")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if TARGET_TABLE not in set(inspector.get_table_names()):
        return

    existing_cols = {c["name"] for c in inspector.get_columns(TARGET_TABLE)}
    for col_name, _ in NEW_COLUMNS:
        if col_name in existing_cols:
            op.drop_column(TARGET_TABLE, col_name)
