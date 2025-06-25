import asyncio
import re
from urllib.parse import urlparse

from telethon import TelegramClient
from telethon.errors import UserAlreadyParticipantError, FloodWaitError
from telethon.tl.functions.channels import JoinChannelRequest, GetFullChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.tl.types import PeerChannel
from telethon.types import User

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
                await client(JoinChannelRequest(identifier))
                full = await client(GetFullChannelRequest(identifier))
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
