from app.db.session import Session as SQLAlchemySession
from sqlalchemy.orm import Session
from fastapi import Depends

from app.services.ai.ai_client_base import AiClientBase
from app.services.ai.gemini_client import GeminiClient
from app.services.ai.open_ai_client import OpenAiClient
from app.services.news.news_api_client import NewsApiClient
from app.services.news.news_maker_base import NewsMakerBase


def get_db():
    db = SQLAlchemySession()
    try:
        yield db
    finally:
        db.close()

def get_news_maker() -> NewsMakerBase:
    return NewsApiClient()

def get_ai_client() -> AiClientBase:
    return GeminiClient()

def get_ai_client_images() -> AiClientBase:
    # return HuggingFaceClient()
    return OpenAiClient()
