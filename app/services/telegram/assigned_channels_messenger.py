import asyncio
import random

from fastapi.params import Depends
from sqlalchemy.orm import Session
from telethon.tl.functions.messages import GetDiscussionMessageRequest
from telethon.tl.types import Channel, PeerChannel, Message, MessageService

from app.config import AI_POST_TEXT_TO_CHANNELS, AI_POST_TEXT_TO_CHANNELS_NO_MESSAGE
from app.configs.logger import logging
from app.db.queries.bot_comment import get_channel_comments
from app.dependencies import get_db
from app.models.bot_comment import BotComment
from app.services.telegram.clients_creator import ClientsCreator, get_bot_roles_to_comment, BotClient
from app.services.telegram.helpers import join_chats
from app.services.text_maker import TextMakerDependencyConfig


class AssignedChannelsMessenger:
    def __init__(
            self,
            clients_creator: ClientsCreator = Depends(),
            config: TextMakerDependencyConfig = Depends(TextMakerDependencyConfig),
            session: Session = Depends(get_db)
    ):
        self.clients = []
        self.clients_creator = clients_creator
        self.ai_client = config.ai_client
        self.session = session
        self.chat_names = None
        self.message = None

    async def send_messages_to_assigned_channels(self, message: str = None, names: list[str] = None) -> list[dict[str, int]]:
        bot_clients = self.clients_creator.create_clients_from_bots(roles=get_bot_roles_to_comment())
        self.message = message
        self.chat_names = names

        return await asyncio.gather(
            *(self.__start_client(client) for client in bot_clients)
        )

    async def __start_client(self, bot_client: BotClient) -> dict[str, dict[str, int]]:
        client = bot_client.client
        await self.clients_creator.start_client(bot_client)
        logging.info(f"{bot_client.get_name()} started")

        bot = bot_client.bot
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

            comments = get_channel_comments(self.session, channel=chat.title)
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

                    if self.message is None:
                        prompt = AI_POST_TEXT_TO_CHANNELS_NO_MESSAGE.format(post=discussion.messages[0].message)
                    else:
                        prompt = AI_POST_TEXT_TO_CHANNELS.format(text=self.message, post=discussion.messages[0].message)
                    message = self.ai_client.generate_text(prompt=prompt)
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

        await self.clients_creator.disconnect_client(bot_client)

        try:
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            logging.error(e)

        logging.info(f"Messages sent: {result}")
        return {bot_client.get_name(): result}
