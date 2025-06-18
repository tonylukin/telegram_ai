from telethon import TelegramClient
from app.configs.logger import logging
from telethon.types import User

async def get_user_by_username(client: TelegramClient, username: str) -> User|None:
    try:
        user = await client.get_entity(username)
        return user
    except Exception as e:
        logging.error(f"Error: {e}")
        return None
