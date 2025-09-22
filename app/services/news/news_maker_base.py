from abc import abstractmethod, ABC
from typing import TypedDict, NotRequired

class NewsItem(TypedDict):
    text: NotRequired[str]
    title: NotRequired[str]
    url: NotRequired[str]

class NewsMakerBase(ABC):
    @abstractmethod
    def get_news(self, count: int = None) -> list[NewsItem]:
        pass

    @abstractmethod
    def get_political_news(self, count: int = None) -> list[NewsItem]:
        pass
