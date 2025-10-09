import asyncio
import random

from fastapi.params import Depends
from sqlalchemy.orm import Session
from telethon.tl.functions.messages import GetDiscussionMessageRequest
from telethon.tl.types import Channel, PeerChannel, Message, MessageService

from app.config import AI_POST_TEXT_TO_CHANNELS, AI_POST_TEXT_TO_CHANNELS_NO_MESSAGE
from app.configs.logger import logger
from app.db.queries.bot_comment import get_channel_comments
from app.dependencies import get_db, get_ai_client
from app.models.bot_comment import BotComment
from app.services.ai.ai_client_base import AiClientBase
from app.services.telegram.clients_creator import ClientsCreator, get_bot_roles_to_comment, BotClient
from app.services.telegram.helpers import join_chats


class AssignedChannelsMessenger:
    def __init__(
            self,
            clients_creator: ClientsCreator = Depends(),
            ai_client: AiClientBase = Depends(get_ai_client),
            session: Session = Depends(get_db)
    ):
        self._clients = []
        self._clients_creator = clients_creator
        self._ai_client = ai_client
        self._session = session
        self._chat_names = None
        self._message = None

    async def send_messages_to_assigned_channels(self, message: str = None, names: list[str] = None, bot_roles: list[str] = None) -> list[dict[str, int]]:
        bot_clients = self._clients_creator.create_clients_from_bots(roles=bot_roles if bot_roles else get_bot_roles_to_comment())
        self._message = message
        self._chat_names = names

        return await asyncio.gather(
            *(self.__start_client(client) for client in bot_clients)
        )

    async def __start_client(self, bot_client: BotClient) -> dict[str, dict[str, int]]:
        client = bot_client.client
        await self._clients_creator.start_client(bot_client, task_name='send_messages_to_assigned_channels')
        logger.info(f"[AssignedChannelsMessenger] {bot_client.get_name()} started")

        bot = bot_client.bot
        result = {}

        if self._chat_names is not None:
            await join_chats(client, self._chat_names)

        async for dialog in client.iter_dialogs():
            chat = dialog.entity

            if self._chat_names is not None and chat.username not in self._chat_names:
                continue

            if not isinstance(chat, Channel):
                continue
            if not chat.broadcast:
                logger.info(f"[AssignedChannelsMessenger][{bot_client.get_name()}] {chat.title} is not a channel")
                continue

            comments = get_channel_comments(self._session, channel=chat.title)
            if comments:
                logger.info(f"[AssignedChannelsMessenger][{bot_client.get_name()}] {chat.title}: has recent comments, skipping")
                continue

            try:
                messages = await client.get_messages(chat, limit=10)
                posts = [msg for msg in messages if isinstance(msg, Message) and not isinstance(msg, MessageService) and len(msg.message) > 0]

                if not posts:
                    continue

                last_post = posts[0]
                logger.info(f"[AssignedChannelsMessenger][{bot_client.get_name()}] Last post in {chat.title} is message ID {last_post.message[:10]}...")

                try:
                    discussion = await client(GetDiscussionMessageRequest(
                        peer=chat,
                        msg_id=last_post.id
                    ))

                    discussion_chat_id = discussion.messages[0].peer_id.channel_id
                    discussion_peer = PeerChannel(discussion_chat_id)

                    if self._message is None:
                        prompt = AI_POST_TEXT_TO_CHANNELS_NO_MESSAGE.format(post=discussion.messages[0].message)
                    else:
                        prompt = AI_POST_TEXT_TO_CHANNELS.format(text=self._message, post=discussion.messages[0].message)
                    message = self._ai_client.generate_text(prompt=prompt)
                    await client.send_message(
                        entity=discussion_peer,
                        message=message,
                        reply_to=discussion.messages[0].id
                    )
                    logger.info(f"[AssignedChannelsMessenger][{bot_client.get_name()}] ✅ Commented on discussion {discussion.messages[0].message[:10]}... for {chat.title}")

                    result[chat.title] = 1
                    bot_comment = BotComment(
                        bot_id=bot.id,
                        comment=message,
                        channel=chat.title,
                    )
                    self._session.add(bot_comment)
                    await asyncio.sleep(random.choice(range(10, 15)))

                except Exception as e:
                    logger.warning(f"[AssignedChannelsMessenger][{bot_client.get_name()}] ⚠️ No discussion thread for message {last_post.id} in {chat.title}: {e}")

            except Exception as e:
                logger.error(f"[AssignedChannelsMessenger][{bot_client.get_name()}] ❌ Error in {chat.title}: {e}")

        await self._clients_creator.disconnect_client(bot_client)

        try:
            self._session.commit()
        except Exception as e:
            self._session.rollback()
            logger.error(f'[AssignedChannelsMessenger][{bot_client.get_name()}] Saving to db error: {e}')

        logger.info(f"[AssignedChannelsMessenger][{bot_client.get_name()}] Messages sent: {result}")
        return {bot_client.get_name(): result}
