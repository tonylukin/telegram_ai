import random
import asyncio
import hashlib

from fastapi.params import Depends
from sqlalchemy.orm import Session

from app.config import is_dev, GENERATOR_FROM_CHANNEL_AI_PROMPT
from app.configs.logger import logger
from app.db.queries.tg_lead import get_tg_lead_by_post_id
from app.dependencies import get_ai_client, get_db
from app.models.tg_lead import TgLead
from app.services.ai.ai_client_base import AiClientBase
from app.services.notification_sender import NotificationSender
from app.services.telegram.chat_messenger import ChatMessenger
from app.services.telegram.clients_creator import ClientsCreator
from app.services.telegram.helpers import get_name_from_user
from app.services.telegram.user_messages_search import UserMessagesSearch
from app.models.bot import Bot


class GeneratorFromChannels:
    def __init__(
            self,
            user_message_search: UserMessagesSearch = Depends(),
            clients_creator: ClientsCreator = Depends(),
            ai_client: AiClientBase = Depends(get_ai_client),
            chat_messenger: ChatMessenger = Depends(),
            session: Session = Depends(get_db),
    ):
        self._user_message_search = user_message_search
        self._clients_creator = clients_creator
        self._ai_client = ai_client
        self._chat_messenger = chat_messenger
        self._session = session
        self._telegram_message_sender = NotificationSender()
        self._notify_about_leads: bool = is_dev()

    def set_notification_credentials(self, chat_id: str, bot_token: str = None):
        self._notify_about_leads = True
        if bot_token:
            self._telegram_message_sender.telegram_message_sender.set_telegram_bot_token(bot_token)
        self._telegram_message_sender.telegram_message_sender.set_telegram_chat_id(chat_id)
        return self

    async def generate_from_telegram_channels(
            self,
            chats: list[str],
            condition: str,
            except_users: list[str] = None,
            answers: list[str] = None,
            bot_roles: list[str] = None,
    ) -> dict[str, list[str]]:
        if bot_roles is None:
            bot_roles = [Bot.ROLE_LEAD_FROM_CHANNEL]
        bot_clients = self._clients_creator.create_clients_from_bots(roles=bot_roles, limit=1)
        if not bot_clients:
            raise Exception('[GeneratorFromChannels::generate_from_telegram_channels]: No bots found')

        await self._clients_creator.start_client(bot_clients[0], task_name='generate_from_telegram_channels')
        chat_messages_list = await self._user_message_search.get_last_messages_from_chats(client=bot_clients[0].client, chats=chats, limit=100)
        result = {}

        for chat_messages in chat_messages_list:
            try:
                message_to_id_map = {}
                message_texts = []
                chat = chat_messages.get('chat')
                messages = chat_messages.get('messages')
                if not messages:
                    continue

                for message in messages:
                    if message.text and message.text.strip() and message.id:
                        if message.sender and (message.sender.username and '@' + message.sender.username.lower() in except_users or message.sender.id in except_users):
                            continue
                        text_hash = hashlib.md5(message.text.encode("utf-8")).hexdigest()
                        message_to_id_map[text_hash] = (message.id, get_name_from_user(message.sender))
                        message_texts.append(message.text)
                try:
                    matched_list = (self
                                    ._ai_client
                                    .generate_text(prompt=GENERATOR_FROM_CHANNEL_AI_PROMPT.format(messages=message_texts, condition=condition))
                                    .split('<br>')
                                    )
                except Exception as e:
                    logger.error(f"[GeneratorFromChannels::generate_from_telegram_channels][{bot_clients[0].get_name()}] error: {e}")
                    matched_list = []

                chat_key = chat.username or chat.id
                result[chat_key] = []

                for matched_message in matched_list:
                    if not matched_message:
                        continue

                    # response_message = self._ai_client.generate_text(
                    #     prompt=answer_prompt.format(message=matched_message)
                    # )
                    text_hash = hashlib.md5(matched_message.encode("utf-8")).hexdigest()
                    post_id, sender_name = message_to_id_map[text_hash]
                    if get_tg_lead_by_post_id(session=self._session, post_id=post_id):
                        logger.warning(f"[GeneratorFromChannels::generate_from_telegram_channels][{bot_clients[0].get_name()}] lead exists, skip message #{post_id}: {matched_message}")
                        continue

                    answer = None
                    if answers:
                        answer = random.choice(answers)
                        if not await self._chat_messenger.send_message(
                                bot_client=bot_clients[0],
                                chat=chat,
                                message=answer,
                                reply_to_post_id=post_id
                        ):
                            logger.error(f"[GeneratorFromChannels::generate_from_telegram_channels][{bot_clients[0].get_name()}] replying to message error: {matched_message}")
                            continue

                    tg_lead = TgLead(
                        channel=chat.username or chat.id,
                        message=matched_message,
                        answer=answer,
                        post_id=post_id,
                        bot_id=bot_clients[0].bot.id,
                    )
                    self._session.add(tg_lead)
                    if self._notify_about_leads:
                        message = f'Found new lead from {sender_name} in chat @{chat.username} [{chat.id}]\n'
                        message += f'<blockquote>{matched_message}</blockquote>\n\n'
                        message += f'<strong>Answer</strong>:\n{answer}'
                        self.__notify_about_lead(message)

                    result[chat_key].append(matched_message)

            except Exception as e:
                logger.error(f"[GeneratorFromChannels::generate_from_telegram_channels][{bot_clients[0].get_name()}] error: {e}")

        try:
            self._session.flush()
        except Exception as e:
            logger.error(f"[GeneratorFromChannels::generate_from_telegram_channels][{bot_clients[0].get_name()}] Flush error: {e}")

        await self._clients_creator.disconnect_client(bot_clients[0])
        return result

    def __notify_about_lead(self, message: str):
        asyncio.create_task(
            self._telegram_message_sender.send_notification_message(message)
        )
