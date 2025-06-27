from typing import List

from telethon import TelegramClient

from app.db.queries.bot import get_bots
from app.models.bot import Bot


class ClientsCreator:
    def __init__(self, roles: list[str] = None):
        self.bots = get_bots(roles)
        # self.bots = list(filter(lambda bot: bot.id == 4, self.bots)) #todo remove

    def create_clients_from_bots(self) -> List[TelegramClient]:
        clients = []
        for bot in self.bots:
            api_id = bot.app_id
            api_hash = bot.app_token
            session = bot.name
            client = TelegramClient(api_id=api_id, api_hash=api_hash, session=session)
            clients.append(client)

        return clients

def get_telegram_clients_to_react() -> ClientsCreator:
    return ClientsCreator([Bot.ROLE_REACT])

def get_telegram_clients_to_comment() -> ClientsCreator:
    return ClientsCreator([Bot.ROLE_POST, Bot.ROLE_INVITE])

def get_telegram_clients_to_invite() -> ClientsCreator:
    return ClientsCreator([Bot.ROLE_POST, Bot.ROLE_INVITE])

def get_telegram_clients_for_human_scanner() -> ClientsCreator:
    return ClientsCreator([Bot.ROLE_HUMAN_SCANNER])
