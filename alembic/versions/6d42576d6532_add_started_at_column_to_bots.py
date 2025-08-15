"""add started_at column to bots

Revision ID: 6d42576d6532
Revises: 83d4a19fc99c
Create Date: 2025-08-14 19:50:43.268583

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6d42576d6532'
down_revision: Union[str, None] = '83d4a19fc99c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bots", sa.Column("started_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("bots", "started_at")
