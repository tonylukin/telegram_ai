"""create_ig_users_table

Revision ID: 9159f9b9570c
Revises: 02a613b1c945
Create Date: 2025-08-07 22:25:01.207976

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '9159f9b9570c'
down_revision: Union[str, None] = '02a613b1c945'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ig_users',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('description', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), onupdate=sa.func.now())
    )
    op.create_index(op.f('ix_ig_users_username'), 'ig_users', ['username'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_ig_users_username'), table_name='ig_users')
    op.drop_table('ig_users')
