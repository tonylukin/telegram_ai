"""add phone_number to bots

Revision ID: 130d878b4e64
Revises: 9159f9b9570c
Create Date: 2025-08-11 22:25:18.489273

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '130d878b4e64'
down_revision: Union[str, None] = '9159f9b9570c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('bots', sa.Column('phone_number', sa.String(length=15)))


def downgrade() -> None:
    op.drop_column('bots', 'phone_number')
