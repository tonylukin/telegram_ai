from typing import Dict, List, Any

import requests

from app.config import APIFY_API_TOKEN
from app.configs.logger import logger
from app.services.apify.apify_client import ApifyClient


class InstagramScrapperClient(ApifyClient):
    async def get_data(self, username: str) -> dict[str, list] | None:
        try:
            profile_data = self.__get_following_followers(username)
            profile_data.update(self.__get_posts(username))
        except Exception as e:
            logger.error(e)
            return None

        return profile_data

    def __get_following_followers(self, nickname: str, follow_limit: int = 50):
        return {
            "followers": [],
            "following": [],
        }

    def __get_posts(self, nickname: str, posts_limit: int = 30) -> dict[str, list]:
        return {
            'posts': [],
        }
