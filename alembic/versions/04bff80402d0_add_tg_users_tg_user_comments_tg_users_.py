"""Add tg_users, tg_user_comments, tg_users_invited tables

Revision ID: 04bff80402d0
Revises: 96e7ac0e949b
Create Date: 2025-06-11 19:30:29.994676

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import BIGINT

# revision identifiers, used by Alembic.
revision: str = '04bff80402d0'
down_revision: Union[str, None] = '96e7ac0e949b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        'tg_users',
        sa.Column('id', BIGINT, primary_key=True, autoincrement=True),
        sa.Column('tg_id', BIGINT, nullable=False),
        sa.Column('nickname', sa.String(), nullable=True),
        sa.Column('description', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_unique_constraint(
        'ux_tg_users_tg_id_nickname',
        'tg_users',
        ['tg_id', 'nickname']
    )
    op.create_index(
        'ix_tg_users_nickname',
        'tg_users',
        ['nickname']
    )

    op.create_table(
        'tg_user_comments',
        sa.Column('id', BIGINT, primary_key=True, autoincrement=True),
        sa.Column('user_id', BIGINT, sa.ForeignKey('tg_users.id'), nullable=False),
        sa.Column('comment', sa.Text(), nullable=False),
        sa.Column('channel', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        'ix_tg_user_comments_user_id',
        'tg_user_comments',
        ['user_id']
    )

    op.create_table(
        'tg_users_invited',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('tg_user_id', BIGINT, nullable=False),
        sa.Column('channel', sa.String(128), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('tg_user_id', 'channel', name='ux_tg_users_invited_tg_user_id_channel')
    )
    op.add_column(
        'tg_users_invited',
        sa.Column('tg_username', sa.String(), nullable=True)
    )


def downgrade():
    op.drop_table('tg_users_invited')
    op.drop_index('ix_tg_user_comments_user_id', table_name='tg_user_comments')
    op.drop_table('tg_user_comments')
    op.drop_table('tg_users')
