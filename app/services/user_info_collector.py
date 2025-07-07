from datetime import timedelta, datetime

from fastapi.params import Depends
from telethon import TelegramClient
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import Message, User, PeerChannel

from app.config import AI_USER_INFO_MESSAGES_PROMPT, AI_USER_INFO_REACTIONS_PROMPT
from app.configs.logger import logger
from app.db.queries.tg_users import get_user_by_id
from app.db.session import Session
from app.dependencies import get_db
from app.models.tg_user import TgUser
from app.models.tg_user_comment import TgUserComment
from app.services.ai.ai_client_base import AiClientBase
from app.services.ai.gemini_client import GeminiClient
from app.services.telegram.clients_creator import ClientsCreator, \
    get_bot_roles_for_human_scanner
from app.services.telegram.helpers import get_chat_from_channel, resolve_tg_link, extract_username_or_name
from app.services.telegram.user_messages_search import UserMessagesSearch


def get_ai_client() -> AiClientBase:
    return GeminiClient()

class UserInfoCollector:
    def __init__(
            self,
            clients_creator: ClientsCreator = Depends(),
            ai_client: AiClientBase = Depends(get_ai_client),
            session: Session = Depends(get_db)
    ):
        self.clients_creator = clients_creator
        self.ai_client = ai_client
        self.session = session

    async def __init_client(self) -> TelegramClient:
        clients = self.clients_creator.create_clients_from_bots(roles=get_bot_roles_for_human_scanner())
        client = clients[0]
        await client.start()
        return client

    async def get_user_info(self, username: str, channel_usernames: list[str], prompt: str = None):
        client = await self.__init_client()

        # first check linked chats and add them to initial array removing broadcast
        for chat_name in channel_usernames[:]:
            try:
                chat = await resolve_tg_link(client, chat_name)
                if chat.username and chat.username != chat_name:
                    channel_usernames.remove(chat_name)
                    channel_usernames.append(chat.username)

                linked_chat_id = await get_chat_from_channel(client, chat)
                if linked_chat_id is None:
                    logger.error(f"{chat} does not have a full chat")
                    continue

                if isinstance(linked_chat_id, int):
                    channel_usernames.remove(chat_name)
                    channel_usernames.append(str(linked_chat_id))
            except Exception as e:
                logger.error(f"Search for linked chats error {chat_name}: {e}")

        username = extract_username_or_name(username)
        if username.startswith('@'):
            try:
                user = await client.get_entity(username)
            except Exception as e:
                await client.disconnect()
                logger.error(f"User {username} not found: {e}")
                raise e
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
                            if username.lower() in full_name:
                                user = msg.sender
                                logger.info(f"User found #{user.id} [{full_name}]")
                                break
                    if user:
                        break
                except Exception as e:
                    logger.error(f"⚠️ Search error {chat_name}: {e}")

            if not user:
                await client.disconnect()
                raise ValueError(f"❌ User '{username}' not found in these channels: {channel_usernames}.")

        user_found = get_user_by_id(self.session, user.id)
        date_interval = datetime.now() - timedelta(weeks=4)
        if user_found and user_found.updated_at and user_found.updated_at > date_interval:
            logger.info(f"User {user_found.nickname}[{user_found.tg_id}] has fresh info")
            await client.disconnect()
            return user_found.description

        try:
            full = await client(GetFullUserRequest(user.id))
        except Exception as e:
            full = None
            logger.error(f"Could not find info for {username}: {e}")

        # messages = await UserMessagesSearch.get_user_messages_from_chat(client=client, chats=channel_usernames, username=username)
        comments_reactions_by_channel = await UserMessagesSearch.get_user_comments_reactions(client=client, channel_usernames=channel_usernames, user=user)

        await client.disconnect()

        messages = []
        reactions = []
        prompt_reactions = None
        if len(comments_reactions_by_channel) and prompt is None:
            for _, v in comments_reactions_by_channel.get('comments').items():
                messages.extend(v)
            if messages:
                prompt = AI_USER_INFO_MESSAGES_PROMPT.format(messages=messages)

            for _, v in comments_reactions_by_channel.get('reactions').items():
                reactions.extend(v)
            if reactions:
                prompt_reactions = AI_USER_INFO_REACTIONS_PROMPT.format(reactions=reactions)
        desc = []
        if prompt is not None:
            desc = self.ai_client.generate_text(prompt)
        if prompt_reactions is not None:
            desc = self.ai_client.generate_text(prompt_reactions)

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
            "description": desc,
        }
        self.__save_to_db(user=user, comments_reactions_by_channel=comments_reactions_by_channel, desc=full_desc)
        return full_desc

    def __save_to_db(self, user: User, comments_reactions_by_channel: dict[str, dict[str, set[str]]], desc: dict[str, str]) -> None:
        user_found = get_user_by_id(self.session, user.id)

        try:
            if user_found is None:
                user_found = TgUser(
                    tg_id=user.id,
                )
                self.session.add(user_found)

            user_found.nickname = user.username or f"{user.first_name or ''} {user.last_name or ''}".strip()
            user_found.description = desc
            user_found.updated_at = datetime.now()
            if user_found.id is None:
                self.session.flush()

            for channel, comments_reactions in comments_reactions_by_channel.items():
                comments = comments_reactions.get('comments')
                for comment in comments:
                    if not comment:
                        continue
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
        finally:
            self.session.close()
