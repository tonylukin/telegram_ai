from app.db.session import Session as SQLAlchemySession
from sqlalchemy.orm import Session
from fastapi import Depends

def get_db() -> Session:
    db = SQLAlchemySession()
    try:
        return db
    finally:
        db.close()
