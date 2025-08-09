import asyncio

from fastapi.params import Depends
from telethon import errors
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.tl.types import User

from app.config import MESSAGE_RECEIVER_PROMPT
from app.configs.logger import logger
from app.dependencies import get_ai_client
from app.services.ai.ai_client_base import AiClientBase
from app.services.telegram.clients_creator import ClientsCreator, BotClient


class MessageReceiver:
    def __init__(self, clients_creator: ClientsCreator = Depends(), ai_client: AiClientBase = Depends(get_ai_client)):
        self.clients = []
        self.clients_creator = clients_creator
        self.ai_client = ai_client

    async def check_and_reply(self, promoting_channel: str, promoting_channel_to_invite: str = None) -> list[dict[str, int]]:
        bot_clients = self.clients_creator.create_clients_from_bots()
        return await asyncio.gather(
            *(self.__check_and_reply(bot_client, promoting_channel, promoting_channel_to_invite) for bot_client in bot_clients)
        )

    async def __check_and_reply(self, bot_client: BotClient, promoting_channel: str, promoting_channel_to_invite: str | None) -> dict[str, list]:
        client = bot_client.client
        await self.clients_creator.start_client(bot_client)
        logger.info(f"{bot_client.get_name()} started")
        # promoting_channel_entity = await client.get_entity(promoting_channel)

        dialogs = await client.get_dialogs()  # fetch all chats
        replies = []
        for dialog in dialogs:
            if not isinstance(dialog.entity, User):
                continue
            chat_id = dialog.id

            # Get last message in this dialog
            messages = await client.get_messages(chat_id, limit=10)
            if not messages:
                continue
            last_msg = messages[0]

            # Check if last message is incoming (from another user)
            if last_msg.out or last_msg.sender.bot or last_msg.sender.deleted:  # out=True means message sent by yourself
                continue

            logger.info(f"Dialog: {[message.message for message in messages]}")
            reply = self.ai_client.generate_text(MESSAGE_RECEIVER_PROMPT.format(message=last_msg.text, chat=promoting_channel))
            try:
                await client.send_message(chat_id, reply, reply_to=last_msg.id)
                logger.info(f"Replied in chat {chat_id}")
                replies.append([last_msg.sender.username, last_msg.text, reply])
            except errors.ChatWriteForbiddenError:
                logger.error(f"Cannot send message to chat {chat_id} (write forbidden)")
            except Exception as e:
                logger.error(f"Cannot send message to chat {chat_id} ({e})")

            try:
                if promoting_channel_to_invite:
                    await client(InviteToChannelRequest(
                        channel=promoting_channel_to_invite,
                        users=[last_msg.sender]
                    ))
            except Exception as e:
                logger.error(f"Cannot invite user {last_msg.sender.username} message to channel {promoting_channel} ({e})")

        await self.clients_creator.disconnect_client(bot_client)
        return {bot_client.get_name(): replies}
