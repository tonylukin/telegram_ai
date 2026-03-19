"""add_reaction_to_tg_leads_table

Revision ID: 4e9e8a7f5810
Revises: 53e8f4406f11
Create Date: 2026-03-18 19:54:01.707743

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '4e9e8a7f5810'
down_revision: Union[str, None] = '53e8f4406f11'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tg_leads",
        sa.Column("reaction", sa.SmallInteger(), nullable=True)
    )
    op.add_column(
        "tg_leads",
        sa.Column("workflow", sa.String(), nullable=True)
    )

    op.create_index(
        "ix_tg_leads_message",
        "tg_leads",
        ["message"],
        unique=False,
    )


def downgrade() -> None:
    # Drop index
    op.drop_index('ix_tg_leads_message', 'tg_leads')

    # Drop column
    op.drop_column("tg_leads", "workflow")
    op.drop_column("tg_leads", "reaction")
