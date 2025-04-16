from app.services.ai.ai_client_base import AiClientBase
from diffusers import StableDiffusionPipeline
from diffusers import DiffusionPipeline
import torch
import base64
import io

class StableDiffusion(AiClientBase):
    def __init__(self):
        self.pipe = DiffusionPipeline.from_pretrained("ByteDance/sd2.1-base-zsnr-laionaes6")
        # self.pipe = StableDiffusionPipeline.from_pretrained("runwayml/stable-diffusion-v1-5", torch_dtype=torch.float16)
        # self.pipe.to("cpu")

    def generate_image(self, prompt: str) -> str:
        image = self.pipe(prompt).images[0]

        """Convert a PIL image to a Base64-encoded string."""
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode("utf-8")

    def generate_text(self, prompt: str) -> str:
        pass