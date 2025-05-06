import asyncio
import random

from fastapi.params import Depends
from telethon.tl.types import Channel, PeerChannel
from telethon.tl.functions.messages import SendReactionRequest
from telethon.tl.types import ReactionEmoji
from telethon import TelegramClient
from app.config import TELEGRAM_USERS_TO_REACT
from app.services.telegram.chat_searcher import ChatSearcher
from app.services.telegram.clients_creator import ClientsCreator
from app.configs.logger import logging

def get_telegram_clients() -> ClientsCreator:
    return ClientsCreator(TELEGRAM_USERS_TO_REACT)

class ReactionSender:
    MAX_REACTIONS_PER_CHAT = 5
    MAX_MESSAGES_PER_CHAT = 100
    REACTIONS = ["❤️"]

    def __init__(self, clients_creator: ClientsCreator = Depends(get_telegram_clients), chat_searcher: ChatSearcher = Depends(ChatSearcher)):
        self.clients = []
        self.clients_creator = clients_creator
        self.chat_searcher = chat_searcher
        self.query = None
        self.reaction = None

    async def send_reactions_to_my_chats(self, client: TelegramClient) -> dict[str, dict[str, int]]:
        me = await client.get_me()
        dialogs = await client.get_dialogs()
        logging.info(f"Dialogs found: {len(dialogs)}")
        counter = {}

        for dialog in dialogs:
            current_chat_reactions_count = 0
            entity = dialog.entity
            if not hasattr(entity, 'megagroup') and not hasattr(entity, 'broadcast'):
                continue  # Skip usual chats

            logging.info(f"📥 Processing chat: {entity.title}")
            reaction = self.reaction if self.reaction is not None else random.choice(self.REACTIONS)
            try:
                messages = await client.get_messages(entity, limit=self.MAX_MESSAGES_PER_CHAT)
                for message in messages:
                    if current_chat_reactions_count == self.MAX_REACTIONS_PER_CHAT:
                        break

                    if message.sender_id == me.id:
                        continue

                    if random.choice(range(int(self.MAX_MESSAGES_PER_CHAT / self.MAX_REACTIONS_PER_CHAT * 2))) > 0:
                        continue

                    await asyncio.sleep(min(current_chat_reactions_count, 1) * 30)  # DELAY!!!
                    await client(SendReactionRequest(
                        peer=entity,
                        msg_id=message.id,
                        reaction=[ReactionEmoji(emoticon=reaction)]
                    ))
                    current_chat_reactions_count += 1
                    logging.info(f"Reacted to comment {message.id} in {entity.title}")
                    counter[entity.title] = counter.get(entity.title, 0) + 1

            except Exception as e:
                logging.error(f"⚠️ Failed to react {reaction} to comment {entity.title}: {e}")

        return {client.session.filename: counter}

    async def make_reactions_for_chat(self, client: TelegramClient, chat: Channel) -> dict[str, dict[str, int]]:
        counter = {}
        try:
            logging.info(f"🧭 Sending reaction for: {chat.title}")
            messages = await client.get_messages(chat.id, limit=5)
            for message in messages:
                if message.sender_id == (await client.get_me()).id:
                    logging.warning('it is my post')
                    continue

                reaction = self.reaction if self.reaction is not None else random.choice(self.REACTIONS)
                try:
                    discussion_peer = PeerChannel(chat.id)

                    comments = await client.get_messages(discussion_peer, limit=5)
                    for comment in comments:
                        if comment.out:
                            continue

                        try:
                            await client(SendReactionRequest(
                                peer=discussion_peer,
                                msg_id=comment.id,
                                reaction=[ReactionEmoji(emoticon=reaction)]
                            ))
                            logging.info(f"Reacted to comment {comment.id} in {chat.title}")
                            counter[chat.title] = counter.get(chat.title, 0) + 1
                        except Exception as e:
                            logging.error(f"⚠️ Failed to react {reaction}: {e}")
                except Exception as e:
                    logging.error(f"⚠️ Could not send reaction: {e}")
        except Exception as e:
            logging.error(f"❌ Chat {chat.title} error: {e}")

        return {client.session.filename: counter}

    async def search_chats(self, client: TelegramClient) -> dict[str, dict[str, int]]:
        chats = await self.chat_searcher.search_chats(client, self.query)
        logging.info(f"Found {len(chats)} chats")
        result = {}
        for chat in chats:
            result.update(await self.make_reactions_for_chat(client=client, chat=chat))

        return result

    async def start_client(self, client: TelegramClient) -> dict[str, dict[str, int]]:
        await client.start()
        logging.info(f"{client.session.filename} started")
        if self.query is not None:
            result = await self.search_chats(client)
        else:
            result = await self.send_reactions_to_my_chats(client=client)

        client.disconnect()
        logging.info(f"Reactions found: {result}")
        return result

    async def send_reactions(self, query: str = None, reaction: str = None) -> list[dict[str, int]]:
        self.query = query
        self.reaction = reaction
        clients = await self.clients_creator.create_clients()
        return await asyncio.gather(*(self.start_client(client) for client in clients))
        # await asyncio.gather(*(client.run_until_disconnected() for client in self.clients))
