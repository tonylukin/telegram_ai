from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, func, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from app.models.base import Base

class BotComment(Base):
    __tablename__ = "bot_comments"
    __table_args__ = (
        Index('ix_bot_comments_channel', 'channel'),
    )

    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey("bots.id"), nullable=False)
    comment = Column(Text, nullable=False)
    channel = Column(String(64), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

BotComment.bot = relationship("Bot", back_populates="comments")
