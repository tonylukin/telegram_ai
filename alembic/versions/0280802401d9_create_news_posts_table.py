"""create news_posts table

Revision ID: 0280802401d9
Revises: 
Create Date: 2025-04-12 17:31:30.667751

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0280802401d9'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade():
    op.create_table(
        'news_posts',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('external_id', sa.String(length=64), nullable=False),
        sa.Column('original_text', sa.Text, nullable=False),
        sa.Column('generated_text', sa.Text, nullable=False),
        sa.Column('person', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('now()'), nullable=False)
    )


def downgrade():
    op.drop_table('news_posts')
