from huggingface_hub import InferenceClient
from PIL import Image, ImageOps
import logging

from plugins.base_plugin.base_plugin import BasePlugin

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "black-forest-labs/FLUX.1-schnell"


class TextoImagem(BasePlugin):
    def generate_settings_template(self):
        template_params = super().generate_settings_template()
        template_params["api_key"] = {
            "required": True,
            "service": "Hugging Face",
            "expected_key": "HF_TOKEN",
        }
        return template_params

    def generate_image(self, settings, device_config):
        logger.info("=== Texto Imagem Plugin: Starting image generation ===")

        api_key = device_config.load_env_key("HF_TOKEN")
        if not api_key:
            logger.error("HF_TOKEN not configured")
            raise RuntimeError("HF_TOKEN not configured.")

        text_prompt = (settings.get("textPrompt") or "").strip()
        if not text_prompt:
            logger.error("Text prompt not provided")
            raise RuntimeError("Text Prompt is required.")

        model = settings.get("model") or DEFAULT_MODEL
        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]

        logger.info("Generating image with model '%s'", model)

        try:
            client = InferenceClient(provider="auto", api_key=api_key)
            image = client.text_to_image(text_prompt, model=model)
        except Exception as error:
            logger.error("Failed to make Hugging Face request: %s", error)
            raise RuntimeError("Hugging Face request failure, please check logs.") from error

        image = ImageOps.fit(image.convert("RGB"), dimensions, method=Image.Resampling.LANCZOS)

        logger.info(
            "=== Texto Imagem Plugin: Image generation complete (%sx%s) ===",
            image.size[0],
            image.size[1],
        )
        return image