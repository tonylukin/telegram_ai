from sqlalchemy import Column, Text, String, DateTime, func, Integer, ForeignKey
from sqlalchemy.orm import relationship

from app.models.base import Base


class TgBotMessage(Base):
    __tablename__ = "tg_bot_messages"

    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey("bots.id"), nullable=False, index=True)
    sender_name = Column(String, nullable=False)
    text = Column(Text)
    reply_text = Column(Text)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationship to Bot model
    bot = relationship("Bot")