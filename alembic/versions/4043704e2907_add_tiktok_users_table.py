"""add tiktok_users table

Revision ID: 4043704e2907
Revises: 1d8d301d00cf
Create Date: 2025-08-21 23:28:30.981255

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4043704e2907'
down_revision: Union[str, None] = '1d8d301d00cf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'tiktok_users',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('description', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), onupdate=sa.func.now())
    )
    op.create_index(op.f('ix_tiktok_users_username'), 'tiktok_users', ['username'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_tiktok_users_username'), table_name='ig_users')
    op.drop_table('tiktok_users')
