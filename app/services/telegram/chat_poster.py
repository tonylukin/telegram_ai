import asyncio
from fastapi.params import Depends
from sqlalchemy.orm import Session
from telethon.tl.functions.channels import JoinChannelRequest

from app.configs.logger import logger
from app.dependencies import get_open_ai_client, get_db
from app.models import BotComment
from app.services.ai.ai_client_base import AiClientBase
from app.services.telegram.clients_creator import ClientsCreator, BotClient, get_bot_roles_to_comment
from app.services.telegram.helpers import is_user_in_group, cut_string_to_count_of_characters


class ChatPoster:
    def __init__(
            self,
            clients_creator: ClientsCreator = Depends(),
            ai_client: AiClientBase = Depends(get_open_ai_client),
            session: Session = Depends(get_db)
    ):
        self._clients_creator = clients_creator
        self._ai_client = ai_client
        self._session = session

    async def send_messages_to_chats_by_names(
            self,
            prompt: str,
            chat_names: list[str],
    ) -> list[dict[str, int]]:
        bot_clients = self._clients_creator.create_clients_from_bots(roles=get_bot_roles_to_comment(), limit=len(chat_names))
        if len(bot_clients) == 0:
            raise Exception('No bots found')

        return await asyncio.gather(
            *(self.__start_client(bot_client=client, chat_names=chat_names, prompt=prompt) for client in bot_clients)
        )

    async def __start_client(self, bot_client: BotClient, chat_names: list[str], prompt: str) -> dict[str, dict[str, int]]:
        client = bot_client.client
        await self._clients_creator.start_client(bot_client, task_name='chat_poster_by_names')
        logger.info(f"[ChatPoster::__start_client] {bot_client.get_name()} started")

        result = {}
        for name in chat_names:
            try:
                chat = await client.get_entity(name)
                if not await is_user_in_group(client, chat):
                    logger.info(f"[ChatPoster::__start_client][{bot_client.get_name()}] 🚪 Not in chat. Joining {chat.title}")
                    await client(JoinChannelRequest(chat))
                    await asyncio.sleep(120) # before sending the first message let's wait 2 minutes

                message = self._ai_client.generate_text(prompt)
                if await client.send_message(entity=chat, message=message):
                    result[name] = 1
                    bot_comment = BotComment(
                        bot_id=bot_client.bot.id,
                        comment=message,
                        channel=cut_string_to_count_of_characters(chat.title, 64),
                    )
                    self._session.add(bot_comment)

                logger.info(f"[ChatPoster::__start_client][{bot_client.get_name()}] ✅ Sent message to {name}")
            except Exception as e:
                logger.error(f"[ChatPoster::__start_client][{bot_client.get_name()}] ❌ Failed to send message to {name}: {e}")

        await self._clients_creator.disconnect_client(bot_client)

        try:
            self._session.commit()
        except Exception as e:
            self._session.rollback()
            logger.exception(f'[ChatPoster::__start_client][{bot_client.get_name()}] Commit error {e}')

        return {bot_client.get_name(): result}
