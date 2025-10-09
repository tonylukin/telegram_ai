from sqlalchemy import (
    Column, Integer, String, Text, DateTime, func, ForeignKey
)
from sqlalchemy.orm import relationship

from app.models.base import Base


class TgLead(Base):
    __tablename__ = "tg_leads"

    id = Column(Integer, primary_key=True, index=True)
    channel = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    answer = Column(Text, nullable=True)
    post_id = Column(Integer, nullable=False)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    bot = relationship("Bot")
