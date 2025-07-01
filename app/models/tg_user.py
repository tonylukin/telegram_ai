from sqlalchemy import (
    Column, BigInteger, Integer, String, JSON, Text, DateTime, ForeignKey, Index, UniqueConstraint, func
)
from app.models.base import Base

class TgUser(Base):
    __tablename__ = "tg_users"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tg_id = Column(BigInteger, nullable=False)
    nickname = Column(String, nullable=True)
    description = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, nullable=True, onupdate=func.now(), default=func.now())

    __table_args__ = (
        Index("ix_tg_users_nickname", "nickname"),
        UniqueConstraint('tg_id', 'nickname', name="ux_tg_users_tg_id_nickname"),
    )
