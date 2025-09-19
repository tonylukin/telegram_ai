from app.configs.logger import logger
from app.services.apify.base_apify_client import BaseApifyClient


class InstagramScrapperClient(BaseApifyClient):
    async def get_data(self, username: str) -> dict[str, list | dict] | None:
        try:
            data = {}

            profile_data = self.__get_profile(username)
            if profile_data:
                data.update({
                    'bio': profile_data.get('profile').get('biography'),
                    'posts': profile_data.get('profile').get('latestPosts'),
                    'related': profile_data.get('profile').get('relatedProfiles'),
                })

            return data if data else None

        except Exception as e:
            logger.error(f"Instagram scraper error for '{username}': {e}")
            return None

    def __get_profile(self, username: str) -> dict[str, dict] | None:
        try:
            actor_id = "apify/instagram-profile-scraper"
            run_input = {
                "usernames": [username],
                # "resultsType": "details" # Этот параметр может быть устаревшим, актор сам вернет детали
            }

            resp = self._run_apify_actor(actor_id, run_input)

            if resp and len(resp) > 0:
                return {"profile": resp[0]}

            logger.warning(f"Profile not found for username: {username}")
            return None

        except Exception as e:
            logger.error(f"Error fetching profile details for '{username}': {e}")
            return None

    def __get_posts(self, username: str, posts_limit: int = 30) -> dict[str, list] | None:
        try:
            actor_id = "apify/instagram-scraper"
            run_input = {
                "usernames": [username],
                "resultsType": "posts",
                "resultsLimit": posts_limit,
            }

            resp = self._run_apify_actor(actor_id, run_input)

            if not resp:
                return {"posts": []}

            posts = [
                {
                    "id": item.get("id"),
                    "caption": item.get("caption"),
                    "url": item.get("url"),
                    "likes": item.get("likesCount"),
                    "comments": item.get("commentsCount"),
                    "timestamp": item.get("timestamp"),
                }
                for item in resp
            ]
            return {"posts": posts}
        except Exception as e:
            logger.error(f"Error fetching posts for '{username}': {e}")
            return None

    def __get_followers(self, username: str, limit: int = 50) -> dict[str, list] | None:
        try:
            # NOTE: Этот актор может быть нестабильным.
            actor_id = "apify/instagram-follower-scraper"
            run_input = {
                "username": [username],  # Некоторые акторы ожидают массив
                "limit": limit,
            }
            resp = self._run_apify_actor(actor_id, run_input)

            if not resp:
                return {"followers": []}

            return {"followers": [user.get("username") for user in resp]}
        except Exception as e:
            logger.error(f"Error fetching followers for '{username}': {e}")
            return None

    def __get_following(self, username: str, limit: int = 50) -> dict[str, list] | None:
        try:
            # NOTE: Этот актор может быть нестабильным.
            actor_id = "apify/instagram-following-scraper"
            run_input = {
                "username": [username],
                "limit": limit,
            }
            resp = self._run_apify_actor(actor_id, run_input)

            if not resp:
                return {"following": []}

            return {"following": [user.get("username") for user in resp]}
        except Exception as e:
            logger.error(f"Error fetching following for '{username}': {e}")
            return None