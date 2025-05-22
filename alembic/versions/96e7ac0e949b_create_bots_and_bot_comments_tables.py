"""create bots and bot_comments tables

Revision ID: 96e7ac0e949b
Revises: 873d3dd90d1a
Create Date: 2025-05-21 20:01:23.368776

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '96e7ac0e949b'
down_revision: Union[str, None] = '873d3dd90d1a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        'bots',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
    )

    op.create_index('ux_bots_name', 'bots', ['name'], unique=True)

    op.create_table(
        'bot_comments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('bot_id', sa.Integer(), sa.ForeignKey('bots.id'), nullable=False),
        sa.Column('comment', sa.Text(), nullable=False),
        sa.Column('channel', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
    )

    op.create_index('ix_bot_comments_channel', 'bot_comments', ['channel'], unique=False)


def downgrade():
    op.drop_index('ix_bot_comments_channel', table_name='bot_comments')
    op.drop_index('ux_bots_name', table_name='bots')
    op.drop_table('bot_comments')
    op.drop_table('bots')
