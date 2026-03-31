from plugins.base_plugin.base_plugin import BasePlugin
from utils.http_client import get_http_session
from utils.image_utils import take_screenshot_html
from utils.app_utils import get_fonts
from datetime import datetime
import logging
import os
import pytz

logger = logging.getLogger(__name__)

API_NINJAS_URL = "https://api.api-ninjas.com/v1/horoscope"

ZODIAC_SIGNS = [
    "aries", "taurus", "gemini", "cancer", "leo", "virgo",
    "libra", "scorpio", "sagittarius", "capricorn", "aquarius", "pisces"
]

ZODIAC_SYMBOLS = {
    "aries": "\u2648",
    "taurus": "\u2649",
    "gemini": "\u264A",
    "cancer": "\u264B",
    "leo": "\u264C",
    "virgo": "\u264D",
    "libra": "\u264E",
    "scorpio": "\u264F",
    "sagittarius": "\u2650",
    "capricorn": "\u2651",
    "aquarius": "\u2652",
    "pisces": "\u2653",
}

LABELS = {
    "en": {
        "title": "Daily Horoscope",
        "love": "Love",
        "work": "Work",
        "money": "Money",
        "mood": "Mood",
        "compatibility": "Compatibility",
        "lucky_number": "Lucky Number",
        "fallback": "No horoscope available today.",
    },
}




def fetch_horoscope(sign, date_str, api_key, force_fetch=False):
    """Fetch horoscope from API Ninjas with daily cache.
    - Performs a live request to API Ninjas and returns the result.
    - Raises `RuntimeError` on authorization errors or when the request fails.
    """
    if not api_key:
        logger.warning("API Ninjas key not configured, cannot fetch horoscope.")
        raise RuntimeError("API Ninjas API Key not configured.")

    session = get_http_session()
    try:
        # API expects parameter name `zodiac` with capitalized sign (e.g. Aries)
        response = session.get(
            API_NINJAS_URL,
            params={"zodiac": sign.capitalize()},
            headers={"X-Api-Key": api_key},
            timeout=15,
        )

        # Authorization errors should be surfaced as configuration/auth errors
        if response.status_code in (401, 403):
            logger.error("API Ninjas authorization error (status %s): %s", response.status_code, response.text)
            # Always treat as error, never use cache
            raise RuntimeError("API Ninjas API Key invalid or unauthorized.")

        if not response.ok:
            logger.error("API Ninjas returned status %s: %s", response.status_code, response.text)
            if force_fetch:
                raise RuntimeError("Failed to retrieve horoscope from API Ninjas.")
            return None

        data = response.json()

        # Normalize response: some endpoints may return a list
        if isinstance(data, list) and len(data) > 0:
            data = data[0]

        if not isinstance(data, dict):
            logger.error("Unexpected horoscope response format: %s", type(data))
            if force_fetch:
                raise RuntimeError("Unexpected horoscope response format.")
            return None

        return data
    except RuntimeError:
        # re-raise known runtime errors
        raise
    except Exception as e:
        logger.error("Failed to fetch horoscope: %s", e)
        if force_fetch:
            raise RuntimeError("Failed to retrieve horoscope from API Ninjas.")
        return None


def truncate_text(text, max_chars=180):
    """Truncate text to max_chars, ending at a word boundary with ellipsis."""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars].rsplit(" ", 1)[0]
    return truncated.rstrip(".,;:!? ") + "..."




class DailyHoroscope(BasePlugin):
    def generate_settings_template(self):
        template_params = super().generate_settings_template()
        template_params["api_key"] = {
            "required": True,
            "service": "API Ninjas",
            "expected_key": "API_NINJAS",
        }
        template_params["style_settings"] = True
        # Provide alphabetically sorted zodiac signs (values remain lowercase)
        template_params["zodiac_signs"] = sorted(ZODIAC_SIGNS)
        template_params["icons_generated"] = self._icons_exist()
        return template_params

    def _icons_dir(self):
        return self.get_plugin_dir("icons")

    def _icon_path(self, sign):
        return os.path.join(self._icons_dir(), f"{sign}.png")

    def _icons_exist(self):
        """Check if all 12 zodiac icon PNGs exist."""
        icons_dir = self._icons_dir()
        if not os.path.isdir(icons_dir):
            return False
        return all(
            os.path.isfile(os.path.join(icons_dir, f"{sign}.png"))
            for sign in ZODIAC_SIGNS
        )

    def generate_zodiac_icons(self):
        """Render all 12 zodiac symbols via browser screenshot and save as PNGs.

        Uses the same Chromium rendering pipeline as plugin image generation
        to capture the styled Unicode symbol exactly as the browser renders it.
        """
        icon_size = 256
        icons_dir = self._icons_dir()
        os.makedirs(icons_dir, exist_ok=True)

        font_faces = get_fonts()
        font_face_css = ""
        for f in font_faces:
            font_face_css += (
                f'@font-face {{ font-family: "{f["font_family"]}"; '
                f'font-weight: {f["font_weight"]}; '
                f'font-style: {f["font_style"]}; '
                f'src: url({f["url"]}) format("truetype"); }}\n'
            )

        generated = []
        for sign in ZODIAC_SIGNS:
            symbol = ZODIAC_SYMBOLS.get(sign, "")
            html = f"""<html><head><style>
                {font_face_css}
                * {{ margin: 0; padding: 0; }}
                body {{
                    width: {icon_size}px;
                    height: {icon_size}px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    background: transparent;
                }}
                .symbol {{
                    font-family: "Jost", sans-serif;
                    font-size: {int(icon_size * 0.75)}px;
                    line-height: 1;
                    text-align: center;
                }}
            </style></head><body><span class="symbol">{symbol}</span></body></html>"""

            img = take_screenshot_html(html, (icon_size, icon_size))
            if img:
                img.save(self._icon_path(sign), "PNG")
                generated.append(sign)
                logger.info("Generated zodiac icon: %s", sign)
            else:
                logger.error("Failed to generate zodiac icon: %s", sign)

        return generated

    def generate_image(self, settings, device_config):
        sign = settings.get("sign", "aries").lower()
        if sign not in ZODIAC_SIGNS:
            sign = "aries"

        # Always use English labels
        labels = LABELS["en"]

        # colors: use global styles; plugin no longer reads per-instance colors
        primary_color = None
        secondary_color = None

        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]

        api_key = device_config.load_env_key("API_NINJAS")

        timezone_name = device_config.get_config("timezone", default="America/New_York")
        tz = pytz.timezone(timezone_name)
        today = datetime.now(tz)
        date_str = today.strftime("%Y-%m-%d")


        # If the API key is not configured, raise an error
        if not api_key:
            logger.error("API Ninjas API Key not configured")
            raise RuntimeError("API Ninjas API Key not configured.")

        try:
            data = fetch_horoscope(sign, date_str, api_key, force_fetch=False)
        except RuntimeError:
            # Re-raise known runtime errors so the refresh system can display them
            raise

        # If no data is available, use the fallback message (do not force an error)

        # --- Parse API Ninjas v1/2 response ---
        api_date = None
        horoscope_text = labels["fallback"]
        if data:
            # Log for debugging if missing/empty
            logger.info(f"Horoscope API response: {data}")
            description = data.get("horoscope")
            if description and isinstance(description, str) and description.strip():
                horoscope_text = description.strip()
                api_date = data.get("date")
            else:
                logger.warning(f"No valid 'horoscope' in API response: {data}")

        # Do not truncate or limit lines before rendering. Let CSS handle overflow/ellipsis if needed.

        # Date display: prefer API date, fallback to system
        if api_date:
            try:
                date_display = datetime.strptime(api_date, "%Y-%m-%d").strftime("%B %d, %Y")
            except Exception:
                date_display = today.strftime("%B %d, %Y")
        else:
            date_display = today.strftime("%B %d, %Y")

        symbol = ZODIAC_SYMBOLS.get(sign, "")
        sign_display = sign.upper()

        # Prefer pre-rendered icon PNG; fall back to Unicode symbol
        icon_path = self._icon_path(sign)
        use_icon = os.path.isfile(icon_path)

        # Do not pass internal flags to the template
        template_settings = dict(settings)
        template_settings.pop("_manual_update", None)

        template_params = {
            "title": labels["title"],
            "symbol": symbol,
            "icon_path": icon_path if use_icon else "",
            "sign_display": sign_display,
            "horoscope_text": horoscope_text,
            "date_display": date_display,
            "plugin_settings": template_settings,
            "orientation": device_config.get_config("orientation", "horizontal"),
        }

        image = self.render_image(
            dimensions, "daily_horoscope.html", "daily_horoscope.css", template_params
        )

        if not image:
            raise RuntimeError("Failed to render horoscope image.")
        return image
