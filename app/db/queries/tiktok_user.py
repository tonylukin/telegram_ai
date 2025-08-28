from sqlalchemy.orm import Session
from app.models.tiktok_user import TikTokUser


def get_tiktok_user_by_username(session: Session, username: str) -> TikTokUser | None:
    return session.query(TikTokUser).filter_by(username=username).first()
