from abc import abstractmethod, ABC

class AiClientBase(ABC):
    @abstractmethod
    def generate_text(self, prompt: str) -> str:
        pass

    @abstractmethod
    def generate_image(self, prompt: str) -> str|None:
        pass
