from telethon import TelegramClient

from app.db.session import Session
from app.models.bot import Bot

session = Session()

def get_bot(client: TelegramClient = None, name: str = None) -> Bot:
    if client is not None:
        name = client.session.filename.split('.')[0]
    return session.query(Bot).filter_by(name=name).first()