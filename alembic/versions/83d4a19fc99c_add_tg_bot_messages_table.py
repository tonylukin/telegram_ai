"""add tg bot messages table

Revision ID: 83d4a19fc99c
Revises: 130d878b4e64
Create Date: 2025-08-13 21:27:56.523310

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '83d4a19fc99c'
down_revision: Union[str, None] = '130d878b4e64'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        "tg_bot_messages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("bot_id", sa.Integer, sa.ForeignKey("bots.id"), nullable=False, index=True),
        sa.Column("sender_name", sa.String(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("reply_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    op.drop_index("ix_tg_bot_messages_bot_id", table_name="tg_bot_messages")
    op.drop_table("tg_bot_messages")
