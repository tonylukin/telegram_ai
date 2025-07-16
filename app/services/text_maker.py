import hashlib
import random
from typing import TypedDict, List

from fastapi.params import Depends
from sqlalchemy.orm import Session

from app.config import AI_NEWS_POST_IMAGE, AI_NEWS_POST_TEXT, IMAGE_CREATION_PROBABILITY, PERSONS, \
    AI_MASS_NEWS_POST_TEXT, AI_NEWS_EMOTIONS
from app.configs.logger import logging
from app.dependencies import get_db
from app.models.news_post import NewsPost
from app.services.ai.ai_client_base import AiClientBase
from app.services.ai.gemini_client import GeminiClient
from app.services.ai.open_ai_client import OpenAiClient
from app.services.news.news_api_client import NewsApiClient
from app.services.news.news_maker_base import NewsMakerBase, NewsItem


def get_news_maker() -> NewsMakerBase:
    return NewsApiClient()

def get_ai_client() -> AiClientBase:
    return GeminiClient()

def get_ai_client_images() -> AiClientBase:
    # return HuggingFaceClient()
    return OpenAiClient()

def get_persons() -> List[str]:
    return PERSONS

class TextMakerDependencyConfig:
    def __init__(
            self,
            news_maker: NewsMakerBase = Depends(get_news_maker),
            ai_client: AiClientBase = Depends(get_ai_client),
            ai_client_images: AiClientBase = Depends(get_ai_client_images),
            persons: List[str] = Depends(get_persons),
            session: Session = Depends(get_db)
    ):
        self.news_maker = news_maker
        self.ai_client = ai_client
        self.ai_client_images = ai_client_images
        self.persons = persons
        self.session = session

class Response(TypedDict):
    original: str | None
    generated: str
    person: str | None
    image: str | None

class TextMaker:
    def __init__(self, config: TextMakerDependencyConfig):
        self.news_maker = config.news_maker
        self.ai_client = config.ai_client
        self.ai_client_images = config.ai_client_images
        self.session = config.session
        self.persons = config.persons

    def create_texts(self, count: int = None, person: str = None) -> list[Response]:
        news_list = self.news_maker.get_news(count)

        if count is None:
            return self.__create_compound_text(news_list, person)

        response_list = []
        for news in news_list:
            news_text = news.get('text')
            external_id = TextMaker.__generate_external_id(news_text)
            if self.__get_post_by_external_id(external_id) is not None:
                logging.info(f'Skipping {news_text} \'{external_id}\' exists')
                continue

            by_person = person or random.choice(self.persons)
            emotion = random.choice(AI_NEWS_EMOTIONS)
            try:
                text = self.ai_client.generate_text(f"{emotion} {AI_NEWS_POST_TEXT.format(news_text=news_text, by_person=by_person)}")
                image = None
                if IMAGE_CREATION_PROBABILITY < 1 and random.choice(range(1, 101)) <= int(IMAGE_CREATION_PROBABILITY * 100):
                    image = self.ai_client_images.generate_image(AI_NEWS_POST_IMAGE.format(news_text=news_text, by_person=by_person))
            except Exception as e:
                logging.error(f'Skipping news {news_text}, error: {e}')
                continue
            response = Response(original=news_text, generated=text, person=by_person, image=image)
            response_list.append(response)
            self.__save_to_db(response, external_id)

        return response_list

    def __create_compound_text(self, news_list: list[NewsItem], person: str = None) -> list[Response]:
        def is_new_news_item(news_item: NewsItem):
            news_item_external_id = TextMaker.__generate_external_id(news_item['text'])
            return self.__get_post_by_external_id(news_item_external_id) is None

        try:
            news_texts = list(
                map(
                    lambda news_item: news_item.get('text'),
                    filter(is_new_news_item, news_list)
                )
            )
            by_person = person or random.choice(self.persons)
            emotion = random.choice(AI_NEWS_EMOTIONS)
            text = self.ai_client.generate_text(
                f"{emotion} {AI_MASS_NEWS_POST_TEXT.format(news_items=news_texts, by_person=by_person)}"
            )

            original = '\n\n'.join(news_texts)
            external_id = TextMaker.__generate_external_id(original)
            if self.__get_post_by_external_id(external_id) is not None:
                logging.info(f'Skipping {text} \'{external_id}\' exists')
        except Exception as e:
            logging.error(e)
            return []

        response = Response(generated=text, person=by_person, original=original, image=None)
        self.__save_to_db(response, external_id)
        return [response]

    @staticmethod
    def __generate_external_id(text: str) -> str:
        return hashlib.md5(text.encode()).hexdigest()

    def __get_post_by_external_id(self, external_id: str) -> NewsPost | None:
        return self.session.query(NewsPost).filter_by(external_id=external_id).first()

    def __save_to_db(self, response: Response, external_id: str):
        try:
            post = NewsPost(
                external_id=external_id,
                original_text=response["original"],
                generated_text=response["generated"],
                person=response["person"]
            )
            self.session.add(post)
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            logging.error(e)
        finally:
            self.session.close()
