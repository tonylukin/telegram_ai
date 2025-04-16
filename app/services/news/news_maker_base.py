from abc import abstractmethod, ABC
from typing import TypedDict, List

class NewsItem(TypedDict):
    text: str

class NewsMakerBase(ABC):
    @abstractmethod
    def get_news(self, count: int) -> List[NewsItem]:
        pass
