from typing import Dict, List, Any

from app.configs.logger import logger
from app.services.apify.base_apify_client import BaseApifyClient


class TikTokScrapperClient(BaseApifyClient):
    async def get_data(self, username: str) -> dict[str, list] | None:
        try:
            # profile_data = self.__get_following_followers(username)
            profile_data = {}
            profile_data.update(self.__get_posts(username))
        except Exception as e:
            logger.error(e)
            return None

        return profile_data

    # @deprecated
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
        items = self._run_apify_actor(actor_id='clockworks~tiktok-scraper', payload=payload)

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
        items = self._run_apify_actor(actor_id='clockworks~tiktok-profile-scraper', payload=payload)

        if items and items[0].get('error'):
            raise Exception(items[0].get('error'))

        posts = []
        for it in items:
            post = {
                "id": it.get("id"),
                "text": it.get("text", "").strip(),
                "create_time": it.get("createTimeISO") or it.get("createTime"),
                "place": it.get("locationCreated") or None,
                "video_url": it.get("webVideoUrl") or None,
            }
            if post.get('id'):
                posts.append(post)

        return {
            'posts': posts,
        }
