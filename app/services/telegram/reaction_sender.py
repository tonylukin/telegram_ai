import asyncio
import random

from fastapi.params import Depends
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import SendReactionRequest
from telethon.tl.types import Channel, PeerChannel
from telethon.tl.types import ReactionEmoji

from app.configs.logger import logging
from app.services.telegram.chat_searcher import ChatSearcher
from app.services.telegram.clients_creator import ClientsCreator, get_bot_roles_to_react, BotClient


class ReactionSender:
    MAX_REACTIONS_PER_CHAT = 5
    MAX_MESSAGES_PER_CHAT = 100
    REACTIONS = ["❤️", "🔥", "👍", "💯", "🙏", "👀", "😁", "🎉", "🤔", "👏", "🥰"]

    def __init__(self, clients_creator: ClientsCreator = Depends(), chat_searcher: ChatSearcher = Depends(ChatSearcher)):
        self.clients = []
        self.clients_creator = clients_creator
        self.chat_searcher = chat_searcher
        self.query = None
        self.reaction = None
        self.names = None

    async def __send_reactions_to_my_chats(self, bot_client: BotClient) -> dict[str, dict[str, int]]:
        client = bot_client.client
        me = await client.get_me()
        dialogs = await client.get_dialogs()
        logging.info(f"Dialogs found: {len(dialogs)}")
        counter = {}

        for dialog in dialogs:
            current_chat_reactions_count = 0
            entity = dialog.entity
            if not hasattr(entity, 'megagroup') and not hasattr(entity, 'broadcast'):
                continue  # Skip usual chats

            logging.info(f"📥 Processing chat: {entity.title}")
            reaction = self.reaction if self.reaction is not None else random.choice(self.REACTIONS)
            try:
                messages = await client.get_messages(entity, limit=self.MAX_MESSAGES_PER_CHAT)
                for message in messages:
                    if current_chat_reactions_count == self.MAX_REACTIONS_PER_CHAT:
                        break

                    if message.sender_id == me.id:
                        continue

                    if random.choice(range(int(self.MAX_MESSAGES_PER_CHAT / self.MAX_REACTIONS_PER_CHAT * 2))) > 0:
                        continue

                    await asyncio.sleep(min(current_chat_reactions_count, 1) * 30)  # DELAY!!!
                    await client(SendReactionRequest(
                        peer=entity,
                        msg_id=message.id,
                        reaction=[ReactionEmoji(emoticon=reaction)]
                    ))
                    current_chat_reactions_count += 1
                    logging.info(f"Reacted to comment {message.id} in {entity.title}")
                    counter[entity.title] = counter.get(entity.title, 0) + 1

            except Exception as e:
                logging.error(f"⚠️ Failed to react {reaction} to comment {entity.title}: {e}")

        return {bot_client.get_name(): counter}

    async def __make_reactions_for_chat(self, bot_client: BotClient, chat: Channel) -> dict[str, dict[str, int]]:
        counter = {}
        client = bot_client.client
        try:
            logging.info(f"🧭 Sending reaction for: {chat.title}")
            messages = await client.get_messages(chat.id, limit=10)
            discussion_peer = PeerChannel(chat.id)
            me = await client.get_me()

            for message in messages:
                if message.sender_id == me.id or message.out or random.random() > 0.5:
                    logging.warning('it is my post')
                    continue

                reaction = self.reaction if self.reaction is not None else random.choice(self.REACTIONS)
                try:
                    await client(SendReactionRequest(
                        peer=discussion_peer,
                        msg_id=message.id,
                        reaction=[ReactionEmoji(emoticon=reaction)]
                    ))
                    logging.info(f"Reacted to comment {message.id} in {chat.title}")
                    counter[chat.title] = counter.get(chat.title, 0) + 1
                except Exception as e:
                    logging.error(f"⚠️ Failed to react {reaction}: {e}")
        except Exception as e:
            logging.error(f"❌ Chat {chat.title} error: {e}")

        return {bot_client.get_name(): counter}

    async def __search_chats(self, bot_client: BotClient) -> dict[str, dict[str, int]]:
        client = bot_client.client
        chats = await self.chat_searcher.search_chats(client, self.query)
        logging.info(f"Found {len(chats)} chats")
        result = {}
        for chat in chats:
            try:
                await client(JoinChannelRequest(chat))
                result.update(await self.__make_reactions_for_chat(bot_client=bot_client, chat=chat))
            except Exception as e:
                logging.error(f"Search chats error: {e}")

        return result

    async def __send_to_specific_chats(self, bot_client: BotClient) -> dict[str, dict[str, int]]:
        client = bot_client.client
        result = {}
        chats = []
        for name in self.names:
            try:
                chat = await client.get_entity(name)
                chats.append(chat)
            except Exception as e:
                logging.error(f"Getting chat instance error: {e}")

        for chat in chats:
            try:
                await client(JoinChannelRequest(chat))
                await asyncio.sleep(5)
                result.update(await self.__make_reactions_for_chat(bot_client=bot_client, chat=chat))
            except Exception as e:
                logging.error(f"Search chats error: {e}")

        return result

    async def __start_client(self, bot_client: BotClient) -> dict[str, dict[str, int]]:
        await self.clients_creator.start_client(bot_client)
        logging.info(f"{bot_client.get_name()} started")
        if self.names is not None:
            result = await self.__send_to_specific_chats(bot_client)
        elif self.query is not None:
            result = await self.__search_chats(bot_client)
        else:
            result = await self.__send_reactions_to_my_chats(bot_client)

        await self.clients_creator.disconnect_client(bot_client)
        logging.info(f"Reactions sent: {result}")
        return result

    async def send_reactions(self, query: str = None, reaction: str = None, names: list[str] = None) -> list[dict[str, int]]:
        self.query = query
        self.reaction = reaction
        self.names = names
        bot_clients = self.clients_creator.create_clients_from_bots(roles=get_bot_roles_to_react())
        return await asyncio.gather(*(self.__start_client(client) for client in bot_clients))
        # await asyncio.gather(*(client.run_until_disconnected() for client in self.clients))
