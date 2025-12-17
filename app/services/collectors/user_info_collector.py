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
from app.dependencies import get_db, get_open_ai_client
from app.models.tg_user import TgUser
from app.models.tg_user_comment import TgUserComment
from app.services.ai.ai_client_base import AiClientBase
from app.services.telegram.chat_searcher import ChatSearcher
from app.services.telegram.clients_creator import ClientsCreator, \
    get_bot_roles_for_human_scanner, BotClient
from app.services.telegram.user_instance_searcher import UserInstanceSearcher
from app.services.telegram.user_messages_search import UserMessagesSearch


class UserInfoCollector:
    _translations = {
        'ru': {
            'messages_prompt': AI_USER_INFO_MESSAGES_PROMPT,
            'reactions_prompt': AI_USER_INFO_REACTIONS_PROMPT,
        },
        'en': {
            'messages_prompt': AI_USER_INFO_MESSAGES_PROMPT_EN,
            'reactions_prompt': AI_USER_INFO_REACTIONS_PROMPT_EN,
        },
    }

    def __init__(
            self,
            clients_creator: ClientsCreator = Depends(),
            ai_client: AiClientBase = Depends(get_open_ai_client),
            chat_searcher: ChatSearcher = Depends(),
            session: Session = Depends(get_db),
            user_messages_search: UserMessagesSearch = Depends(),
            user_instance_searcher: UserInstanceSearcher = Depends(),
    ):
        self._clients_creator = clients_creator
        self._ai_client = ai_client
        self._chat_searcher = chat_searcher
        self._session = session
        self._user_messages_search = user_messages_search
        self._user_instance_searcher = user_instance_searcher

    def __init_client(self) -> BotClient:
        bot_clients = self._clients_creator.create_clients_from_bots(roles=get_bot_roles_for_human_scanner(), limit=1)
        if len(bot_clients) == 0:
            raise Exception('No bots found')
        return bot_clients[0]

    async def get_user_info(self, username: str, channel_usernames: list[str], prompt: str = None, lang: str = 'ru'):
        bot_client = self.__init_client()
        client = bot_client.client
        await self._clients_creator.start_client(bot_client, task_name='user_info_collector')

        user = await self._user_instance_searcher.search_user_by_channels(bot_client=bot_client, username=username, channel_usernames=channel_usernames)

        if not user or not isinstance(user, User):
            await self._clients_creator.disconnect_client(bot_client)
            raise ValueError(f"❌ User '{username}' not found in these channels: {channel_usernames}.")

        user_found = get_user_by_id(self._session, user.id)
        date_interval = datetime.now() - timedelta(weeks=4)
        if user_found and user_found.updated_at and user_found.updated_at > date_interval:
            logger.info(f"User {user_found.nickname}[{user_found.tg_id}] has fresh info")
            await self._clients_creator.disconnect_client(bot_client)
            return user_found.description

        try:
            full = await client(GetFullUserRequest(user.id))
        except Exception as e:
            full = None
            logger.info(f"Could not find info for {username}: {e}")

        # messages = await self._user_messages_search.get_user_messages_from_chats(client=client, chats=channel_usernames, username=username)
        comments_reactions_by_channel = await self._user_messages_search.get_user_comments_reactions(client=client, channel_usernames=channel_usernames, user=user)

        await self._clients_creator.disconnect_client(bot_client)

        messages_found = []
        if user_found:
            messages_found = get_user_comments(self._session, user_found.id)

        messages = set([message_found.comment for message_found in messages_found])
        reactions = []
        if len(comments_reactions_by_channel):
            for entry in comments_reactions_by_channel.values():
                messages.update(entry['comments'])
                reactions.extend(entry['reactions'])

        desc = []
        if messages:
            try:
                desc.append(self._ai_client.generate_text((prompt or self._translations.get(lang).get('messages_prompt')).format(messages=messages)))
            except Exception as e:
                logger.error(f"user_info_collector messages generate text: {e}")
        if reactions:
            try:
                desc.append(self._ai_client.generate_text(self._translations.get(lang).get('reactions_prompt').format(reactions=reactions)))
            except Exception as e:
                logger.error(f"user_info_collector reactions generate text: {e}")

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
            self.__save_to_db(user=user, comments_reactions_by_channel=comments_reactions_by_channel, messages_found=messages_found, desc=full_desc, user_found=user_found)
        return full_desc

    def __save_to_db(self, user: User, comments_reactions_by_channel: dict[str, dict[str, set[str]]], messages_found: list[TgUserComment], desc: dict[str, str], user_found: TgUser | None) -> None:
        try:
            if user_found is None:
                user_found = TgUser(
                    tg_id=user.id,
                )
                self._session.add(user_found)

            user_found.nickname = user.username or f"{user.first_name or ''} {user.last_name or ''}".strip()
            user_found.description = desc
            user_found.updated_at = datetime.now()
            existing_comments = {message_found.comment for message_found in messages_found}
            if user_found.id is None:
                self._session.flush()

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
                        self._session.add(tg_user_comment)
            self._session.commit()
        except Exception as e:
            self._session.rollback()
            logger.error(e)
