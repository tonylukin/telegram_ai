from sqlalchemy import Column, BigInteger, String, DateTime, func
from app.models.base import Base

class NewsPost(Base):
    __tablename__ = "news_posts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    external_id = Column(String, nullable=False, unique=True, index=True)
    original_text = Column(String, nullable=False)
    generated_text = Column(String, nullable=False)
    person = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
