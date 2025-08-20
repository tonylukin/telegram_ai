from sqlalchemy.orm import Session

from app.models.tg_bot_message import TgBotMessage

def find_all(session: Session, limit: int = 50, offset: int = 0) -> list[TgBotMessage]:
    return session.query(TgBotMessage).limit(limit).offset(offset).all()
