from typing import List

from fastapi.params import Depends
from sqlalchemy.orm import Session
from telethon import TelegramClient

from app.db.queries.bot import get_bots
from app.dependencies import get_db
from app.models.bot import Bot

class BotClient:
    def __init__(self, client: TelegramClient, bot: Bot):
        self.client = client
        self.bot = bot

    def get_name(self):
        return self.bot.name

class ClientsCreator:
    def __init__(self, session: Session = Depends(get_db)):
        self.session = session

    def create_clients_from_bots(self, roles: list[str] = None) -> List[BotClient]:
        bots = get_bots(session=self.session, roles=roles)
        clients = []
        for bot in bots:
            api_id = bot.app_id
            api_hash = bot.app_token
            session = bot.name
            client = TelegramClient(api_id=api_id, api_hash=api_hash, session=f"sessions/{session}")
            clients.append(BotClient(client, bot))

        return clients

def get_bot_roles_to_react() -> list[str]:
    return [Bot.ROLE_REACT]

def get_bot_roles_to_comment() -> list[str]:
    return [Bot.ROLE_POST]

def get_bot_roles_to_invite() -> list[str]:
    return [Bot.ROLE_INVITE]

def get_bot_roles_for_human_scanner() -> list[str]:
    return [Bot.ROLE_HUMAN_SCANNER]
