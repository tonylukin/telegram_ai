"""add updated_at column to tg_users

Revision ID: a3e946294f92
Revises: 6a3078200547
Create Date: 2025-06-29 12:39:20.806536

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3e946294f92'
down_revision: Union[str, None] = '6a3078200547'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tg_users', sa.Column('updated_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('tg_users', 'updated_at')
