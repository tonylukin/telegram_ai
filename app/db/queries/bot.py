from telethon import TelegramClient
from sqlalchemy import cast
from sqlalchemy.dialects.postgresql import ARRAY, VARCHAR

from app.db.session import Session
from app.models.bot import Bot

def get_bot(session: Session, client: TelegramClient = None, name: str = None) -> Bot:
    if client is not None:
        name = client.session.filename.removeprefix('sessions/').split('.')[0]
    return session.query(Bot).filter_by(name=name).first()

def get_bots(session: Session, roles: list[str] = None) -> list[Bot]:
    query = session.query(Bot)

    if roles:
        query = query.filter(Bot.roles.op("&&")(cast(roles, ARRAY(VARCHAR))))

    return query.all()
