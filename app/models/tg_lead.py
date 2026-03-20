from sqlalchemy import (
    Column, Integer, String, Text, DateTime, func, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship

from app.models.base import Base


class TgLead(Base):
    REACTION_LIKE = 1
    REACTION_DISLIKE = -1
    __tablename__ = "tg_leads"

    id = Column(Integer, primary_key=True, index=True)
    channel = Column(String, nullable=False)
    message = Column(Text, nullable=False, index=True)
    answer = Column(Text, nullable=True)
    post_id = Column(Integer, nullable=False, index=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    workflow = Column(String, nullable=False)
    reaction = Column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("post_id", "channel", name="ux_tg_leads_post_id_channel"),
    )

    bot = relationship("Bot")
