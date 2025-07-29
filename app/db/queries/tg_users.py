from sqlalchemy.orm import Session

from app.models.tg_user import TgUser

def get_user_by_id(session: Session, tg_user_id: int) -> TgUser | None:
    return session.query(TgUser).filter_by(tg_id=tg_user_id).first()
