import asyncio
import random

from fastapi.params import Depends
from sqlalchemy.orm import Session
from telethon import TelegramClient
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import GetDiscussionMessageRequest
from telethon.tl.types import Channel, PeerChannel

from app.config import TELEGRAM_CHATS_TO_POST, AI_POST_TEXT_TO_CHANNELS, AI_POST_TEXT_TO_CHANNELS_NO_MESSAGE
from app.configs.logger import logging, logger
from app.db.queries.bot_comment import get_bot_comments
from app.dependencies import get_db
from app.models.bot_comment import BotComment
from app.services.telegram.chat_searcher import ChatSearcher
from app.services.telegram.clients_creator import ClientsCreator, get_bot_roles_to_comment, BotClient
from app.services.telegram.helpers import is_user_in_group, has_antispam_bot, get_chat_from_channel
from app.services.text_maker import TextMakerDependencyConfig


class ChatMessenger:
    def __init__(
            self,
            clients_creator: ClientsCreator = Depends(),
            chat_searcher: ChatSearcher = Depends(ChatSearcher),
            config: TextMakerDependencyConfig = Depends(TextMakerDependencyConfig),
            session: Session = Depends(get_db)
    ):
        self.clients = []
        self.clients_creator = clients_creator
        self.chat_searcher = chat_searcher
        self.ai_client = config.ai_client
        self.session = session
        self.chat_names = None
        self.message = None

    @staticmethod
    async def send_message(client: TelegramClient, chat: Channel | PeerChannel, message: str, reply_to_post_id: int|None) -> bool:
        try:
            await client.send_message(
                entity=chat,
                message=message,
                reply_to=reply_to_post_id
            )
            logging.info(f"✅ Sent message to {chat.title}")
            return True
        except Exception as e:
            logging.error(f"❌ Failed to send message to {chat.title}: {e}")
            return False

    async def send_messages_to_chats_by_names(self, message: str = None, names: list[str] = None) -> list[dict[str, int]]:
        self.chat_names = names
        if self.chat_names is None:
            self.chat_names = TELEGRAM_CHATS_TO_POST
        self.message = message
        bot_clients = self.clients_creator.create_clients_from_bots(roles=get_bot_roles_to_comment())
        if len(bot_clients) == 0:
            raise Exception('No bots found')

        chat_names = self.chat_names[:]
        random.shuffle(chat_names)
        k, m = divmod(len(chat_names), len(bot_clients))
        return await asyncio.gather(
            *(self.__start_client(client, chat_names[i * k + min(i, m):(i + 1) * k + min(i + 1, m)]) for i, client in
              enumerate(bot_clients))
        )

    async def __start_client(self, bot_client: BotClient, chat_names: list[str]) -> dict[str, dict[str, int]]:
        client = bot_client.client
        await self.clients_creator.start_client(bot_client)
        logging.info(f"{bot_client.get_name()} started")

        bot = bot_client.bot

        chats = []
        post_texts = {}
        for name in chat_names:
            try:
                chat = await client.get_entity(name)
                if not isinstance(chat, Channel):
                    logger.info(f"{name}: Not a Channel")
                    continue

                last_messages = await client.get_messages(chat.id, limit=5)
                post_text_data = (chat.title, None)
                random_message = None
                if last_messages:
                    random_message = random.choice(last_messages)
                    post_text_data = (random_message.message, random_message.id)

                linked_chat_id = await get_chat_from_channel(client, chat)
                if linked_chat_id is None:
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
                logging.error(f"{name}: {e}")

        result = {}
        for chat in chats:
            try:
                comments = get_bot_comments(self.session, channel=chat.title, bot=bot_client.bot)
                if len(comments) > 0:
                    logging.info(f"{chat.title}: {bot_client.get_name()} has recent comments")
                    continue
                if await has_antispam_bot(chat=chat, client=client):
                    logging.info(f"{chat.title} has antispam bot")
                    continue
                if not await is_user_in_group(client, chat):
                    logging.info(f"🚪 Not in chat. Joining {chat.title}")
                    await client(JoinChannelRequest(chat))
                    await asyncio.sleep(120) # before sending the first message let's wait 2 minutes

                (post_text, post_id) = post_texts[chat.id]
                if self.message is None: # todo add emotions
                    prompt = AI_POST_TEXT_TO_CHANNELS_NO_MESSAGE.format(post=post_text)
                else:
                    prompt = AI_POST_TEXT_TO_CHANNELS.format(text=self.message, post=post_text)
                message = self.ai_client.generate_text(prompt)
                if await self.send_message(client=client, chat=chat, message=message, reply_to_post_id=post_id):
                    result[chat.title] = 1
                    bot_comment = BotComment(
                        bot_id=bot.id,
                        comment=message,
                        channel=chat.title,
                    )
                    self.session.add(bot_comment)

                await asyncio.sleep(random.choice(range(10, 15)))
            except Exception as e:
                logging.error(f"Error [{chat.title}]: {e}")

        await self.clients_creator.disconnect_client(bot_client)

        try:
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            logging.error(e)
        result = {bot_client.get_name(): result}
        logging.info(f"Messages sent: {result}")
        return result
