from abc import abstractmethod, ABC
from typing import TypedDict

class NewsItem(TypedDict):
    text: str

class NewsMakerBase(ABC):
    @abstractmethod
    def get_news(self, count: int = None) -> list[NewsItem]:
        pass
