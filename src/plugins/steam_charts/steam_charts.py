from plugins.base_plugin.base_plugin import BasePlugin
from utils.http_client import get_http_session
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

STEAM_FEATURED_URL = "https://store.steampowered.com/api/featuredcategories/"

CHART_MODES = {
    "new_trending": {
        "label": "New and Trending",
        "api_key": "new_releases",
    },
    "top_sellers": {
        "label": "Top Sellers",
        "api_key": "top_sellers",
    },
    "most_played": {
        "label": "Most Played",
        "api_key": "most_played",
    },
}

MAX_ITEMS = 5


class SteamCharts(BasePlugin):
    def generate_settings_template(self):
        template_params = super().generate_settings_template()
        template_params["chart_modes"] = CHART_MODES
        template_params["style_settings"] = True
        return template_params

    def generate_image(self, settings, device_config):
        mode = settings.get("mode", "new_trending")
        items_count = min(int(settings.get("itemsCount", MAX_ITEMS)), MAX_ITEMS)
        show_images = settings.get("showImages", "true") == "true"
        show_movement = settings.get("showMovement", "true") == "true"
        show_updated = settings.get("showUpdated", "true") == "true"

        mode_config = CHART_MODES.get(mode)
        if not mode_config:
            raise RuntimeError(f"Unknown chart mode: {mode}")

        games = self._fetch_games(mode_config["api_key"], items_count)

        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]

        updated_time = datetime.now().strftime("%H:%M")

        template_params = {
            "title": "STEAM CHARTS",
            "subtitle": mode_config["label"],
            "games": games,
            "show_images": show_images,
            "show_movement": show_movement,
            "show_updated": show_updated,
            "updated_time": updated_time,
            "plugin_settings": settings,
        }

        return self.render_image(
            dimensions, "steam_charts.html", "steam_charts.css", template_params
        )

    def _fetch_games(self, api_category, count):
        """Fetch game list from Steam featured categories API."""
        try:
            session = get_http_session()
            response = session.get(STEAM_FEATURED_URL, timeout=15)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.error(f"Failed to fetch Steam data: {e}")
            raise RuntimeError(
                "Unable to fetch Steam data. Please try again later."
            )

        category_data = data.get(api_category)
        if not category_data:
            raise RuntimeError(
                f"Steam category '{api_category}' not found in response."
            )

        items = category_data.get("items", [])
        if not items:
            raise RuntimeError("No games found for this category.")

        games = []
        for i, item in enumerate(items[:count]):
            game = {
                "rank": i + 1,
                "name": item.get("name", "Unknown"),
                "image": item.get("small_capsule_image") or item.get("header_image", ""),
                "movement": self._detect_movement(item),
            }
            games.append(game)

        return games

    @staticmethod
    def _detect_movement(item):
        """Detect movement indicator from available item data."""
        if item.get("discount_expiration"):
            return None
        if item.get("discounted", False):
            return None
        return None
