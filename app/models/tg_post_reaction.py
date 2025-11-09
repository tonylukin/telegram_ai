from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    func,
    ARRAY
)
from sqlalchemy.ext.mutable import MutableList
from app.models.base import Base


class TgPostReaction(Base):
    __tablename__ = "tg_post_reactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    channel = Column(String(128), nullable=False)
    post_id = Column(Integer, nullable=False)
    reactions = Column(MutableList.as_mutable(ARRAY(String)), nullable=True)
    bot_ids = Column(MutableList.as_mutable(ARRAY(Integer)), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    sender_name = Column(String, nullable=True, default=None)

    __table_args__ = (
        UniqueConstraint("post_id", "channel", name="uq_tg_post_reactions_post_id_channel"),
    )
