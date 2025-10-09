from typing import TypedDict

from fastapi.params import Depends
from sqlalchemy.orm import Session

from app.config import AI_WHAT_IN_FUTURE_TEXT_PROMPT
from app.configs.logger import logger
from app.dependencies import get_db, get_ai_client, get_news_maker
from app.services.ai.ai_client_base import AiClientBase
from app.services.news.news_maker_base import NewsMakerBase

class Response(TypedDict):
    original: str | None
    generated: str

class TextMakerWhatInTheFuture:
    def __init__(
            self,
            news_maker: NewsMakerBase = Depends(get_news_maker),
            ai_client: AiClientBase = Depends(get_ai_client),
            session: Session = Depends(get_db)
    ):
        self._news_maker = news_maker
        self._ai_client = ai_client
        self._session = session

    def create_text(self) -> Response | None:
        news_list = self._news_maker.get_political_news(1)
        if not news_list:
            return None

        try:
            news_item = news_list[0]
            prompt = AI_WHAT_IN_FUTURE_TEXT_PROMPT.format(title=news_item.get('title'), url=news_item.get('url'))
            generated_text = self._ai_client.generate_text(prompt=prompt)
            original_text = f'{news_item.get('title')}\n\n{news_item.get('url')}'

            return Response(original=original_text, generated=generated_text)
        except Exception as e:
            logger.error(f'[TextMaker::What_in_the_future] Skipping news, error: {e}')
            return None
