import asyncio
from fastapi.params import Depends
from telethon.tl.types import Channel, PeerChannel
from telethon.tl.functions.messages import SendReactionRequest, GetDiscussionMessageRequest
from telethon.tl.types import ReactionEmoji
from telethon import TelegramClient
from app.config import TELEGRAM_USERS_TO_REACT
from app.services.telegram.chat_searcher import ChatSearcher
from app.services.telegram.clients_creator import ClientsCreator
from app.configs.logger import logging

def get_telegram_clients() -> ClientsCreator:
    return ClientsCreator(TELEGRAM_USERS_TO_REACT)

class ReactionSender:
    def __init__(self, clients_creator: ClientsCreator = Depends(get_telegram_clients), chat_searcher: ChatSearcher = Depends(ChatSearcher)):
        self.clients = []
        self.clients_creator = clients_creator
        self.chat_searcher = chat_searcher
        self.query = ''

    @staticmethod
    async def make_reactions_for_chat(client: TelegramClient, chat: Channel, reaction: str = "❤️"):
        try:
            logging.info(f"🧭 Sending reaction for: {chat.title}")
            messages = await client.get_messages(chat.id, limit=5)
            for message in messages:
                if message.sender_id == (await client.get_me()).id:
                    logging.warning('it is my post')
                    continue
                if not message.replies or not message.replies.replies:
                    logging.warning('No comments')
                    continue  # no comments
                try:
                    # entity = await client.get_entity(chat)
                    discussion = await client(GetDiscussionMessageRequest(
                        peer=chat,
                        msg_id=message.id
                    ))
                    discussion_chat = discussion.messages[0].peer_id.channel_id
                    discussion_peer = PeerChannel(discussion_chat)

                    comments = await client.get_messages(discussion_peer, limit=10)
                    for comment in comments:
                        if not comment.out:
                            try:
                                await client(SendReactionRequest(
                                    peer=discussion_peer,
                                    msg_id=comment.id,
                                    reaction=[ReactionEmoji(emoticon=reaction)]
                                ))
                                logging.info(f"❤️ Reacted to comment {comment.id} in {chat.title}")
                            except Exception as e:
                                logging.error(f"⚠️ Failed to react to comment: {e}")
                except Exception as e:
                    logging.error(f"⚠️ Could not send reaction: {e}")
        except Exception as e:
            logging.error(f"❌ Chat {chat.title} error: {e}")

        client.disconnect()

    async def search_chats(self, client: TelegramClient):
        chats = await self.chat_searcher.search_chats(client, self.query)
        logging.info(f"Found {len(chats)} chats")
        for chat in chats:
            await self.make_reactions_for_chat(client=client, chat=chat)

    async def start_client(self, client: TelegramClient):
        await client.start()
        logging.info(f"{client.session.filename} started")
        await self.search_chats(client)

    async def send_reactions(self, query: str):
        self.query = query
        clients = await self.clients_creator.create_clients()
        await asyncio.gather(*(self.start_client(client) for client in clients))
        # await asyncio.gather(*(client.run_until_disconnected() for client in self.clients))
