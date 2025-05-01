import asyncio
import random
from fastapi.params import Depends
from telethon import TelegramClient, events
from app.configs.logger import logging
from telethon.tl.functions.messages import GetDiscussionMessageRequest
from telethon.tl.types import PeerChannel
from app.config import TELEGRAM_CHANNELS_TO_COMMENT, TELEGRAM_USERS_TO_COMMENT
from app.services.ai.ai_client_base import AiClientBase
from app.services.ai.gemini_client import GeminiClient
from app.config import AI_COMMENT_TEXT, AI_COMMENT_TEXT_LINK
from app.services.telegram.clients_creator import ClientsCreator

def get_ai_client() -> AiClientBase:
    return GeminiClient()

def get_telegram_clients() -> ClientsCreator:
    return ClientsCreator(TELEGRAM_USERS_TO_COMMENT)

class ChannelMessageSender:
    def __init__(self, ai_client: AiClientBase = Depends(get_ai_client), clients_creator: ClientsCreator = Depends(get_telegram_clients)):
        self.ai_client = ai_client
        self.channels_configs = TELEGRAM_CHANNELS_TO_COMMENT
        self.clients_creator = clients_creator

    async def start_messaging(self):
        clients = await self.clients_creator.create_clients()
        await asyncio.gather(*(self.start_client(client) for client in clients))
        await asyncio.gather(*(client.run_until_disconnected() for client in clients))

    async def start_client(self, client: TelegramClient):
        await client.start()
        channel_usernames = list(self.channels_configs.keys())
        logging.info(f"✅ Started client: {client.session} for channels: {channel_usernames}")

        @client.on(events.NewMessage(chats=channel_usernames))
        async def handler(event):
            if not event.message:
                logging.warning("📭 Event with no message")
                return

            sender = await event.get_chat()
            channel_name = sender.username
            channel_config = self.channels_configs.get(channel_name)
            probability = channel_config.get('probability', 1)
            if probability < 1 and random.choice(range(1, 101)) <= int(probability * 100):
                logging.info(f"Channel {channel_name} probability is {probability} - missing this comment")
                return

            if channel_config.get('off', False):
                logging.info(f"Channel {channel_name} switched off")
                return

            await asyncio.sleep(random.choice(range(30, 90))) #DELAY!!!
            post_id = event.id
            logging.info(f"📌 New post: {post_id} [@{channel_name}] config: {channel_config}")
            replies = event.message.replies
            if replies and replies.comments and replies.channel_id:
                try:
                    discussion = await client(GetDiscussionMessageRequest(
                        peer=event.message.peer_id,
                        msg_id=post_id
                    ))

                    discussion_msg = discussion.messages[0]
                    group_id = discussion.chats[0].id
                    link = ''
                    if channel_config.get("link", False) and random.choice(range(4)) == 0:
                        link = AI_COMMENT_TEXT_LINK
                    comment_text = self.ai_client.generate_text(AI_COMMENT_TEXT.format(text=discussion_msg.message + link))

                    logging.info(f"🗨️ Assigned group: {group_id}[@{channel_name}], message: {discussion_msg.message}")

                    await client.send_message(
                        entity=PeerChannel(group_id),
                        message=comment_text,
                        reply_to=discussion_msg.id
                    )
                    logging.info(f"✅ Comment sent to {group_id}[@{channel_name}]: {comment_text}")
                except Exception as e:
                    logging.error(f"❌ Sending comment error: {e}")
            else:
                logging.info("❌ Comments off or no assigned group")

        self.clients.append(client)

    # async def can_send_messages(self, client: TelegramClient, chat_id: int) -> bool:
    #     try:
    #         # Пробуем получить свои права в чате
    #         full_chat = await client(GetFullChannelRequest(PeerChannel(chat_id)))
    #         rights = full_chat.full_chat.participants.participants
    #
    #         me = await client.get_me()
    #         for p in rights:
    #             if getattr(p, "user_id", None) == me.id:
    #                 # Проверяем, не мут/бан
    #                 banned_rights = getattr(p, "banned_rights", None)
    #                 if banned_rights:
    #                     logging.info(f"🔒 У пользователя запрет: {banned_rights}")
    #                     return False
    #                 return True
    #     except Exception as e:
    #         logging.error(f"❌ Ошибка при проверке прав: {e}")
    #         return False
