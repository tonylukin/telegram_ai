from app.services.news.news_maker_base import NewsMakerBase, NewsItem
import requests
from app.config import NEWS_API_ORG_API_KEY
from typing import List

class NewsApiClient(NewsMakerBase):
    def get_news(self, count: int) -> List:
        url = f"https://newsapi.org/v2/everything?apiKey={NEWS_API_ORG_API_KEY}&language=ru&sources=lenta&sortBy=publishedAt&pageSize={count}&page=1"
        response = requests.get(url)
        data = response.json()
        return [NewsItem(text=newsData['description']) for newsData in data["articles"]]
