from app.db.session import Session as SQLAlchemySession
from sqlalchemy.orm import Session
from fastapi import Depends

def get_db():
    db = SQLAlchemySession()
    try:
        yield db
    finally:
        db.close()
