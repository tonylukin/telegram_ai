import requests
from telethon import TelegramClient
from telethon.errors import ChannelPrivateError, UserNotParticipantError
from telethon.tl.functions.channels import GetFullChannelRequest, GetParticipantRequest, JoinChannelRequest

from app.config import TELEMETR_API_KEY
from app.configs.logger import logger
from app.services.telegram.chat_searcher import ChatSearcher
from app.services.telegram.helpers import is_user_in_group

PAGE_SIZE = 30

class ChannelsApiFetcher:
    @staticmethod
    def __fetch_channels(params: dict = None):
        url = "https://api.telemetr.io/v1/channels/search"

        params = {
            "peer_type": "Group",
            "country": "russia",
            "limit": PAGE_SIZE,
            ** (params or {}),
        }

        headers = {
            "accept": "application/json",
            "x-api-key": TELEMETR_API_KEY
        }
        logger.info(f"Request {params} {headers}")

        response = requests.get(url, headers=headers, params=params)
        channels = list(response.json())
        return channels

    async def get_postable_channels(self, client: TelegramClient, params: dict = None) -> list[tuple[str, str, int]]:
        results = []
        if params is None:
            params = {}

        skip = 0
        while True:
            params.update({"skip": skip})
            try:
                channels = self.__fetch_channels(params)
            except Exception as e:
                logger.error(e)
                channels = []

            logger.info(f"Found {len(channels)} channels")
            results.extend(await self.__get_postable_channels(client, channels))

            skip += PAGE_SIZE
            if not channels or len(channels) != PAGE_SIZE:
                break

        return results

    async def __get_postable_channels(self, client: TelegramClient, channels) -> list[tuple[str, str, int]]:
        results = []

        for ch in channels:
            title = ch.get("title")
            if not title or not ch.get("members_count") or ch["members_count"] < 5000:
                continue

            try:
                channels_found = await ChatSearcher.search_chats(client, title)
                if not channels_found:
                    logger.info(f"No channels found for {title}")
                    continue

                channel = channels_found[0]
                if not channel.broadcast and channel.username:
                    results.append(('@'+channel.username, title, ch["members_count"]))
                else:
                    logger.info(f"Is broadcast {title}")

            except (UserNotParticipantError, ChannelPrivateError):
                logger.info(f"❌ Not a member or private: {title}")
            except Exception as e:
                logger.error(f"⚠️ Error on {title}: {e}")

        return results
