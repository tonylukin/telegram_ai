from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship
from app.models.base import Base


class TgPostReaction(Base):
    __tablename__ = "tg_post_reactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    channel = Column(String(128), nullable=False)
    post_id = Column(Integer, nullable=False)
    reaction = Column(String(16), nullable=False)
    bot_id = Column(Integer, ForeignKey("bots.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    sender_name = Column(String, nullable=True, default=None)

    bot = relationship("Bot", back_populates="reactions")

    __table_args__ = (
        UniqueConstraint("post_id", "channel", "bot_id", name="uq_tg_post_reactions_post_id_channel_bot_id"),
    )
