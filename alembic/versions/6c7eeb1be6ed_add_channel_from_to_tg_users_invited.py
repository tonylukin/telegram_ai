"""Add channel_from to tg_users_invited

Revision ID: 6c7eeb1be6ed
Revises: 04bff80402d0
Create Date: 2025-06-23 19:30:28.905288

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6c7eeb1be6ed'
down_revision: Union[str, None] = '04bff80402d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tg_users_invited', sa.Column('channel_from', sa.String(), nullable=True))
    op.add_column('tg_users_invited', sa.Column('bot_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_tg_users_invited_bot_id_bots',  # Constraint name
        'tg_users_invited',  # Source table
        'bots',  # Referenced table
        ['bot_id'],  # Local columns
        ['id'],  # Remote columns
        ondelete='SET NULL'  # Optional: adjust depending on logic
    )


def downgrade() -> None:
    op.drop_column('tg_users_invited', 'channel_from')
    op.drop_constraint('fk_tg_users_invited_bot_id_bots', 'tg_users_invited', type_='foreignkey')
    op.drop_column('tg_users_invited', 'bot_id')
