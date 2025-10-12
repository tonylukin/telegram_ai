from sqlalchemy import Column, Integer, String, DateTime, func, Index, ARRAY
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import relationship

from app.models.base import Base


class Bot(Base):
    ROLE_SUPER_ADMIN = 'super_admin'
    ROLE_POST = 'post'
    ROLE_INVITE = 'invite'
    ROLE_REACT = 'react'
    ROLE_HUMAN_SCANNER = 'human_scanner'
    ROLE_LEAD_FROM_CHANNEL = 'lead_from_channel'
    ROLE_HEALTH_CHECK = 'health_check'

    STATUS_BUSY = 'busy'

    __tablename__ = "bots"
    __table_args__ = (
        Index('ux_bots_name', 'name'),
    )

    id = Column(Integer, primary_key=True)
    name = Column(String(64), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    app_id = Column(Integer, nullable=True)
    app_token = Column(String(32), nullable=True)
    roles = Column(MutableList.as_mutable(ARRAY(String)), nullable=True)
    status = Column(String, nullable=True)
    phone_number = Column(String(15), nullable=True)
    started_at = Column(DateTime)
    task_name = Column(String(32), nullable=True)

    comments = relationship("BotComment", back_populates="bot", lazy="selectin")
