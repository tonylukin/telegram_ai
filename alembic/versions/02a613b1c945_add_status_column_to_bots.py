"""add status column to bots

Revision ID: 02a613b1c945
Revises: a3e946294f92
Create Date: 2025-07-17 17:12:14.045077

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '02a613b1c945'
down_revision: Union[str, None] = 'a3e946294f92'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('bots', sa.Column('status', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('bots', 'status')
