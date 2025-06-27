from fastapi.params import Depends
from telethon import TelegramClient
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import Message, User, PeerChannel

from app.config import AI_USER_INFO_PROMPT
from app.configs.logger import logger
from app.db.session import Session
from app.models.tg_user import TgUser
from app.models.tg_user_comment import TgUserComment
from app.services.ai.ai_client_base import AiClientBase
from app.services.ai.gemini_client import GeminiClient
from app.services.telegram.clients_creator import ClientsCreator, \
    get_telegram_clients_for_human_scanner
from app.services.telegram.user_messages_search import UserMessagesSearch


def get_ai_client() -> AiClientBase:
    return GeminiClient()

class UserInfoCollector:
    def __init__(
            self,
            clients_creator: ClientsCreator = Depends(get_telegram_clients_for_human_scanner),
            ai_client: AiClientBase = Depends(get_ai_client),
    ):
        self.clients_creator = clients_creator
        self.ai_client = ai_client
        self.session = Session()

    async def __init_client(self) -> TelegramClient:
        clients = self.clients_creator.create_clients_from_bots()
        client = clients[0]
        await client.start()
        return client

    async def get_user_info(self, username: str, channel_usernames: list[str], prompt: str = None):
        client = await self.__init_client()

        if username.startswith('@'): # todo to service
            user = await client.get_entity(username)
        else:
            user = None
            for chat_name in channel_usernames:
                try:
                    chat = await client.get_entity(chat_name) # todo get info from broadcast -> to linked group (app/services/telegram/user_inviter.py::75)
                    linked_chat_id = None
                    if chat.broadcast:
                        full = await client(GetFullChannelRequest(chat))
                        linked_chat_id = full.full_chat.linked_chat_id
                        if not linked_chat_id:
                            logger.error(f"{chat} does not have a full chat")
                            continue
                        chat = PeerChannel(linked_chat_id)

                    async for msg in client.iter_messages(chat, limit=5000):
                        if isinstance(msg, Message) and msg.sender and isinstance(msg.sender, User):
                            full_name = f"{msg.sender.first_name or ''} {msg.sender.last_name or ''}".strip().lower()
                            if username.lower() in full_name:
                                user = msg.sender
                                if linked_chat_id is not None:
                                    channel_usernames.append(msg.chat.username) #adding linked chat to list along with the broadcast
                                break
                    if user:
                        break
                except Exception as e:
                    logger.error(f"⚠️ Search error {chat_name}: {e}")

            if not user:
                raise ValueError(f"❌ User not found '{username}' in these channels: {channel_usernames}.")

        try:
            full = await client(GetFullUserRequest(user.id))
        except Exception as e:
            full = None
            logger.error(f"Could not find info for {username}: {e}")

        # messages = await UserMessagesSearch.get_user_messages_from_chat(client=client, chats=channel_usernames, username=username)
        comments_by_channel = await UserMessagesSearch.get_user_comments(client=client, channel_usernames=channel_usernames, user=user)

        if len(comments_by_channel) and prompt is None:
            messages = []
            for _, v in comments_by_channel.items():
                messages.extend(v)
            prompt = AI_USER_INFO_PROMPT.format(messages=messages)
        desc = ''
        if prompt is not None:
            desc = self.ai_client.generate_text(prompt)

        await client.disconnect()

        full_desc = {
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "bio": full.full_user.about if full is not None and hasattr(full.full_user, 'about') else None,
            "phone": user.phone,
            "is_bot": user.bot,
            "is_verified": user.verified,
            "comment_count": len(comments_by_channel),
            "description": desc,
        }
        self.__save_to_db(user=user, comments_by_channel=comments_by_channel, desc=full_desc)
        return full_desc

    def __save_to_db(self, user: User, comments_by_channel: dict[str, set[str]], desc: dict[str, str]) -> None:
        user_found = self.session.query(TgUser).filter_by(tg_id=user.id).first()

        try:
            if user_found is None:
                user_found = TgUser(
                    tg_id=user.id,
                )
                self.session.add(user_found)

            user_found.nickname = user.username or f"{user.first_name or ''} {user.last_name or ''}".strip()
            user_found.description = desc
            if user_found.id is None:
                self.session.flush()

            for channel, comments in comments_by_channel.items():
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
