from sqlalchemy.orm import Session

from app.models.ig_user import IgUser

def get_ig_user_by_username(session: Session, username: str) -> IgUser | None:
    return session.query(IgUser).filter_by(username=username).first()
