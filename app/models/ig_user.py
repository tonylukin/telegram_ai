from sqlalchemy import Column, BigInteger, String, JSON, DateTime, func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class IgUser(Base):
    __tablename__ = "ig_users"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    username = Column(String, nullable=False, unique=True, index=True)
    description = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
