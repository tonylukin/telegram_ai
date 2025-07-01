from telethon import TelegramClient
from telethon.tl.custom.message import Message
from telethon.tl.functions.messages import GetDiscussionMessageRequest
from telethon.tl.types import PeerChannel
from telethon.tl.types import PeerUser, User

from app.configs.logger import logging
from app.services.telegram.helpers import get_user_by_username


class UserMessagesSearch:

    """@deprecated"""
    @staticmethod
    async def get_last_messages_from_user(client: TelegramClient, username: str, limit: int = 10):
        user = await get_user_by_username(client, username)

        messages = []

        async for dialog in client.iter_dialogs():
            async for msg in client.iter_messages(dialog.id, limit=100):
                if msg.from_id and isinstance(msg.from_id, PeerUser) and msg.from_id.user_id == user.id:
                    messages.append(msg)
                    if len(messages) >= limit:
                        return messages

        return messages

    """@deprecated"""
    @staticmethod
    async def get_user_messages_from_chat(client: TelegramClient, chats: list[str], username: str, limit: int = 50):
        user = await get_user_by_username(client, username)  # assume this returns a User or int
        messages = []

        for chat in chats:
            try:
                chat_entity = await client.get_entity(chat)
                async for msg in client.iter_messages(chat_entity, from_user=user.id, limit=limit):
                    messages.append(msg.message if isinstance(msg, Message) else None)
            except Exception as e:
                logging.error(f"Error accessing chat {chat}: {e}")

        return messages

    @staticmethod
    async def get_user_comments(client: TelegramClient, channel_usernames: list[str], user: User, limit: int = 50) -> dict[str, set[str]]:
        result = {}

        for channel_username in channel_usernames:
            # 1. Get the channel and user entities
            channel = await client.get_entity(int(channel_username) if channel_username.isnumeric() else channel_username)

            # 2. Get recent posts from the channel
            posts = await client.get_messages(channel, limit=limit * 10)
            comments = set()

            for post in posts:
                try:
                    if post.from_id.user_id == user.id:
                        comments.add(post.message)

                    # 3. Get the linked discussion group (if exists)
                    discussion = await client(GetDiscussionMessageRequest(
                        peer=channel,
                        msg_id=post.id
                    ))

                    discussion_chat_id = discussion.messages[0].peer_id.channel_id
                    discussion_peer = PeerChannel(discussion_chat_id)

                    # 4. Retrieve comments in discussion group from the user
                    async for msg in client.iter_messages(discussion_peer, from_user=user, limit=limit):
                        comments.add(msg.message)
                except Exception as e:
                    logging.error(f"⚠️ Skipping post {post.id}: {e}")
                    continue

            if len(comments):
                result[channel_username] = comments

        return result
