import asyncio
import csv
import os
import random

from fastapi.params import Depends
from sqlalchemy.orm import Session
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import GetDiscussionMessageRequest
from telethon.tl.types import Channel, PeerChannel

from app.config import TELEGRAM_CHATS_TO_POST, AI_POST_TEXT_TO_CHANNELS, AI_POST_TEXT_TO_CHANNELS_NO_MESSAGE, \
    CHAT_MESSENGER_DEFAULT_CHANNELS_LIST_CSV_PATH
from app.configs.logger import logger
from app.db.queries.bot_comment import get_bot_comments
from app.dependencies import get_db, get_ai_client
from app.models.bot_comment import BotComment
from app.services.ai.ai_client_base import AiClientBase
from app.services.telegram.chat_searcher import ChatSearcher
from app.services.telegram.clients_creator import ClientsCreator, get_bot_roles_to_comment, BotClient
from app.services.telegram.helpers import is_user_in_group, get_chat_from_channel


class ChatMessenger:
    BOT_LIMIT = 4
    MAX_CHANNELS_PER_BOT = 5

    def __init__(
            self,
            clients_creator: ClientsCreator = Depends(),
            chat_searcher: ChatSearcher = Depends(ChatSearcher),
            ai_client: AiClientBase = Depends(get_ai_client),
            session: Session = Depends(get_db)
    ):
        self._clients = []
        self._clients_creator = clients_creator
        self._chat_searcher = chat_searcher
        self._ai_client = ai_client
        self._session = session
        self._chat_names = None
        self._messages = None

    @staticmethod
    async def send_message(bot_client: BotClient, chat: Channel | PeerChannel, message: str, reply_to_post_id: int | None) -> bool:
        try:
            client = bot_client.client
            entity = await client.get_entity(chat)
            await client.send_message(
                entity=entity,
                message=message,
                reply_to=reply_to_post_id
            )
            logger.info(f"[ChatMessenger::send_message][{bot_client.get_name()}] ✅ Sent message to {chat.title}")
            return True
        except Exception as e:
            logger.warning(f"[ChatMessenger::send_message][{bot_client.get_name()}] ❌ Failed to send message to {chat.title}: {e}")
            return False

    async def send_messages_to_chats_by_names(self, messages: list[str] = None, names: list[str] = None, bot_roles: list[str] = None) -> list[dict[str, int]]:
        self._chat_names = names
        if self._chat_names is None:
            names_from_csv = self.__get_names_from_csv()
            self._chat_names = names_from_csv if names_from_csv else TELEGRAM_CHATS_TO_POST
        self._messages = messages
        bot_clients = self._clients_creator.create_clients_from_bots(roles=bot_roles if bot_roles else get_bot_roles_to_comment(), limit=self.BOT_LIMIT)
        if len(bot_clients) == 0:
            raise Exception('No bots found')

        chat_names = self._chat_names[:]
        random.shuffle(chat_names)
        k, m = divmod(len(chat_names), len(bot_clients))
        return await asyncio.gather(
            *(self.__start_client(client, chat_names[i * k + min(i, m):(i + 1) * k + min(i + 1, m)]) for i, client in
              enumerate(bot_clients))
        )

    async def __start_client(self, bot_client: BotClient, chat_names: list[str]) -> dict[str, dict[str, int]]:
        client = bot_client.client
        await self._clients_creator.start_client(bot_client, task_name='send_messages_to_chats_by_names')
        logger.info(f"[ChatMessenger::__start_client] {bot_client.get_name()} started")

        bot = bot_client.bot

        chats = []
        post_texts = {}
        for name in chat_names[:self.MAX_CHANNELS_PER_BOT]:
            try:
                chat = await client.get_entity(name)
                if not isinstance(chat, Channel):
                    logger.info(f"[ChatMessenger::__start_client][{bot_client.get_name()}] {name}: Not a Channel")
                    continue

                last_messages = [message for message in await client.get_messages(chat.id, limit=10) if message.message]
                post_text_data = (chat.title, None)
                random_message = None
                if last_messages:
                    random_message = random.choice(last_messages)
                    post_text_data = (random_message.message, random_message.id)

                linked_chat_id = await get_chat_from_channel(client, chat)
                if linked_chat_id is None or isinstance(linked_chat_id, Channel):
                    chats.append(chat)
                    post_texts[chat.id] = post_text_data
                    continue

                if isinstance(linked_chat_id, int) and random_message:
                    # emulate discussion (linked) chat with parent title and id
                    linked_chat = PeerChannel(int(linked_chat_id))
                    linked_chat.title = chat.title
                    linked_chat.id = chat.id
                    chats.append(linked_chat)
                    discussion = await client(GetDiscussionMessageRequest(
                        peer=chat,
                        msg_id=random_message.id
                    ))

                    discussion_msg = random.choice(discussion.messages)
                    post_texts[linked_chat.id] = (discussion_msg.message, discussion_msg.id)

            except Exception as e:
                logger.error(f"[ChatMessenger::__start_client][{bot_client.get_name()}] {name}: {e}")

        result = {}
        for chat in chats:
            try:
                comments = get_bot_comments(self._session, channel=chat.title, bot=bot_client.bot)
                if len(comments) > 0:
                    logger.info(f"[ChatMessenger::__start_client][{bot_client.get_name()}] {chat.title}: {bot_client.get_name()} has recent comments")
                    continue
                # if await has_antispam_bot(chat=chat, client=client):
                #     logger.info(f"{chat.title} has antispam bot")
                #     continue
                if not await is_user_in_group(client, chat):
                    logger.info(f"[ChatMessenger::__start_client][{bot_client.get_name()}] 🚪 Not in chat. Joining {chat.title}")
                    await client(JoinChannelRequest(chat))
                    await asyncio.sleep(120) # before sending the first message let's wait 2 minutes

                (post_text, post_id) = post_texts[chat.id]
                if self._messages is None: # todo add emotions
                    prompt = AI_POST_TEXT_TO_CHANNELS_NO_MESSAGE.format(post=post_text)
                else:
                    prompt = AI_POST_TEXT_TO_CHANNELS.format(text=random.choice(self._messages), post=post_text)
                message = self._ai_client.generate_text(prompt)
                if await self.send_message(bot_client=bot_client, chat=chat, message=message, reply_to_post_id=post_id):
                    result[chat.title] = 1
                    bot_comment = BotComment(
                        bot_id=bot.id,
                        comment=message,
                        channel=chat.title if len(chat.title) <= 64 else chat.title[:61] + '...',
                    )
                    self._session.add(bot_comment)

                await asyncio.sleep(random.choice(range(10, 15)))
            except Exception as e:
                logger.error(f"[ChatMessenger::__start_client][{bot_client.get_name()}] Error [{chat.title}]: {e}")

        await self._clients_creator.disconnect_client(bot_client)

        try:
            self._session.commit()
        except Exception as e:
            self._session.rollback()
            logger.error(f'[ChatMessenger::__start_client][{bot_client.get_name()}] Commit error {e}')
        result = {bot_client.get_name(): result}
        logger.info(f"[ChatMessenger::__start_client][{bot_client.get_name()}] Messages sent: {result}")
        return result

    @staticmethod
    def __get_names_from_csv(csv_path: str = CHAT_MESSENGER_DEFAULT_CHANNELS_LIST_CSV_PATH, limit: int = 100) -> list[str]:
        if not os.path.exists(csv_path):
            logger.info(f"[ChatMessenger::__get_names_from_csv] {csv_path} doesn't exist")
            return []

        channels = []
        counter = 0
        with open(csv_path, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.reader(file)
            for row in reader:
                if counter == limit:
                    break
                if len(row) >= 2:
                    channel_username = row[0].strip()
                    channels.append(channel_username)
                    counter += 1

        return channels
