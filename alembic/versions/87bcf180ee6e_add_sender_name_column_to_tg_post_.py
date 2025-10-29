"""add sender_name column to tg_post_reactions

Revision ID: 87bcf180ee6e
Revises: 003c5a04a396
Create Date: 2025-10-28 23:22:06.408478

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '87bcf180ee6e'
down_revision: Union[str, None] = '003c5a04a396'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column(
        "tg_post_reactions",
        sa.Column("sender_name", sa.String(), nullable=True)
    )


def downgrade():
    op.drop_column("tg_post_reactions", "sender_name")
