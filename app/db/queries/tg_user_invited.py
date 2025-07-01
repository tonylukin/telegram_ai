from app.db.session import Session
from app.models.tg_user_invited import TgUserInvited

def get_invited_users(session: Session, tg_user_id: int, channel: str) -> TgUserInvited|None:
    return session.query(TgUserInvited).filter_by(tg_user_id=tg_user_id, channel=channel).first()
