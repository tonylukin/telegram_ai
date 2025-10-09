import asyncio

from fastapi.params import Depends
from sqlalchemy.orm import Session
from telethon import errors, events
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.tl.types import User

from app.config import MESSAGE_RECEIVER_PROMPT
from app.configs.logger import logger
from app.dependencies import get_ai_client, get_db
from app.models.tg_bot_message import TgBotMessage
from app.services.ai.ai_client_base import AiClientBase
from app.services.telegram.clients_creator import ClientsCreator, BotClient
from app.services.telegram.helpers import get_name_from_user


class MessageReceiver:
    BATCH_SIZE = 3

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

    async def check_and_reply(self, promoting_channel: str, promoting_channel_to_invite: str = None) -> list[dict[str, int]]:
        bot_clients = self._clients_creator.create_clients_from_bots()
        results = []
        for i in range(0, len(bot_clients), self.BATCH_SIZE):
            batch = bot_clients[i:i + self.BATCH_SIZE]
            batch_results = await asyncio.gather(
                *(self.__check_and_reply(bot_client, promoting_channel, promoting_channel_to_invite) for bot_client in
                  batch)
            )
            results.extend(batch_results)

        return results

    async def get_new_messages_for_bot(self, bot_name: str):
        bot_clients = self._clients_creator.create_clients_from_bots(names=[bot_name])
        if not bot_clients:
            raise RuntimeError(f'[MessageReceiver::get_new_messages_for_bot] No clients found for {bot_name}')

        client = bot_clients[0].client
        logger.info(f'[MessageReceiver::get_new_messages_for_bot][{bot_name}] Listening for bot messages')

        @client.on(events.NewMessage)
        async def handler(event):
            if event.chat is not None:
                return
            sender = await event.get_sender()
            sender_name = get_name_from_user(sender)
            logger.info(f"[MessageReceiver::get_new_messages_for_bot][{sender_name} to {bot_clients[0].get_name()}] {event.text}")

        logger.info("[MessageReceiver::get_new_messages_for_bot] Listening for messages...")
        await self._clients_creator.start_client(bot_client=bot_clients[0], task_name='get_new_messages_for_bot')
        try:
            await client.run_until_disconnected()
        finally:
            await self._clients_creator.disconnect_client(bot_clients[0])

    async def __check_and_reply(self, bot_client: BotClient, promoting_channel: str, promoting_channel_to_invite: str | None) -> dict[str, list]:
        client = bot_client.client
        await self._clients_creator.start_client(bot_client, task_name='messages_check_and_reply')
        logger.info(f"[Check_and_reply] {bot_client.get_name()} started")

        try:
            dialogs = await client.get_dialogs()  # fetch all chats
        except Exception as e:
            logger.error(f"[Check_and_reply][{bot_client.get_name()}] Cannot get dialogs: {e}")
            dialogs = []

        replies = []
        for dialog in dialogs:
            try:
                if not isinstance(dialog.entity, User) or dialog.entity.bot:
                    continue
                chat_id = dialog.id

                # Get last message in this dialog
                messages = []
                try:
                    messages = await client.get_messages(chat_id, limit=10)
                except Exception as e:
                    logger.error(f"[Check_and_reply][{bot_client.get_name()}] Failed to get messages for {chat_id}: {e}")
                if not messages:
                    continue
                last_msg = messages[0]

                # Check if last message is incoming (from another user)
                if last_msg.out or last_msg.sender.bot or last_msg.sender.deleted or (last_msg.sender.first_name == 'Telegram' and last_msg.sender.verified):
                    continue

                dialog_messages = ['- ' + message.message for message in messages if message.message]
                logger.info(f"[Check_and_reply][{bot_client.get_name()}] Dialog: {dialog_messages}")
                try:
                    reply_text = self._ai_client.generate_text(MESSAGE_RECEIVER_PROMPT.format(message=last_msg.text, chat=promoting_channel))
                    sender_name = get_name_from_user(last_msg.sender)
                    await client.send_message(chat_id, reply_text, reply_to=last_msg.id)
                    logger.info(f"[Check_and_reply][{bot_client.get_name()}] Replied in chat {chat_id}")
                    replies.append([sender_name, last_msg.text, reply_text])
                    self.__save_bot_message_to_db(bot_id=bot_client.bot.id, sender_name=sender_name, text="\n".join(dialog_messages), reply_text=reply_text)
                except errors.ChatWriteForbiddenError:
                    logger.error(f"[Check_and_reply][{bot_client.get_name()}] Cannot send message to chat {chat_id} (write forbidden)")
                except Exception as e:
                    logger.error(f"[Check_and_reply][{bot_client.get_name()}] Cannot send message to chat {chat_id} ({e})")

                try:
                    if promoting_channel_to_invite:
                        await client(InviteToChannelRequest(
                            channel=promoting_channel_to_invite,
                            users=[last_msg.sender]
                        ))
                except Exception as e:
                    logger.error(f"[Check_and_reply][{bot_client.get_name()}] Cannot invite user {last_msg.sender.username} to channel {promoting_channel} ({e})")

            except Exception as e:
                logger.error(f"[Check_and_reply][{bot_client.get_name()}] Common error: {e}")

        await self._clients_creator.disconnect_client(bot_client)
        return {bot_client.get_name(): replies}

    def __save_bot_message_to_db(self, bot_id: int, sender_name: str, text: str, reply_text: str) -> TgBotMessage | None:
        try:
            message = TgBotMessage(
                bot_id=bot_id,
                sender_name=sender_name,
                text=text,
                reply_text=reply_text
            )
            self._session.add(message)
            self._session.commit()
        except Exception as e:
            self._session.rollback()
            logger.error(f"[Check_and_reply][#{bot_id}] Error saving TgBotMessage: {e}")
            return None

        return message
