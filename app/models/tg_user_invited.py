from sqlalchemy import (
    Column, BigInteger, Integer, String, Text, DateTime, ForeignKey, Index, UniqueConstraint, func
)
from app.models.base import Base

class TgUserInvited(Base):
    __tablename__ = "tg_users_invited"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tg_user_id = Column(BigInteger, nullable=False)
    channel = Column(String(128), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    tg_username = Column(String, nullable=True)
    channel_from = Column(String, nullable=True)
    bot_id = Column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint('tg_user_id', 'channel', name="ux_tg_users_invited_tg_user_id_channel"),
    )
