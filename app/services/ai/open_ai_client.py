import base64

import openai
import requests

from app.config import OPENAI_API_KEY, OPEN_AI_TEXT_MODEL, OPEN_AI_IMAGE_MODEL
from app.services.ai.ai_client_base import AiClientBase


class OpenAiClient(AiClientBase):
    def __init__(self):
        super().__init__()
        openai.api_key = OPENAI_API_KEY
        self.client = openai.OpenAI(api_key=OPENAI_API_KEY)

    def generate_text(self, prompt: str):
        # model: str = "gpt-4"
        model: str = OPEN_AI_TEXT_MODEL
        response = self.client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content

    def generate_image(self, prompt: str) -> str | None:
        is_gpt_image = "gpt-image" in OPEN_AI_IMAGE_MODEL

        # Base payload accepted by all OpenAI image models
        kwargs = {
            "model": OPEN_AI_IMAGE_MODEL,
            "prompt": prompt,
        }

        if is_gpt_image:
            # Pass new model arguments inside extra_body to bypass SDK validation
            kwargs["extra_body"] = {
                "quality": "auto",
                "aspect_ratio": "1:1"
            }
        else:
            # Legacy parameters for DALL-E models
            kwargs["n"] = 1
            kwargs["size"] = "1024x1024"

        try:
            response = self.client.images.generate(**kwargs)
            image_url = response.data[0].url

            img_response = requests.get(image_url)
            if img_response.status_code == 200:
                image_base64 = base64.b64encode(img_response.content).decode("utf-8")
                return image_base64
        except Exception as e:
            print(f"Generation error: {e}")

        return None
