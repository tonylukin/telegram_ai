"""change post_id unique index in tg_leads

Revision ID: c7c456579697
Revises: 4e9e8a7f5810
Create Date: 2026-03-19 19:53:58.142397

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7c456579697'
down_revision: Union[str, None] = '4e9e8a7f5810'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ux_tg_leads_post_id", "tg_leads", type_="unique")

    op.create_unique_constraint(
        "ux_tg_leads_post_id_channel",
        "tg_leads",
        ["post_id", "channel"],
    )


def downgrade() -> None:
    op.drop_constraint("ux_tg_leads_post_id_channel", "tg_leads", type_="unique")

    op.create_unique_constraint(
        "ux_tg_leads_post_id",
        "tg_leads",
        ["post_id"],
    )
