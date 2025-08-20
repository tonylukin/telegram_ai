from sqlalchemy import (
    Column, BigInteger, Integer, String, Text, DateTime, ForeignKey, Index, UniqueConstraint, func
)
from sqlalchemy.orm import relationship

from app.models.base import Base

class TgUserComment(Base):
    __tablename__ = "tg_user_comments"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("tg_users.id"), nullable=False, index=True)
    comment = Column(Text, nullable=False)
    channel = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    tg_user = relationship("TgUser", back_populates="comments")

    __table_args__ = (
        Index("ix_tg_user_comments_user_id", "user_id"),
    )
