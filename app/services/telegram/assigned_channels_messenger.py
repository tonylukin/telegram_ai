import asyncio
import random

from fastapi.params import Depends
from telethon import TelegramClient
from telethon.tl.functions.messages import GetDiscussionMessageRequest
from telethon.tl.types import Channel, PeerChannel, Message, MessageService

from app.config import AI_POST_TEXT_TO_CHANNELS
from app.configs.logger import logging
from app.db.queries.bot import get_bot
from app.db.queries.bot_comment import get_channel_comments
from app.db.session import Session
from app.models.bot_comment import BotComment
from app.services.telegram.clients_creator import ClientsCreator, get_telegram_clients_to_comment
from app.services.telegram.helpers import join_chats
from app.services.text_maker import TextMakerDependencyConfig


class AssignedChannelsMessenger:
    def __init__(
            self,
            clients_creator: ClientsCreator = Depends(get_telegram_clients_to_comment),
            config: TextMakerDependencyConfig = Depends(TextMakerDependencyConfig),
    ):
        self.clients = []
        self.clients_creator = clients_creator
        self.ai_client = config.ai_client
        self.session = Session()
        self.chat_names = None
        self.message = None

    async def send_messages_to_assigned_channels(self, message: str, names: list[str] = None) -> list[dict[str, int]]:
        clients = await self.clients_creator.create_clients()
        self.message = message
        self.chat_names = names

        return await asyncio.gather(
            *(self.__start_client(client) for client in clients)
        )

    async def __start_client(self, client: TelegramClient) -> dict[str, dict[str, int]]:
        await client.start()
        logging.info(f"{client.session.filename} started")

        bot = get_bot(client)
        if bot is None:
            logging.error('Bot not found')
            return {}

        result = {}

        if self.chat_names is not None:
            await join_chats(client, self.chat_names)

        async for dialog in client.iter_dialogs():
            chat = dialog.entity

            if self.chat_names is not None and chat.username not in self.chat_names:
                continue

            if not isinstance(chat, Channel):
                continue
            if not chat.broadcast:
                logging.info(f"{chat.title} is not a channel")
                continue

            comments = get_channel_comments(channel=chat.title)
            if comments:
                logging.info(f"{chat.title}: has recent comments, skipping")
                continue

            try:
                messages = await client.get_messages(chat, limit=10)
                posts = [msg for msg in messages if isinstance(msg, Message) and not isinstance(msg, MessageService) and len(msg.message) > 0]

                if not posts:
                    continue

                last_post = posts[0]
                logging.info(f"Last post in {chat.title} is message ID {last_post.message[:10]}...")

                try:
                    discussion = await client(GetDiscussionMessageRequest(
                        peer=chat,
                        msg_id=last_post.id
                    ))

                    discussion_chat_id = discussion.messages[0].peer_id.channel_id
                    discussion_peer = PeerChannel(discussion_chat_id)

                    message = self.ai_client.generate_text(AI_POST_TEXT_TO_CHANNELS.format(text=self.message, post=discussion.messages[0].message))
                    await client.send_message(
                        entity=discussion_peer,
                        message=message,
                        reply_to=discussion.messages[0].id
                    )
                    logging.info(f"✅ Commented on discussion {discussion.messages[0].message[:10]}... for {chat.title}")

                    result[chat.title] = 1
                    bot_comment = BotComment(
                        bot_id=bot.id,
                        comment=message,
                        channel=chat.title,
                    )
                    self.session.add(bot_comment)
                    await asyncio.sleep(random.choice(range(10, 15)))

                except Exception as e:
                    logging.warning(f"⚠️ No discussion thread for message {last_post.id} in {chat.title}: {e}")

            except Exception as e:
                logging.error(f"❌ Error in {chat.title}: {e}")

        try:
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            logging.error(e)
        finally:
            self.session.close()

        await client.disconnect()
        logging.info(f"Messages sent: {result}")
        return {client.session.filename: result}
