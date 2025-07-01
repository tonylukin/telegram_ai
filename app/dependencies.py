from app.db.session import Session
from fastapi import Depends

def get_db() -> Session:
    db = Session()
    try:
        return db
    finally:
        db.close()
