from sqlalchemy import Column, Integer, String, DateTime, func, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from app.models.base import Base

class Bot(Base):
    __tablename__ = "bots"
    __table_args__ = (
        Index('ux_bots_name', 'name'),
    )

    id = Column(Integer, primary_key=True)
    name = Column(String(64), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    comments = relationship("BotComment", back_populates="bot", lazy="selectin")
