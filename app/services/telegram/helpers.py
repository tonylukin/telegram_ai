import asyncio
import re
from urllib.parse import urlparse

from telethon import TelegramClient
from telethon.errors import UserAlreadyParticipantError, FloodWaitError, UserNotParticipantError, ChannelPrivateError
from telethon.tl.functions.channels import JoinChannelRequest, GetFullChannelRequest, GetParticipantRequest
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.tl.types import PeerChannel
from telethon.types import User
from telethon.tl.types import Channel, Chat

from app.configs.logger import logger


async def get_user_by_username(client: TelegramClient, username: str) -> User | None:
    try:
        user = await client.get_entity(username)
        return user
    except Exception as e:
        logger.error(f"Error: {e}")
        return None


def extract_chat_reference(link: str):
    """Extract channel username or invite hash."""
    if re.match(r'^@?\w+$', link):  # Handle @channel_name
        return link.lstrip('@'), 'public'
    elif 'joinchat/' in link or '+' in link:
        invite_hash = link.split('/')[-1].split('+')[-1]
        return invite_hash, 'private'
    elif 't.me/' in link:
        parsed = urlparse(link)
        path = parsed.path.strip('/')
        if path:
            return path, 'public'
    return None, 'unknown'


async def join_chats(client: TelegramClient, chats_to_join: list[str]):
    for link in chats_to_join:
        try:
            identifier, kind = extract_chat_reference(link)

            if not identifier:
                logger.warning(f"⚠️ Could not parse: {link}")
                continue

            if kind == 'public':
                full = await client(GetFullChannelRequest(identifier))
                if await is_user_in_group(client, full.full_chat):
                    continue
                await client(JoinChannelRequest(identifier))
                linked_chat_id = full.full_chat.linked_chat_id
                if linked_chat_id:
                    await client(JoinChannelRequest(PeerChannel(linked_chat_id)))
                logger.info(f"✅ Joined public: {identifier}")
            elif kind == 'private':
                await client(ImportChatInviteRequest(identifier))
                logger.info(f"✅ Joined private invite: {identifier}")
            else:
                logger.warning(f"⚠️ Unknown type for: {link}")

            await asyncio.sleep(5)  # delay to avoid spam detection

        except UserAlreadyParticipantError:
            logger.info(f"🟡 Already a member: {link}")
        except FloodWaitError as e:
            logger.warning(f"⏳ Rate limited. Sleeping for {e.seconds} seconds")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            logger.error(f"❌ Error joining {link}: {e}")


async def is_user_in_group(client: TelegramClient, chat: Channel|Chat) -> bool:
    try:
        result = await client(GetParticipantRequest(channel=chat, participant='me'))
        return True
    except UserNotParticipantError:
        return False
    except ChannelPrivateError:
        return False

async def get_chat_from_channel(client: TelegramClient, channel: Channel) -> Channel | int |None:
    if channel.broadcast:
        full = await client(GetFullChannelRequest(channel.id))
        linked_chat_id = full.full_chat.linked_chat_id
        if not linked_chat_id:
            logger.error(f"{channel.username} does not have a full chat")
            return None

        return linked_chat_id

    return channel


async def resolve_tg_link(client, link: str):
    """
    Универсальный парсер Telegram-ссылки: t.me/username или t.me/+invite
    Возвращает entity (Channel, Chat и т.п.)
    """
    tag = link
    # Очистка
    link = link.strip().replace("https://", "").replace("http://", "")

    # Извлекаем "somechat" или "+abcXYZ"
    match = re.match(r"(t|telegram)\.me/([\w\d_+-]+)", link)
    if match:
        tag = match.group(2)

    if tag.startswith('+'):  # инвайт-ссылка
        invite_hash = tag[1:]
        try:
            update = await client(ImportChatInviteRequest(invite_hash))
            return update.chats[0]
        except UserAlreadyParticipantError:
            # Если уже вступил — можно просто получить entity по username
            return await client.get_entity(invite_hash)
    else:
        # Обычный username
        return await client.get_entity(tag)

# todo test on this
def extract_username_or_name(text: str) -> str:
    """
    Извлекает Telegram username или возвращает имя как есть.

    Юзкейсы:
    - "https://t.me/username" -> "@username"
    - "http://telegram.me/username" -> "@username"
    - "t.me/username" -> "@username"
    - "@username" -> "@username"
    - "Иван Иванов" -> "Иван Иванов"
    """
    if not text or not isinstance(text, str):
        return ""

    text = text.strip()

    # Match ссылки t.me/username или telegram.me/username
    match = re.search(r'(?:https?://)?(?:t(?:elegram)?\.me)/@?([a-zA-Z0-9_]{5,})', text)
    if match:
        return f"@{match.group(1)}"

    # Match @username
    match = re.match(r'^@([a-zA-Z0-9_]{5,})$', text)
    if match:
        return f"@{match.group(1)}"

    # Ни username, ни ссылка — возвращаем как есть
    return text
