"""
Famous Quotes Plugin for InkyPi
This plugin fetches famous quotes from the API Ninjas Quotes API v2
and displays them on the InkyPi device with optional category filtering.
"""

from plugins.base_plugin.base_plugin import BasePlugin
from PIL import Image
from utils.http_client import get_http_session
import logging

logger = logging.getLogger(__name__)


class FamousQuotes(BasePlugin):
    def generate_settings_template(self):
        template_params = super().generate_settings_template()
        template_params['api_key'] = {
            "required": True,
            "service": "API Ninjas",
            "expected_key": "API_NINJAS"
        }
        template_params['style_settings'] = True
        return template_params

    def generate_image(self, settings, device_config):
        logger.info("=== Famous Quotes Plugin: Starting image generation ===")

        api_key = device_config.load_env_key("API_NINJAS")
        if not api_key:
            logger.error("API Ninjas API Key not configured")
            return self._render_error_image(
                device_config,
                settings,
                "Missing API key"
            )

        # Get category setting
        category = settings.get("category", "random")
        
        # Fetch quote from API
        quote_data = self._fetch_quote(api_key, category)
        
        if not quote_data:
            logger.error("Failed to fetch quote or API returned empty")
            return self._render_error_image(
                device_config,
                settings,
                "Failed to load quote"
            )

        # Parse quote data
        quote_text = quote_data.get("quote", "")
        author = quote_data.get("author", "")
        
        if not quote_text:
            logger.error("API returned empty quote")
            return self._render_error_image(
                device_config,
                settings,
                "No quote found"
            )

        # Get display settings
        show_author = settings.get("show_author", "true") == "true"
        max_lines = int(settings.get("max_lines", "4"))

        # Get device dimensions
        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]
            logger.debug(f"Vertical orientation detected, dimensions: {dimensions[0]}x{dimensions[1]}")

        # Prepare template parameters
        template_params = {
            "quote": quote_text,
            "author": author if (show_author and author) else "",
            "max_lines": max_lines,
            "show_author": show_author and bool(author),
            "plugin_settings": settings
        }

        logger.info(f"Rendering quote: {quote_text[:50]}...")
        image = self.render_image(
            dimensions,
            "famous_quotes.html",
            "famous_quotes.css",
            template_params
        )

        logger.info("=== Famous Quotes Plugin: Image generation complete ===")
        return image

    def _fetch_quote(self, api_key, category):
        """Fetch a quote from API Ninjas Quotes API v2"""
        try:
            headers = {"X-Api-Key": api_key}
            
            if category and category != "random":
                url = f"https://api.api-ninjas.com/v2/quotes?category={category}"
            else:
                url = "https://api.api-ninjas.com/v2/quotes"

            logger.debug(f"Fetching from URL: {url}")
            session = get_http_session()
            response = session.get(url, headers=headers, timeout=10)

            if response.status_code != 200:
                logger.error(f"API error (status {response.status_code}): {response.text}")
                return None

            data = response.json()
            
            # API returns an array of quotes, use the first one
            if isinstance(data, list) and len(data) > 0:
                return data[0]
            elif isinstance(data, dict):
                return data
            else:
                logger.error(f"Unexpected API response format: {data}")
                return None

        except Exception as e:
            logger.error(f"Error fetching quote: {str(e)}")
            return None

    def _render_error_image(self, device_config, settings, error_message):
        """Render error message"""
        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]

        template_params = {
            "quote": error_message,
            "author": "",
            "show_author": False,
            "plugin_settings": settings
        }

        return self.render_image(
            dimensions,
            "famous_quotes.html",
            "famous_quotes.css",
            template_params
        )
