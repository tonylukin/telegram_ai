from collections.abc import Iterable
from typing import TypedDict

from telethon import TelegramClient
from telethon.tl.custom.message import Message
from telethon.tl.functions.messages import GetDiscussionMessageRequest
from telethon.tl.types import PeerChannel, PeerUser, User, Chat, Channel

from app.config import is_dev
from app.configs.logger import logger
from app.services.telegram.clients_creator import BotClient
from app.services.telegram.helpers import get_instance_by_username, get_channel_entity_by_username_or_id, join_chats


class ChatMessages(TypedDict):
    chat: Chat | Channel
    messages: list[Message]

class UserMessagesSearch:

    """@deprecated"""
    @staticmethod
    async def get_last_messages_from_user(client: TelegramClient, username: str, limit: int = 10):
        user = await get_instance_by_username(client, username)

        messages = []

        async for dialog in client.iter_dialogs():
            async for msg in client.iter_messages(dialog.id, limit=100):
                if msg.from_id and isinstance(msg.from_id, PeerUser) and hasattr(msg.from_id, 'user_id') and msg.from_id.user_id == user.id:
                    messages.append(msg)
                    if len(messages) >= limit:
                        return messages

        return messages

    @staticmethod
    async def get_user_messages_from_chats(client: TelegramClient, chats: list[str], username: str = None, limit: int = 50) -> list[ChatMessages]:
        user = None
        if username:
            user = await get_instance_by_username(client, username)  # assume this returns a User or int
        messages_by_chat = []
        chats = list(set(chats))

        for chat in chats:
            try:
                chat_entity = await get_instance_by_username(client, chat)
                messages = []
                async for msg in client.iter_messages(chat_entity, from_user=user.id if user else None, limit=limit):
                    if isinstance(msg, Message):
                        messages.append(msg)
                messages_by_chat.append({
                    'chat': chat_entity,
                    'messages': messages,
                })
            except Exception as e:
                logger.error(f"[UserMessagesSearch::get_user_messages_from_chats][{client.session.filename}] Error accessing chat {chat}: {e}")

        return messages_by_chat

    @staticmethod
    async def get_user_comments_reactions(client: TelegramClient, channel_usernames: list[str], user: User, limit: int = 50) -> dict[str, dict[str, set[str]]]:
        result = {}

        for channel_username in channel_usernames:
            try:
                # 1. Get the channel and user entities
                channel = await client.get_entity(int(channel_username) if channel_username.isnumeric() else channel_username)
                if isinstance(channel, User):
                    continue

                # 2. Get recent posts from the channel
                posts = await client.get_messages(channel, limit=limit * 10)
                if isinstance(posts, Message):
                    posts = [posts]
            except Exception as e:
                logger.error(f"[UserMessagesSearch::get_user_comments_reactions][{client.session.filename}] Error getting info for {channel_username}: {e}")
                continue

            comments = set()
            reactions = set()

            if not isinstance(posts, Iterable):
                continue

            for post in posts:
                try:
                    if hasattr(post, 'from_id') and post.from_id and hasattr(post.from_id, 'user_id') and post.from_id.user_id == user.id and post.message:
                        comments.add(post.message)

                    # 5. Check if user reacted to this post
                    if post.reactions and post.reactions.recent_reactions:
                        for reaction in post.reactions.recent_reactions:
                            if hasattr(reaction.peer_id, 'user_id') and reaction.peer_id.user_id == user.id:
                                reactions.add(f"Reaction {reaction.reaction.emoticon} on post {post.message}")

                    # 3. Get the linked discussion group (if exists)
                    try:
                        discussion = await client(GetDiscussionMessageRequest(
                            peer=channel,
                            msg_id=post.id
                        ))
                    except Exception as e:
                        if is_dev():
                            logger.error(f"[UserMessagesSearch::get_user_comments_reactions][{client.session.filename}] ⚠️ Linked discussion group error {post.id}: {e}")
                        continue

                    discussion_chat_id = discussion.messages[0].peer_id.channel_id
                    discussion_peer = PeerChannel(discussion_chat_id)

                    # 4. Retrieve comments in discussion group from the user
                    async for msg in client.iter_messages(discussion_peer, from_user=user, limit=limit):
                        if msg.message:
                            comments.add(msg.message)

                    # 6. Check if user reacted to comments in discussion [TOO HEAVY]
                    # async for msg in client.iter_messages(discussion_peer, limit=limit):
                    #     if msg.reactions and msg.reactions.recent_reactions:
                    #         for reaction in msg.reactions.recent_reactions:
                    #             if hasattr(reaction.peer_id, 'user_id') and reaction.peer_id.user_id == user.id:
                    #                 reactions.add(f"Reaction {reaction.reaction.emoticon} on post {msg.message}")

                except ValueError as e:
                    if is_dev():
                        logger.error(f"[UserMessagesSearch::get_user_comments_reactions][{client.session.filename}] ⚠️ Value error: {e}")
                    continue
                except Exception as e:
                    logger.error(f"[UserMessagesSearch::get_user_comments_reactions][{client.session.filename}] ⚠️ Skipping post {post.id}: {e}")
                    continue

            if comments or reactions:
                result[channel_username] = {
                    'comments': comments,
                    'reactions': reactions
                }

        return result

    @staticmethod
    async def get_last_messages_from_chats(client: TelegramClient, chats: list[str], limit: int = 50) -> list[ChatMessages]:
        return await UserMessagesSearch.get_user_messages_from_chats(client=client, chats=chats, limit=limit)

    @staticmethod
    async def get_user_messages_like_status_in_channels(
            bot_client: BotClient,
            channel_usernames: list[str],
            user: str,
            limit: int = 10
    ) -> dict[str, list[dict]]:
        """
        Return dict[channel_username] -> list of user's last messages (up to limit) each with like status.
        like: True  -> at least one like emoji (e.g. 👍) and no unlike emoji
              False -> at least one unlike emoji (e.g. 👎) and no like emoji
              None  -> no reactions or mixed/other reactions
        """
        result: dict[str, list[dict]] = {}

        LIKE_EMOJIS = {"👍"}
        UNLIKE_EMOJIS = {"👎"}
        client = bot_client.client

        for channel_username in channel_usernames:
            try:
                channel = await get_channel_entity_by_username_or_id(client, channel_username)
                if isinstance(channel, User) or channel is None:
                    continue

                messages_list: list[dict] = []

                user_entity = await client.get_entity(user)
                await join_chats(client, [channel_username])
                async for msg in client.iter_messages(channel, from_user=user_entity, limit=limit):
                    if not isinstance(msg, Message) or not msg.message:
                        continue

                    like_status: bool | None = None
                    if msg.reactions:
                        emoticons: set[str] = set()

                        recent = getattr(msg.reactions, "recent_reactions", None) or []
                        for r in recent:
                            try:
                                emoticon = getattr(getattr(r, "reaction", None), "emoticon", None)
                                if emoticon:
                                    emoticons.add(emoticon)
                            except Exception:
                                continue

                        results = getattr(msg.reactions, "results", None) or []
                        for rc in results:
                            try:
                                emoticon = getattr(getattr(rc, "reaction", None), "emoticon", None)
                                if emoticon:
                                    emoticons.add(emoticon)
                            except Exception:
                                continue

                        has_like = bool(emoticons & LIKE_EMOJIS)
                        has_unlike = bool(emoticons & UNLIKE_EMOJIS)

                        if has_like and not has_unlike:
                            like_status = True
                        elif has_unlike and not has_like:
                            like_status = False
                        else:
                            like_status = None

                    messages_list.append({
                        "id": msg.id,
                        "message": msg.message,
                        "like": like_status
                    })

                if messages_list:
                    result[channel_username] = messages_list
            except Exception as e:
                logger.error(
                    f"[UserMessagesSearch::get_user_messages_like_status_in_channels][{bot_client.get_name()}] Error processing {channel_username}: {e}")

        return result