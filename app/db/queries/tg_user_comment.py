from sqlalchemy.orm import Session

from app.models.tg_user_comment import TgUserComment


def get_user_comments(session: Session, tg_user_id: int) -> list[type[TgUserComment]]:
    return session.query(TgUserComment).filter_by(user_id=tg_user_id).all()
