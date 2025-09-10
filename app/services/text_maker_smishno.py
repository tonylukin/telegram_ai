import random
from typing import TypedDict

from fastapi.params import Depends
from sqlalchemy.orm import Session

from app.config import AI_SMISHNO_JOKE_ADJECTIVES, AI_SMISHNO_TEXT_PROMPT
from app.configs.logger import logging, logger
from app.dependencies import get_db
from app.services.ai.ai_client_base import AiClientBase
from app.services.news.news_maker_base import NewsMakerBase
from app.services.text_maker import get_ai_client_images, get_ai_client, get_news_maker


class Response(TypedDict):
    original: str | None
    generated: str
    adjective: str
    image: str | None

class TextMakerSmishno:
    def __init__(
            self,
            news_maker: NewsMakerBase = Depends(get_news_maker),
            ai_client: AiClientBase = Depends(get_ai_client),
            ai_client_images: AiClientBase = Depends(get_ai_client_images),
            session: Session = Depends(get_db)
    ):
        self.news_maker = news_maker
        self.ai_client = ai_client
        self.ai_client_images = ai_client_images
        self.session = session

    def create_text(self) -> Response | None:
        news_list = self.news_maker.get_news(1)
        if not news_list:
            return None

        try:
            news_item = news_list[0]
            adjective = random.choice(AI_SMISHNO_JOKE_ADJECTIVES)
            prompt = AI_SMISHNO_TEXT_PROMPT.format(news_text=news_item.get('text'), joke_adjective=adjective)
            generated_text = self.ai_client.generate_text(prompt=prompt)
            image = None
            try:
                image = self.ai_client_images.generate_image(prompt=prompt)
            except Exception as e:
                logger.error(f'TEXT MAKER SMISHNO ERROR: {e}')

            return Response(original=news_item.get('text'), generated=generated_text, adjective=adjective, image=image)
        except Exception as e:
            logging.error(f'Skipping news, error: {e}')
            return None
