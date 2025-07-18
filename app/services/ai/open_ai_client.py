import base64

import openai
import requests

from app.config import OPENAI_API_KEY
from app.services.ai.ai_client_base import AiClientBase


class OpenAiClient(AiClientBase):
    def __init__(self):
        super().__init__()
        openai.api_key = OPENAI_API_KEY
        self.client = openai.OpenAI(api_key=OPENAI_API_KEY)

    def generate_text(self, prompt: str):
        model: str = "gpt-4"
        response = self.client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content

    def generate_image(self, prompt: str) -> str|None:
        response = self.client.images.generate(
            # model="dall-e-2",
            model="dall-e-3",  # Или "dall-e-3" для более качественных изображений
            prompt=prompt,
            n=1,
            # size="256x256"
        )

        image_url = response.data[0].url
        img_response = requests.get(image_url)
        if img_response.status_code == 200:
            image_base64 = base64.b64encode(img_response.content).decode("utf-8")
            return image_base64
        else:
            return None
