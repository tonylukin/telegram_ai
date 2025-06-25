import base64

import requests

from app.config import HUGGING_FACE_API_KEY
from app.services.ai.ai_client_base import AiClientBase


class HuggingFaceClient(AiClientBase):
    def generate_image(self, prompt: str) -> str|None:
        # url = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-2"
        # url = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"
        url = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-2-1"
        headers = {"Authorization": f"Bearer {HUGGING_FACE_API_KEY}"}

        data = {"inputs": prompt}
        response = requests.post(url, headers=headers, json=data)

        if response.status_code == 200:
            image_data = response.content
            encoded_image = base64.b64encode(image_data).decode('utf-8')
            return encoded_image

        print(response.text)
        return None

    def generate_text(self, prompt: str) -> str:
        pass




