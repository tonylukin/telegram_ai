import os
from datetime import datetime, timedelta

from fastapi.params import Depends
from sqlalchemy.orm import Session

from app.config import TIKTOK_AI_USER_INFO_PROFILE_PROMPT_RU, TIKTOK_AI_USER_INFO_PROFILE_PROMPT_EN
from app.configs.logger import logger
from app.db.queries.ig_user import get_ig_user_by_username
from app.dependencies import get_db, get_ai_client
from app.models.tiktok_user import TikTokUser
from app.services.ai.ai_client_base import AiClientBase
from app.services.apify.tiktok_scrapper_client import TikTokScrapperClient

class TikTokUserInfoCollector:
    __translations = {
        'ru': {
            'profile_prompt': TIKTOK_AI_USER_INFO_PROFILE_PROMPT_RU,
        },
        'en': {
            'profile_prompt': TIKTOK_AI_USER_INFO_PROFILE_PROMPT_EN,
        },
    }

    def __init__(
            self,
            ai_client: AiClientBase = Depends(get_ai_client),
            session: Session = Depends(get_db),
            tiktok_scrapper_client: TikTokScrapperClient = Depends(),
    ):
        self.ai_client = ai_client
        self.session = session
        self.tiktok_scrapper_client = tiktok_scrapper_client

    async def get_user_info(self, username: str, prompt: str = None, lang: str = 'ru') -> dict | None:
        user_found = get_ig_user_by_username(self.session, username)
        date_interval = datetime.now() - timedelta(weeks=12)
        if user_found and user_found.updated_at and user_found.updated_at > date_interval:
            logger.info(f"User {user_found.username} has fresh info")
            return user_found.description

        profile_data = await self.tiktok_scrapper_client.get_data(username)
        if profile_data is None:
            return None

        logger.info(f"Data from {username}: {profile_data}")
        overview = self.ai_client.generate_text(
            (prompt or self.__translations.get(lang).get('profile_prompt')).format(
                followers=profile_data.get('followers'),
                following=profile_data.get('following'),
                posts=profile_data.get('posts'),
            )
        )
        full_desc = {
            'description': overview,
            'followers': len(profile_data.get('followers')),
            'following': len(profile_data.get('following')),
            'posts': len(profile_data.get('posts')),
        }
        self.__save_to_db(user_found, username, full_desc)

        return full_desc

    def __save_to_db(self, user_found: TikTokUser | None, username: str, full_desc: dict[str, str]) -> None:
        try:
            if user_found is None:
                user_found = TikTokUser(username=username, description=full_desc)
                self.session.add(user_found)

            user_found.description = full_desc
            user_found.updated_at = datetime.now()
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            logger.error(e)
