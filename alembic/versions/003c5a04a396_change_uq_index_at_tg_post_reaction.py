"""change_uq_index_at_tg_post_reaction

Revision ID: 003c5a04a396
Revises: 8b05799aa604
Create Date: 2025-10-25 16:08:54.552079

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003c5a04a396'
down_revision: Union[str, None] = '8b05799aa604'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_tg_post_reactions_post_id_bot_id",
        "tg_post_reactions",
        type_="unique",
    )

    op.create_unique_constraint(
        "uq_tg_post_reactions_post_id_channel_bot_id",
        "tg_post_reactions",
        ["post_id", "channel", "bot_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_tg_post_reactions_post_id_channel_bot_id",
        "tg_post_reactions",
        type_="unique",
    )

    op.create_unique_constraint(
        "uq_tg_post_reactions_post_id_bot_id",
        "tg_post_reactions",
        ["post_id", "bot_id"],
    )
