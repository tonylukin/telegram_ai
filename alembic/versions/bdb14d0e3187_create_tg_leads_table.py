"""create tg_leads table

Revision ID: bdb14d0e3187
Revises: 4043704e2907
Create Date: 2025-10-02 23:12:57.891987

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func


# revision identifiers, used by Alembic.
revision: str = 'bdb14d0e3187'
down_revision: Union[str, None] = '4043704e2907'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tg_leads",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("channel", sa.String, nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("answer", sa.Text, nullable=True),
        sa.Column("post_id", sa.Integer, nullable=False),
        sa.Column("bot_id", sa.Integer, sa.ForeignKey("bots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=func.now(), nullable=False),
        sa.UniqueConstraint('post_id', name='ux_tg_leads_post_id')
    )


def downgrade() -> None:
    op.drop_table("tg_leads")
