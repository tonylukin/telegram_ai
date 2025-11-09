import asyncio
import random
from typing import Final

from fastapi.params import Depends
from sqlalchemy.orm import Session
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import SendReactionRequest
from telethon.tl.types import Channel, PeerChannel, ReactionEmoji, User

from app.configs.logger import logger
from app.db.queries.tg_post_reaction import get_reaction_by_post_id_and_channel
from app.dependencies import get_db
from app.models.tg_post_reaction import TgPostReaction
from app.services.telegram.chat_searcher import ChatSearcher
from app.services.telegram.clients_creator import ClientsCreator, get_bot_roles_to_react, BotClient
from app.services.telegram.helpers import get_name_from_user


class ReactionSender:
    MAX_REACTIONS_PER_CHAT: Final[int] = 5
    MAX_MESSAGES_PER_CHAT: Final[int] = 100
    REACTIONS: Final[tuple[str, ...]] = ("❤️", "🔥", "👍", "💯", "🙏", "👀", "😁", "🎉", "🤔", "👏", "🥰")
    BATCH_SIZE: Final[int] = 5
    LAST_MESSAGES_COUNT_FOR_RANDOM_REACTIONS: Final[int] = 20

    def __init__(
            self,
            clients_creator: ClientsCreator = Depends(),
            chat_searcher: ChatSearcher = Depends(ChatSearcher),
            session: Session = Depends(get_db),
    ):
        self._clients = []
        self._clients_creator = clients_creator
        self._chat_searcher = chat_searcher
        self._query = None
        self._reaction = None
        self._chat_names = None
        self._usernames = None
        self._session = session

    async def __send_reactions_to_my_chats(self, bot_client: BotClient) -> dict[str, dict[str, int]]:
        client = bot_client.client
        me = await client.get_me()
        dialogs = await client.get_dialogs()
        logger.info(f"[ReactionSender::__send_reactions_to_my_chats][{bot_client.get_name()}] Dialogs found: {len(dialogs)}")
        counter = {}

        for dialog in dialogs:
            current_chat_reactions_count = 0
            entity = dialog.entity
            if not hasattr(entity, 'megagroup') and not hasattr(entity, 'broadcast'):
                continue  # Skip usual chats

            logger.info(f"[ReactionSender::__send_reactions_to_my_chats][{bot_client.get_name()}] 📥 Processing chat: {entity.title}")
            reaction = self._reaction if self._reaction is not None else random.choice(self.REACTIONS)
            try:
                messages = await client.get_messages(entity, limit=self.MAX_MESSAGES_PER_CHAT)
                for message in messages:
                    if current_chat_reactions_count == self.MAX_REACTIONS_PER_CHAT:
                        break

                    if message.sender_id == me.id:
                        continue

                    if random.choice(range(int(self.MAX_MESSAGES_PER_CHAT / self.MAX_REACTIONS_PER_CHAT * 2))) > 0:
                        continue

                    chat_name = entity.username or str(entity.id)
                    tg_post_reaction = get_reaction_by_post_id_and_channel(session=self._session, channel=chat_name, post_id=message.id)
                    if tg_post_reaction is not None and bot_client.bot.id in tg_post_reaction.bot_ids:
                        continue

                    await asyncio.sleep(min(current_chat_reactions_count, 1) * 30)  # DELAY!!!
                    await client(SendReactionRequest(
                        peer=entity,
                        msg_id=message.id,
                        reaction=[ReactionEmoji(emoticon=reaction)]
                    ))
                    current_chat_reactions_count += 1
                    logger.info(f"[ReactionSender::__send_reactions_to_my_chats][{bot_client.get_name()}] Reacted to comment {message.id} in {entity.title}")
                    counter[entity.title] = counter.get(entity.title, 0) + 1

                    if tg_post_reaction is None:
                        tg_post_reaction = TgPostReaction(
                            channel=chat_name,
                            post_id=message.id,
                            sender_name=get_name_from_user(message.sender) if isinstance(message.sender, User) else None,
                            bot_ids=[bot_client.bot.id],
                            reactions=[reaction]
                        )
                        self._session.add(tg_post_reaction)
                    else:
                        tg_post_reaction.bot_ids.append(bot_client.bot.id)
                        tg_post_reaction.reactions.append(reaction)

            except Exception as e:
                logger.error(f"[ReactionSender::__send_reactions_to_my_chats][{bot_client.get_name()}] ⚠️ Failed to react {reaction} to comment {entity.title}: {e}")

        return {bot_client.get_name(): counter}

    async def __make_reactions_for_chat(self, bot_client: BotClient, chat: Channel, usernames: list[str]|list[int] = None) -> dict[str, dict]:
        counter = reaction_data = {}
        client = bot_client.client
        try:
            logger.info(f"[ReactionSender::__make_reactions_for_chat][{bot_client.get_name()}] 🧭 Sending reaction for: {chat.title}")
            messages = await client.get_messages(chat.id, limit=self.LAST_MESSAGES_COUNT_FOR_RANDOM_REACTIONS if not usernames else 100)
            discussion_peer = PeerChannel(chat.id)
            me = await client.get_me()

            id_set = username_set = fullname_set = {}
            if usernames:
                id_set = {u for u in usernames if isinstance(u, int)}
                username_set = {u.lstrip('@') for u in usernames if isinstance(u, str) and u.startswith('@')}
                fullname_set = {u for u in usernames if isinstance(u, str) and not u.startswith('@')}

            for message in messages:
                if not usernames and (message.sender_id == me.id or message.out or random.random() > 0.5):
                    logger.warning(f'[ReactionSender::__make_reactions_for_chat][{bot_client.get_name()}] it is my post')
                    continue

                if usernames:
                    sender_id = getattr(message.sender, "id", None)
                    sender_username = getattr(message.sender, "username", None)
                    sender_fullname = ((getattr(message.sender, "first_name", '') or '') + ' ' + (getattr(message.sender, "last_name", '') or '')).strip()
                    if sender_id not in id_set and sender_username not in username_set and sender_fullname not in fullname_set:
                        continue

                chat_name = chat.username or str(chat.id)
                tg_post_reaction = get_reaction_by_post_id_and_channel(session=self._session, channel=chat_name, post_id=message.id)
                if tg_post_reaction is not None and bot_client.bot.id in tg_post_reaction.bot_ids:
                    continue

                reaction = self._reaction if self._reaction is not None else random.choice(self.REACTIONS)
                try:
                    await client(SendReactionRequest(
                        peer=discussion_peer,
                        msg_id=message.id,
                        reaction=[ReactionEmoji(emoticon=reaction)]
                    ))
                    logger.info(f"[ReactionSender::__make_reactions_for_chat][{bot_client.get_name()}] Reacted to comment {message.id} in {chat.title}")
                    counter[chat.title] = counter.get(chat.title, 0) + 1
                except Exception as e:
                    logger.error(f"[ReactionSender::__make_reactions_for_chat][{bot_client.get_name()}] ⚠️ Failed to react {reaction}: {e}")

                reaction_data = {
                    'channel': chat_name,
                    'post_id': message.id,
                    'sender_name': get_name_from_user(message.sender) if isinstance(message.sender, User) else None,
                    'bot_ids': [bot_client.bot.id],
                    'reactions': [reaction]
                }

        except Exception as e:
            logger.error(f"[ReactionSender::__make_reactions_for_chat][{bot_client.get_name()}] ❌ Chat {chat.title} error: {e}")

        return {bot_client.get_name(): {'counter': counter, 'reaction_data': reaction_data}}

    async def __search_chats(self, bot_client: BotClient, query: str, usernames: list[str] | list[int] = None) -> dict[str, dict[str, int]]:
        client = bot_client.client
        chats = await self._chat_searcher.search_chats(client, query)
        logger.info(f"[ReactionSender::__search_chats][{bot_client.get_name()}] Found {len(chats)} chats")
        result = {}
        for chat in chats:
            try:
                await client(JoinChannelRequest(chat))
            except Exception:
                pass
            try:
                result.update(await self.__make_reactions_for_chat(bot_client=bot_client, chat=chat, usernames=usernames))
            except Exception as e:
                logger.error(f"[ReactionSender::__search_chats][{bot_client.get_name()}] Search chats error: {e}")

        counter_data = {}
        for bot_name in result:
            counter_data[bot_name] = result[bot_name]['counter']
            await self.__save_reaction_data(result[bot_name]['reaction_data'])

        return counter_data

    async def __send_to_specific_chats(self, bot_client: BotClient, chat_names: list[str], usernames: list[str] | list[int] = None) -> dict[str, dict[str, int]]:
        client = bot_client.client
        result = {}
        chats = []
        for chat_name in chat_names:
            try:
                chat = await client.get_entity(chat_name)
                chats.append(chat)
            except Exception as e:
                logger.error(f"[ReactionSender::__send_to_specific_chats][{bot_client.get_name()}] Getting chat instance error: {e}")

        for chat in chats:
            try:
                await client(JoinChannelRequest(chat))
            except Exception:
                pass
            try:
                await asyncio.sleep(5)
                result.update(await self.__make_reactions_for_chat(bot_client=bot_client, chat=chat, usernames=usernames))
            except Exception as e:
                logger.error(f"[ReactionSender::__send_to_specific_chats][{bot_client.get_name()}] Search chats error: {e}")

        counter_data = {}
        for bot_name in result:
            counter_data[bot_name] = result[bot_name]['counter']
            await self.__save_reaction_data(result[bot_name]['reaction_data'])

        return counter_data

    async def __start_client(self, bot_client: BotClient) -> dict[str, dict[str, int]]:
        await self._clients_creator.start_client(bot_client, task_name='send_reactions')
        logger.info(f"[ReactionSender::__start_client] {bot_client.get_name()} started")
        if self._chat_names is not None:
            result = await self.__send_to_specific_chats(bot_client, self._chat_names, self._usernames)
        elif self._query is not None:
            result = await self.__search_chats(bot_client, self._query, self._usernames)
        else:
            result = await self.__send_reactions_to_my_chats(bot_client)

        await self._clients_creator.disconnect_client(bot_client)
        logger.info(f"[ReactionSender::__start_client][{bot_client.get_name()}] Reactions sent: {result}")
        return result

    async def __save_reaction_data(self, reaction_data: dict) -> None:
        if not reaction_data:
            return

        tg_post_reaction = get_reaction_by_post_id_and_channel(
            session=self._session,
            channel=reaction_data['channel'],
            post_id=reaction_data['post_id']
        )
        if tg_post_reaction is None:
            tg_post_reaction = TgPostReaction(
                channel=reaction_data['channel'],
                post_id=reaction_data['post_id'],
                sender_name=reaction_data['sender_name'],
                bot_ids=reaction_data['bot_ids'],
                reactions=reaction_data['reactions']
            )
            self._session.add(tg_post_reaction)
        else:
            for i, bot_id in enumerate(reaction_data['bot_ids']):
                if bot_id not in tg_post_reaction.bot_ids:
                    tg_post_reaction.bot_ids.append(bot_id)
                    tg_post_reaction.reactions.append(reaction_data['reactions'][i])

        self._session.flush()

    async def send_reactions(self, query: str = None, reaction: str = None, chat_names: list[str] = None, usernames: list[str] | list[int] = None) -> list[dict[str, int]]:
        self._query = query
        self._reaction = reaction
        self._chat_names = chat_names
        self._usernames = usernames
        page = 0
        results = []
        while True:
            offset = page * self.BATCH_SIZE
            bot_clients = self._clients_creator.create_clients_from_bots(roles=get_bot_roles_to_react(), limit=self.BATCH_SIZE, offset=offset)
            batch_results = await asyncio.gather(
                *(self.__start_client(bot_client) for bot_client in bot_clients)
            )
            results.extend(batch_results)
            page += 1
            if len(bot_clients) < self.BATCH_SIZE:
                break

        return results
