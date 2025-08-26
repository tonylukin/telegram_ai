from typing import Dict, List, Any

import requests

from app.config import APIFY_API_TOKEN
from app.configs.logger import logger


class TikTokScrapperClient:
    async def get_data(self, username: str) -> dict[str, list] | None:
        try:
            profile_data = self.__get_following_followers(username)
            profile_data.update(self.__get_posts(username))
        except Exception as e:
            logger.error(e)
            return None

        return profile_data

    def __get_following_followers(self, nickname: str, follow_limit: int = 50):
        payload = {
            "profiles": [nickname.lstrip('@')],
            # how many items per page; actor will paginate internally
            "resultsPerPage": max(10, min(100, follow_limit)),
            # fetch followers + following lists:
            "profileConnectionTypes": ["follower", "following"],
            # fetch posts:
            "profileScrapeSections": ["videos"],
            # don’t download media; we just need metadata
            "shouldDownloadVideos": False,
            "shouldDownloadCovers": False,
            "shouldDownloadSubtitles": False,
            "shouldDownloadSlideshowImages": False,
            # optional: country routing (or use Apify proxy groups if needed)
            "proxyCountryCode": "None"
        }
        items = self.__run_apify_actor(actor_id='clockworks~tiktok-scraper', payload=payload)

        followers: List[str] = []
        following: List[str] = []
        for it in items:
            # Connections: look for hints in item keys
            # Common fields include something like "connectionType", "username"/"uniqueId"
            ct = (it.get("connectionType") or it.get("profileConnectionType") or "").lower()
            handle = it.get("authorMeta").get('name')
            if ct == "follower" and handle:
                followers.append(handle)
                continue
            if ct == "following" and handle:
                following.append(handle)
                continue

        return {
            "followers": followers,
            "following": following,
        }

    def __get_posts(self, nickname: str, posts_limit: int = 30) -> dict[str, list]:
        payload = {
            "profiles": [nickname.lstrip('@')],
            "resultsPerPage": posts_limit,
            "shouldDownloadCovers": False,
            "shouldDownloadVideos": False,
            "shouldDownloadSubtitles": False,
            "shouldDownloadSlideshowImages": False,
        }
        items = self.__run_apify_actor(actor_id='clockworks~tiktok-profile-scraper', payload=payload)
        posts = []
        for it in items:
            post = {
                "id": it.get("id"),
                "text": it.get("text", "").strip(),
                "create_time": it.get("createTimeISO") or it.get("createTime"),
                "place": it.get("locationCreated") or None,
                "video_url": it.get("webVideoUrl") or None,
            }
            posts.append(post)

        return {
            'posts': posts,
        }

    def __run_apify_actor(self, actor_id: str, payload: dict):
        url = f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items"
        params = {
            "token": APIFY_API_TOKEN,
            "format": "json",
            "clean": "true"
        }
        resp = requests.post(url, params=params, json=payload, timeout=600)
        if resp.status_code >= 300:
            logger.error(f"Apify actor failed with status code: [{resp.status_code}] {resp.text}")
            raise RuntimeError(resp.text)

        return resp.json()