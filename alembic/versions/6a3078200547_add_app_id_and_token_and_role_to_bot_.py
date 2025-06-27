"""add app id and token and role to bot table

Revision ID: 6a3078200547
Revises: 6c7eeb1be6ed
Create Date: 2025-06-24 18:08:41.677322

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '6a3078200547'
down_revision: Union[str, None] = '6c7eeb1be6ed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('bots', sa.Column('app_id', sa.Integer(), nullable=True))
    op.add_column('bots', sa.Column('app_token', sa.String(length=32), nullable=True))
    op.add_column('bots', sa.Column('roles', postgresql.ARRAY(sa.String()), nullable=True))


def downgrade() -> None:
    op.drop_column('bots', 'roles')
    op.drop_column('bots', 'app_token')
    op.drop_column('bots', 'app_id')
