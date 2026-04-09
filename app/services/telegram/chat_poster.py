import random

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
        session: Session = Depends(get_db),
    ):
        self._clients_creator = clients_creator
        self._ai_client = ai_client
        self._session = session

    async def send_prompted_messages_to_chats_by_names(
        self,
        prompt: str,
        chat_names: list[str],
    ) -> dict[str, int]:
        bot_clients = self._clients_creator.create_clients_from_bots(
            roles=get_bot_roles_to_comment()
        )
        if not bot_clients:
            raise Exception("No bots found")

        random.shuffle(chat_names)

        return await self.__send_messages_to_chats(
            bot_clients=bot_clients,
            chat_names=chat_names,
            prompt=prompt,
        )

    async def send_simple_messages_to_chats_by_names(
        self,
        messages: list[str],
        chat_names: list[str],
        limit: int | None = 1,
    ) -> dict[str, int]:
        if not chat_names:
            return {}

        limit = limit or len(chat_names)

        bot_clients = self._clients_creator.create_clients_from_bots(
            roles=get_bot_roles_to_comment()
        )
        if not bot_clients:
            raise Exception("No bots found")

        random.shuffle(chat_names)
        target_chats = chat_names[:limit]

        return await self.__send_messages_to_chats(
            bot_clients=bot_clients,
            chat_names=target_chats,
            messages=messages,
        )

    async def __send_messages_to_chats(
        self,
        bot_clients: list[BotClient],
        chat_names: list[str],
        prompt: str | None = None,
        messages: list[str] | None = None,
    ) -> dict[str, int]:
        result: dict[str, int] = {}

        for chat_name in chat_names:
            result[chat_name] = 0

            try:
                if prompt:
                    message_for_chat = self._ai_client.generate_text(prompt)
                else:
                    if not messages:
                        logger.warning(
                            f"[ChatPoster::__send_messages_to_chats] "
                            f"⚠️ No messages provided for {chat_name}"
                        )
                        continue
                    message_for_chat = random.choice(messages)
            except Exception as e:
                logger.error(
                    f"[ChatPoster::__send_messages_to_chats] "
                    f"❌ Failed to prepare message for {chat_name}: {e}"
                )
                continue

            shuffled_clients = bot_clients[:]
            random.shuffle(shuffled_clients)

            for bot_client in shuffled_clients:
                sent = await self.__try_send_with_single_bot(
                    bot_client=bot_client,
                    chat_name=chat_name,
                    message=message_for_chat,
                )
                if sent:
                    result[chat_name] = 1
                    break

        try:
            self._session.commit()
        except Exception as e:
            self._session.rollback()
            logger.exception(
                f"[ChatPoster::__send_messages_to_chats] Commit error: {e}"
            )

        return result

    async def __try_send_with_single_bot(
        self,
        bot_client: BotClient,
        chat_name: str,
        message: str,
    ) -> bool:
        client = bot_client.client

        try:
            await self._clients_creator.start_client(
                bot_client,
                task_name="chat_poster_by_names",
            )
            logger.info(
                f"[ChatPoster::__try_send_with_single_bot] {bot_client.get_name()} started"
            )

            chat = await client.get_entity(chat_name)

            if not await is_user_in_group(client, chat):
                logger.info(
                    f"[ChatPoster::__try_send_with_single_bot][{bot_client.get_name()}] "
                    f"🚪 Not in chat. Joining {chat.title}"
                )
                await client(JoinChannelRequest(chat))

                if not await is_user_in_group(client, chat):
                    logger.warning(
                        f"[ChatPoster::__try_send_with_single_bot][{bot_client.get_name()}] "
                        f"⏳ Join request pending for {chat.title}"
                    )
                    return False

            sent_message = await client.send_message(entity=chat, message=message)
            if not sent_message:
                logger.warning(
                    f"[ChatPoster::__try_send_with_single_bot][{bot_client.get_name()}] "
                    f"⚠️ send_message returned empty result for {chat_name}"
                )
                return False

            bot_comment = BotComment(
                bot_id=bot_client.bot.id,
                comment=message,
                channel=cut_string_to_count_of_characters(chat.title, 64),
            )
            self._session.add(bot_comment)

            logger.info(
                f"[ChatPoster::__try_send_with_single_bot][{bot_client.get_name()}] "
                f"✅ Sent message to {chat_name}"
            )
            return True

        except Exception as e:
            logger.error(
                f"[ChatPoster::__try_send_with_single_bot][{bot_client.get_name()}] "
                f"❌ Failed to send message to {chat_name}: {e}"
            )
            return False

        finally:
            try:
                await self._clients_creator.disconnect_client(bot_client)
                logger.info(
                    f"[ChatPoster::__try_send_with_single_bot] {bot_client.get_name()} disconnected"
                )
            except Exception as e:
                logger.error(
                    f"[ChatPoster::__try_send_with_single_bot] "
                    f"❌ Failed to disconnect {bot_client.get_name()}: {e}"
                )