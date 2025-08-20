from sqlalchemy.orm import Session

from app.models.tg_user import TgUser

def get_user_by_id(session: Session, tg_user_id: int) -> TgUser | None:
    return session.query(TgUser).filter_by(tg_id=tg_user_id).first()

def find_all(session: Session, limit: int = 50, offset: int = 0) -> list[TgUser]:
    return session.query(TgUser).limit(limit).offset(offset).all()
