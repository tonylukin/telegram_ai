"""add task_name to bot

Revision ID: 1d8d301d00cf
Revises: 6d42576d6532
Create Date: 2025-08-19 16:37:26.647137

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1d8d301d00cf'
down_revision: Union[str, None] = '6d42576d6532'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('bots', sa.Column('task_name', sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column('bots', 'task_name')
