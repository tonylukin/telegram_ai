from fastapi.params import Depends

from app.configs.logger import logger
from app.services.telegram.chat_searcher import ChatSearcher
from app.services.telegram.clients_creator import BotClient, ClientsCreator
from app.services.telegram.helpers import resolve_tg_link, get_chat_from_channel, extract_username_or_name
from telethon.tl.types import Message, User, PeerChannel, Channel



class UserInstanceSearcher:
    def __init__(
            self,
            clients_creator: ClientsCreator = Depends(),
            chat_searcher: ChatSearcher = Depends(),
    ):
        self._clients_creator = clients_creator
        self._chat_searcher = chat_searcher

    async def search_user_by_channels(self, bot_client: BotClient, username: str, channel_usernames: list[str]) -> User | Channel | None:
        client = bot_client.client

        # first check linked chats and add them to initial array removing broadcast
        for chat_name in channel_usernames[:]:
            try:
                chat = await resolve_tg_link(client, chat_name)
                if chat is None:
                    found_channels = await self._chat_searcher.search_chats(client, chat_name)
                    logger.info(f"Found channels [{len(found_channels)}] for {chat_name}")
                    channel_usernames.remove(chat_name)
                    if len(found_channels) == 0:
                        continue

                    channel_usernames.extend([str(found_channel.id) for found_channel in found_channels])
                    continue

                if isinstance(chat, User):
                    logger.info(f"'{chat.username}' is User instance")
                    channel_usernames.remove(chat_name)
                    continue
                if not isinstance(chat, Channel):
                    logger.info(f"Chat is instance of '{type(chat)}'")
                    channel_usernames.remove(chat_name)
                    continue

                if chat.username and '@' + chat.username != chat_name:
                    channel_usernames.remove(chat_name)
                    channel_usernames.append(chat.username)

                linked_chat_id = await get_chat_from_channel(client, chat)
                if linked_chat_id is None:
                    continue

                if isinstance(linked_chat_id, int):
                    if chat_name in channel_usernames:
                        channel_usernames.remove(chat_name)
                    elif chat.username in channel_usernames:
                        channel_usernames.remove(chat.username)
                    channel_usernames.append(str(linked_chat_id))
            except Exception as e:
                logger.error(f"Search for linked chats error {chat_name}: {e}")

        username = extract_username_or_name(username)
        if username.startswith('@'):
            try:
                user = await client.get_entity(username)
            except Exception as e:
                await self._clients_creator.disconnect_client(bot_client)
                logger.error(f"User {username} not found: {e}")
                raise ValueError('User not found')
        else:
            user = None
            for chat_name in channel_usernames:
                try:
                    chat = chat_name
                    if chat_name.isnumeric():
                        chat = PeerChannel(int(chat_name))

                    async for msg in client.iter_messages(chat, limit=5000):
                        if isinstance(msg, Message) and msg.sender and isinstance(msg.sender, User):
                            full_name = f"{msg.sender.first_name or ''} {msg.sender.last_name or ''}".strip().lower()
                            if username.lower() in full_name or username.lower() in msg.message.lower():
                                user = msg.sender
                                logger.info(f"User found #{user.id} [{full_name}]")
                                break
                    if user:
                        break
                except Exception as e:
                    logger.error(f"⚠️ Search error {chat_name}")

        return user
