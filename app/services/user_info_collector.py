from datetime import timedelta, datetime

from fastapi.params import Depends
from sqlalchemy.orm import Session
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import Message, User, PeerChannel, Channel

from app.config import AI_USER_INFO_MESSAGES_PROMPT, AI_USER_INFO_REACTIONS_PROMPT, AI_USER_INFO_MESSAGES_PROMPT_EN, \
    AI_USER_INFO_REACTIONS_PROMPT_EN
from app.configs.logger import logger
from app.db.queries.tg_user_comment import get_user_comments
from app.db.queries.tg_users import get_user_by_id
from app.dependencies import get_db, get_ai_client
from app.models.tg_user import TgUser
from app.models.tg_user_comment import TgUserComment
from app.services.ai.ai_client_base import AiClientBase
from app.services.telegram.chat_searcher import ChatSearcher
from app.services.telegram.clients_creator import ClientsCreator, \
    get_bot_roles_for_human_scanner, BotClient
from app.services.telegram.helpers import get_chat_from_channel, resolve_tg_link, extract_username_or_name
from app.services.telegram.user_messages_search import UserMessagesSearch


class UserInfoCollector:
    def __init__(
            self,
            clients_creator: ClientsCreator = Depends(),
            ai_client: AiClientBase = Depends(get_ai_client),
            chat_searcher: ChatSearcher = Depends(),
            session: Session = Depends(get_db)
    ):
        self.clients_creator = clients_creator
        self.ai_client = ai_client
        self.chat_searcher = chat_searcher
        self.session = session

    def __init_client(self) -> BotClient:
        bot_clients = self.clients_creator.create_clients_from_bots(roles=get_bot_roles_for_human_scanner(), limit=1)
        if len(bot_clients) == 0:
            raise Exception('No bots found')
        return bot_clients[0]

    async def get_user_info(self, username: str, channel_usernames: list[str], prompt: str = None, lang: str = 'ru'):
        bot_client = self.__init_client()
        client = bot_client.client
        await self.clients_creator.start_client(bot_client, task_name='user_info_collector')

        # first check linked chats and add them to initial array removing broadcast
        for chat_name in channel_usernames[:]:
            try:
                chat = await resolve_tg_link(client, chat_name)
                if chat is None:
                    found_channels = await self.chat_searcher.search_chats(client, chat_name)
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
                await self.clients_creator.disconnect_client(bot_client)
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

        if not user or not isinstance(user, User):
            await self.clients_creator.disconnect_client(bot_client)
            raise ValueError(f"❌ User '{username}' not found in these channels: {channel_usernames}.")

        user_found = get_user_by_id(self.session, user.id)
        date_interval = datetime.now() - timedelta(weeks=4)
        if user_found and user_found.updated_at and user_found.updated_at > date_interval:
            logger.info(f"User {user_found.nickname}[{user_found.tg_id}] has fresh info")
            await self.clients_creator.disconnect_client(bot_client)
            return user_found.description

        try:
            full = await client(GetFullUserRequest(user.id))
        except Exception as e:
            full = None
            logger.info(f"Could not find info for {username}: {e}")

        # messages = await UserMessagesSearch.get_user_messages_from_chat(client=client, chats=channel_usernames, username=username)
        comments_reactions_by_channel = await UserMessagesSearch.get_user_comments_reactions(client=client, channel_usernames=channel_usernames, user=user) #todo use DI

        await self.clients_creator.disconnect_client(bot_client)

        messages_found = []
        if user_found:
            messages_found = get_user_comments(self.session, user_found.id)

        messages = set([message_found.comment for message_found in messages_found])
        reactions = []
        if len(comments_reactions_by_channel):
            for entry in comments_reactions_by_channel.values():
                messages.update(entry['comments'])
                reactions.extend(entry['reactions'])

        translations = {
            'ru': {
                'messages_prompt': AI_USER_INFO_MESSAGES_PROMPT,
                'reactions_prompt': AI_USER_INFO_REACTIONS_PROMPT,
            },
            'en': {
                'messages_prompt': AI_USER_INFO_MESSAGES_PROMPT_EN,
                'reactions_prompt': AI_USER_INFO_REACTIONS_PROMPT_EN,
            },
        }
        desc = []
        if messages:
            desc.append(self.ai_client.generate_text((prompt or translations.get(lang).get('messages_prompt')).format(messages=messages)))
        if reactions:
            desc.append(self.ai_client.generate_text(translations.get(lang).get('reactions_prompt').format(reactions=reactions)))

        full_desc = {
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "bio": full.full_user.about if full is not None and hasattr(full.full_user, 'about') else None,
            "phone": user.phone,
            "is_bot": user.bot,
            "is_verified": user.verified,
            "comment_count": len(messages),
            "reaction_count": len(reactions),
            "description": '\n\n'.join(desc),
        }
        if desc:
            self.__save_to_db(user=user, comments_reactions_by_channel=comments_reactions_by_channel, messages_found=messages_found, desc=full_desc)
        return full_desc

    def __save_to_db(self, user: User, comments_reactions_by_channel: dict[str, dict[str, set[str]]], messages_found: list[TgUserComment], desc: dict[str, str]) -> None:
        user_found = get_user_by_id(self.session, user.id) # todo do not fetch if already done

        try:
            if user_found is None:
                user_found = TgUser(
                    tg_id=user.id,
                )
                self.session.add(user_found)

            user_found.nickname = user.username or f"{user.first_name or ''} {user.last_name or ''}".strip()
            user_found.description = desc
            user_found.updated_at = datetime.now()
            existing_comments = {message_found.comment for message_found in messages_found}
            if user_found.id is None:
                self.session.flush()

            for channel, comments_reactions in comments_reactions_by_channel.items():
                comments = comments_reactions.get('comments')
                for comment in comments:
                    if not comment:
                        continue
                    if comment not in existing_comments:
                        tg_user_comment = TgUserComment(
                            user_id=user_found.id,
                            comment=comment,
                            channel=channel,
                        )
                        self.session.add(tg_user_comment)
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            logger.error(e)
