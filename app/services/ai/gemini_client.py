import base64
from io import BytesIO

# from google import genai
import google.generativeai as genai
from PIL import Image

from app.config import GEMINI_API_KEY, GEMINI_TEXT_MODEL, GEMINI_IMAGE_MODEL
from app.services.ai.ai_client_base import AiClientBase


class GeminiClient(AiClientBase):
    def __init__(self):
        super().__init__()
        # self.client = genai.Client(api_key=GEMINI_API_KEY)
        genai.configure(api_key=GEMINI_API_KEY)

    def generate_image(self, prompt: str):
        pass
        response = self.client.models.generate_images( #todo this will not work
            model=GEMINI_IMAGE_MODEL,
            prompt=prompt,
            config=genai.types.GenerateImagesConfig(
                number_of_images=1
            )
        )
        buffered = BytesIO()
        for generated_image in response.generated_images:
            image = Image.open(BytesIO(generated_image.image.image_bytes))
            image.save(buffered, format="PNG")
            return base64.b64encode(buffered.getvalue()).decode("utf-8")

        return None

    def generate_text(self, prompt: str) -> str:
        model = genai.GenerativeModel(model_name=GEMINI_TEXT_MODEL)
        response = model.generate_content(prompt)
        return response.text
