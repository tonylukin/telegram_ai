from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import DATABASE_URL
import app.models

engine = create_engine(
    DATABASE_URL,
    isolation_level="AUTOCOMMIT"
)
Session = sessionmaker(bind=engine)
