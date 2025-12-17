import asyncio

from fastapi.params import Depends
from telethon.tl.types import User

from app.config import BULLYING_MESSAGE_PROMPT
from app.configs.logger import logger
from app.dependencies import get_open_ai_client
from app.services.ai.ai_client_base import AiClientBase
from app.services.telegram.chat_messenger import ChatMessenger
from app.services.telegram.clients_creator import ClientsCreator, get_bot_roles_to_comment, BotClient
from app.services.telegram.helpers import join_chats
from app.services.telegram.user_instance_searcher import UserInstanceSearcher
from app.services.telegram.user_messages_search import UserMessagesSearch, ChatMessages


class BullyingMachine:
    def __init__(
            self,
            clients_creator: ClientsCreator = Depends(),
            user_instance_searcher: UserInstanceSearcher = Depends(),
            user_message_searcher: UserMessagesSearch = Depends(),
            chat_messenger: ChatMessenger = Depends(),
            ai_client: AiClientBase = Depends(get_open_ai_client),
    ):
        self._clients_creator = clients_creator
        self._user_instance_searcher = user_instance_searcher
        self._user_message_searcher = user_message_searcher
        self._chat_messenger = chat_messenger
        self._ai_client = ai_client

    async def answer_to_messages(self, username: str, channel_usernames: list[str]):
        bot_clients = self._clients_creator.create_clients_from_bots(roles=get_bot_roles_to_comment())
        if not bot_clients:
            logger.error(f'[BullyingMachine::answer_to_messages] No bots found for answer_to_messages [{username}]')
            return None

        await self._clients_creator.start_client(bot_clients[0])
        try:
            user = await self._user_instance_searcher.search_user_by_channels(bot_client=bot_clients[0], username=username, channel_usernames=channel_usernames)
            if not user or not isinstance(user, User):
                logger.error(f"[BullyingMachine::answer_to_messages] ❌ User '{username}' not found in these channels: {channel_usernames}.")
                return None

            chat_messages_list = await self._user_message_searcher.get_user_messages_from_chats(client=bot_clients[0].client, chats=channel_usernames, username=user.username, limit=10)
            return await asyncio.gather(
                *(self.__answer_by_client(bot_client=client, chat_messages_list=chat_messages_list) for client in bot_clients)
            )
        finally:
            await self._clients_creator.disconnect_client(bot_clients[0])

    async def __answer_by_client(self, bot_client: BotClient, chat_messages_list: list[ChatMessages]) -> dict[str, dict[str, int]]:
        await self._clients_creator.start_client(bot_client)
        result = {}
        try:
            for chat_message in chat_messages_list:
                chat = chat_message.get('chat')
                messages = chat_message.get('messages')
                result[chat.username] = 0
                if not messages:
                    logger.info(f'[BullyingMachine::__answer_by_client][{bot_client.get_name()}] No messages found for answer_to_messages [{chat.username}]')
                    continue
                await join_chats(bot_client.client, [chat.username])
                for message in messages:
                    if not message.message:
                        continue
                    answer = self._ai_client.generate_text(BULLYING_MESSAGE_PROMPT.format(message=message.message))
                    if await self._chat_messenger.send_message(bot_client=bot_client, chat=chat, reply_to_post_id=message.id, message=answer):
                        result[chat.username] += 1
        except Exception as e:
            logger.error(f"[BullyingMachine::__answer_by_client][{bot_client.get_name()}] Error: {e}")
        finally:
            await self._clients_creator.disconnect_client(bot_client)

        return {bot_client.get_name(): result}
