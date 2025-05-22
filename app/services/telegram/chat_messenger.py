from telethon import TelegramClient
from telethon.tl.types import Channel, User
from telethon.tl.functions.contacts import SearchRequest
from telethon.tl.functions.messages import SendMessageRequest
from telethon.tl.functions.channels import GetParticipantsRequest, JoinChannelRequest
from telethon.tl.types import ChannelParticipantsSearch
import asyncio
from fastapi.params import Depends
from app.configs.logger import logging
import random

from app.db.queries.bot import get_bot
from app.db.queries.bot_comment import get_bot_comments
from app.db.session import Session
from app.models.bot_comment import BotComment
from app.services.telegram.chat_searcher import ChatSearcher
from app.services.telegram.clients_creator import ClientsCreator, get_telegram_clients_to_comment
from app.config import TELEGRAM_CHATS_TO_POST, AI_POST_TEXT_TO_CHANNELS
from app.services.text_maker import TextMakerDependencyConfig
from telethon.tl.types import ChannelParticipantSelf


class ChatMessenger:
    KNOWN_ANTISPAM_BOTS = {
        "combot", "grouphelpbot", "shieldy_bot", "banofbot", "rose", "spambot"
    }

    def __init__(
            self,
            clients_creator: ClientsCreator = Depends(get_telegram_clients_to_comment),
            chat_searcher: ChatSearcher = Depends(ChatSearcher),
            config: TextMakerDependencyConfig = Depends(TextMakerDependencyConfig),
    ):
        self.clients = []
        self.clients_creator = clients_creator
        self.chat_searcher = chat_searcher
        self.ai_client = config.ai_client
        self.session = Session()
        self.names = None
        self.message = None

    @staticmethod
    async def has_antispam_bot(chat: Channel, client: TelegramClient) -> bool:
        try:
            participants = await client(GetParticipantsRequest(
                channel=chat,
                filter=ChannelParticipantsSearch(""),
                offset=0,
                limit=100,
                hash=0
            ))

            for user in participants.users:
                if isinstance(user, User) and user.username:
                    uname = user.username.lower()
                    if uname in ChatMessenger.KNOWN_ANTISPAM_BOTS or any(bot in uname for bot in ChatMessenger.KNOWN_ANTISPAM_BOTS):
                        return True
        except Exception as e:
            logging.error(f"⚠️ Could not check for antispam bots in {chat.title}: {e}")
        return False

    @staticmethod
    async def is_user_in_group(client, chat):
        try:
            result = await client(GetParticipantsRequest(
                channel=chat,
                filter=ChannelParticipantSelf(),
                offset=0,
                limit=1,
                hash=0
            ))
            return bool(result.participants)
        except Exception as e:
            logging.error(f"⚠️ Не удалось проверить участие в {chat.title}: {e}")
            return False

    @staticmethod
    async def send_message(client: TelegramClient, chat: Channel, message: str) -> bool:
        try:
            await client(SendMessageRequest(
                peer=chat.id,
                message=message
            ))
            logging.info(f"✅ Sent message to {chat.title}")
            return True
        except Exception as e:
            logging.error(f"❌ Failed to send message to {chat.title}: {e}")
            return False

    async def send_messages_to_chats_by_names(self, message: str, names: list[str] = None) -> list[dict[str, int]]:
        self.names = names
        if self.names is None:
            self.names = TELEGRAM_CHATS_TO_POST
        self.message = message
        clients = await self.clients_creator.create_clients()
        return await asyncio.gather(*(self.__start_client(client) for client in clients))

    async def __start_client(self, client: TelegramClient) -> dict[str, dict[str, int]]:
        await client.start()
        logging.info(f"{client.session.filename} started")
        bot = get_bot(client)
        if bot is None:
            logging.error('Bot not found')
            return {}

        chats = []
        for name in self.names:
            try:
                chat = await client.get_entity(name)
                if isinstance(chat, Channel) and chat.megagroup:
                    chats.append(chat)
            except Exception as e:
                logging.error(f"{name}: {e}")

        message = AI_POST_TEXT_TO_CHANNELS.format(text=self.message)
        message = self.ai_client.generate_text(message)

        result = {}
        for chat in chats:
            comments = get_bot_comments(bot=bot, channel=chat.title)
            if len(comments) > 0:
                logging.info(f"{chat.title}: has recent comments")
                continue
            if await self.has_antispam_bot(chat=chat, client=client):
                logging.info(f"{chat.title} has antispam bot")
                continue
            if not await self.is_user_in_group(client, chat):
                logging.error(f"🚪 Not in chat. Joining {chat.title}")
                await client(JoinChannelRequest(chat))
            if await self.send_message(client=client, chat=chat, message=message):
                result[chat.title] = 1
                bot_comment = BotComment(
                    bot_id=bot.id,
                    comment=message,
                    channel=chat.title,
                )
                self.session.add(bot_comment)

            await asyncio.sleep(random.choice(range(10, 15)))

        try:
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            logging.error(e)
        finally:
            self.session.close()
        result = {client.session.filename: result}
        client.disconnect()
        logging.info(f"Messages sent: {result}")
        return result
