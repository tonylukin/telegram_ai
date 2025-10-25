"""create_tg_post_reactions_table

Revision ID: 8b05799aa604
Revises: bdb14d0e3187
Create Date: 2025-10-25 11:00:24.688272

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8b05799aa604'
down_revision: Union[str, None] = 'bdb14d0e3187'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tg_post_reactions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("channel", sa.String(128), nullable=False),
        sa.Column("post_id", sa.Integer, nullable=False),
        sa.Column("reaction", sa.String(16), nullable=False),
        sa.Column("bot_id", sa.Integer, sa.ForeignKey("bots.id"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.UniqueConstraint("post_id", "bot_id", name="uq_tg_post_reactions_post_id_bot_id"),
    )


def downgrade() -> None:
    op.drop_table("tg_post_reactions")
