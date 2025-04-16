"""add unique index to external_id

Revision ID: 873d3dd90d1a
Revises: 0280802401d9
Create Date: 2025-04-14 22:53:14.859711

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '873d3dd90d1a'
down_revision: Union[str, None] = '0280802401d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(op.f('ux_news_posts_external_id'), 'news_posts', ['external_id'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ux_news_posts_external_id', table_name='news_posts')
