from datetime import datetime, timedelta

from fastapi.params import Depends
from sqlalchemy.orm import Session

from app.config import IG_AI_USER_INFO_PROFILE_PROMPT_RU, IG_AI_USER_INFO_PROFILE_PROMPT_EN
from app.configs.logger import logger
from app.db.queries.ig_user import get_ig_user_by_username
from app.dependencies import get_db, get_open_ai_client
from app.models.ig_user import IgUser
from app.services.ai.ai_client_base import AiClientBase
from app.services.apify.instagram_scrapper_client import InstagramScrapperClient


class InstagramUserInfoCollector:
    _translations = {
        'ru': {
            'profile_prompt': IG_AI_USER_INFO_PROFILE_PROMPT_RU,
        },
        'en': {
            'profile_prompt': IG_AI_USER_INFO_PROFILE_PROMPT_EN,
        },
    }

    def __init__(
            self,
            ai_client: AiClientBase = Depends(get_open_ai_client),
            session: Session = Depends(get_db),
            instagram_scrapper_client: InstagramScrapperClient = Depends(),
    ):
        self._ai_client = ai_client
        self._session = session
        self._instagram_scrapper_client = instagram_scrapper_client

    async def get_user_info(self, username: str, prompt: str = None, lang: str = 'ru') -> dict | None:
        username = username.lstrip('@').lower()
        user_found = get_ig_user_by_username(self._session, username)
        date_interval = datetime.now() - timedelta(weeks=12)
        if user_found and user_found.updated_at and user_found.updated_at > date_interval:
            logger.info(f"User {user_found.username} has fresh info")
            return user_found.description

        profile_data = await self._instagram_scrapper_client.get_data(username)
        if profile_data is None:
            return None

        logger.info(f"Data from {username}: {profile_data}")
        overview = self._ai_client.generate_text(
            (prompt or self._translations.get(lang).get('profile_prompt')).format(
                related=profile_data.get('related'),
                posts=profile_data.get('posts'),
                bio=profile_data.get('bio', ''),
            )
        )
        full_desc = {
            'description': overview,
            'posts': len(profile_data.get('posts')),
            'bio': profile_data.get('bio'),
        }
        self.__save_to_db(user_found, username, full_desc)

        return full_desc

    def __save_to_db(self, user_found: IgUser | None, username: str, full_desc: dict[str, str]) -> None:
        try:
            if user_found is None:
                user_found = IgUser(username=username, description=full_desc)
                self._session.add(user_found)

            user_found.description = full_desc
            user_found.updated_at = datetime.now()
            self._session.commit()
        except Exception as e:
            self._session.rollback()
            logger.error(e)

