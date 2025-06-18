from telethon import TelegramClient
from typing import List
from app.config import TELEGRAM_USERS_TO_REACT, TELEGRAM_USERS_TO_COMMENT, TELEGRAM_USERS_TO_INVITE


class ClientsCreator:
    def __init__(self, user_configs: List[dict]):
        self.user_configs = user_configs

    async def create_clients(self) -> List[TelegramClient]:
        clients = []
        for user_config in self.user_configs:
            api_id = int(user_config[0])
            api_hash = user_config[1]
            session = user_config[2]
            client = TelegramClient(api_id=api_id, api_hash=api_hash, session=session)
            clients.append(client)

        return clients

def get_telegram_clients_to_react() -> ClientsCreator:
    return ClientsCreator(TELEGRAM_USERS_TO_REACT)

def get_telegram_clients_to_comment() -> ClientsCreator:
    return ClientsCreator(TELEGRAM_USERS_TO_COMMENT)

def get_telegram_clients_to_invite() -> ClientsCreator:
    return ClientsCreator(TELEGRAM_USERS_TO_INVITE)