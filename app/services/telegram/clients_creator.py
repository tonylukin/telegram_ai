import sqlite3
import asyncio
from datetime import datetime
from typing import List

from fastapi.params import Depends
from sqlalchemy.orm import Session
from telethon import TelegramClient

from app.configs.logger import logger
from app.db.queries.bot import get_bots
from app.dependencies import get_db
from app.models.bot import Bot

class BotClient:
    def __init__(self, client: TelegramClient, bot: Bot):
        self.client = client
        self.bot = bot
        self.bot_name = bot.name

    def get_name(self):
        return self.bot_name

class ClientsCreator:
    def __init__(self, session: Session = Depends(get_db)):
        self.session = session

    def create_clients_from_bots(self, roles: list[str] = None, names: list[str] = None, limit: int = None) -> List[BotClient]:
        bots = get_bots(session=self.session, roles=roles, names=names, limit=limit)
        clients = []
        for bot in bots:
            api_id = bot.app_id
            api_hash = bot.app_token
            session = bot.name
            client = TelegramClient(api_id=api_id, api_hash=api_hash, session=f"sessions/{session}")
            clients.append(BotClient(client, bot))

        return clients

    async def start_client(self, bot_client: BotClient):
        try:
            if not bot_client.client.is_connected():
                await bot_client.client.start()
            bot_client.bot.status = Bot.STATUS_BUSY
            bot_client.bot.started_at = datetime.now()
            self.session.flush()

        except Exception as e:
            logger.error(f"Could not start client [{bot_client.get_name()}] {e}")
            if bot_client.client.is_connected():
                await bot_client.client.disconnect()
            raise RuntimeError("Could not start client")

    async def disconnect_client(self, bot_client: BotClient):
        for _ in range(3):
            try:
                if bot_client.client.is_connected():
                    await bot_client.client.disconnect()
                if bot_client.bot.status is not None:
                    bot_client.bot.status = None
                    bot_client.bot.started_at = None
                    self.session.flush()

                break
            except sqlite3.OperationalError as e:
                logger.error(f"Could not disconnect client {e}")
                await asyncio.sleep(2)
        else:
            raise RuntimeError("Could not disconnect client after retries")

def get_bot_roles_to_react() -> list[str]:
    return [Bot.ROLE_REACT]

def get_bot_roles_to_comment() -> list[str]:
    return [Bot.ROLE_POST]

def get_bot_roles_to_invite() -> list[str]:
    return [Bot.ROLE_INVITE]

def get_bot_roles_for_human_scanner() -> list[str]:
    return [Bot.ROLE_HUMAN_SCANNER]
