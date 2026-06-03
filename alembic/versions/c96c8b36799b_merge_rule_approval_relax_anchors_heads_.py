"""merge rule_approval + relax_anchors heads (TMX-DEPLOY-1)

Revision ID: c96c8b36799b
Revises: e5f3045_rule_approval, e5f3107_relax_anchors
Create Date: 2026-06-03 23:36:33.820435

"""
from typing import Sequence, Union



# revision identifiers, used by Alembic.
revision: str = 'c96c8b36799b'
down_revision: Union[str, None] = ('e5f3045_rule_approval', 'e5f3107_relax_anchors')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
