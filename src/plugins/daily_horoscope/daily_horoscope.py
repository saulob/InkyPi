from plugins.base_plugin.base_plugin import BasePlugin
from utils.http_client import get_http_session
from datetime import datetime
import logging
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
    "pt_br": {
        "title": "Hor\u00f3scopo do Dia",
        "love": "Amor",
        "work": "Trabalho",
        "money": "Dinheiro",
        "mood": "Humor",
        "compatibility": "Compatibilidade",
        "lucky_number": "N\u00famero da Sorte",
        "fallback": "Hor\u00f3scopo indispon\u00edvel hoje.",
    },
}

# In-memory cache: { "sign:YYYY-MM-DD": {...} }
_horoscope_cache = {}


def _cache_key(sign, date_str):
    return f"{sign}:{date_str}"


def fetch_horoscope(sign, date_str, api_key):
    """Fetch horoscope from API Ninjas with daily cache."""
    key = _cache_key(sign, date_str)
    if key in _horoscope_cache:
        logger.info("Returning cached horoscope for %s on %s", sign, date_str)
        return _horoscope_cache[key]

    if not api_key:
        logger.warning("API Ninjas key not configured, cannot fetch horoscope.")
        return None

    session = get_http_session()
    try:
        # API expects parameter name `zodiac` with capitalized sign (e.g. Aries)
        response = session.get(
            API_NINJAS_URL,
            params={"zodiac": sign.capitalize()},
            headers={"X-Api-Key": api_key},
            timeout=15,
        )
        if not response.ok:
            logger.error(
                "API Ninjas returned status %s: %s", response.status_code, response.text
            )
            return None
        data = response.json()

        # Normalize response: some endpoints may return a list
        if isinstance(data, list) and len(data) > 0:
            data = data[0]

        if not isinstance(data, dict):
            logger.error("Unexpected horoscope response format: %s", type(data))
            return None

        # Only cache if we have something useful
        if data.get("horoscope"):
            _horoscope_cache[key] = data

        return data
    except Exception as e:
        logger.error("Failed to fetch horoscope: %s", e)
        return None


def truncate_text(text, max_chars=180):
    """Truncate text to max_chars, ending at a word boundary with ellipsis."""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars].rsplit(" ", 1)[0]
    return truncated.rstrip(".,;:!? ") + "..."


def _hex_to_rgb(hex_color: str):
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 3:
        hex_color = ''.join([c*2 for c in hex_color])
    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return (r, g, b)
    except Exception:
        return (0, 0, 0)


def _rgb_to_hex(rgb):
    return '#{0:02x}{1:02x}{2:02x}'.format(*[max(0, min(255, int(c))) for c in rgb])


def _normalize_primary_color(hex_color: str):
    """If the chosen color is a gray (R==G==B), reduce its brightness toward black.
    Otherwise return the color unchanged. Returns hex string.
    """
    if not hex_color:
        return "#000000"
    r, g, b = _hex_to_rgb(hex_color)
    if r == g == b:
        # reduce brightness to make 'gray' behave like a reduced black for text
        factor = 0.35
        r2 = int(r * factor)
        g2 = int(g * factor)
        b2 = int(b * factor)
        return _rgb_to_hex((r2, g2, b2))
    return hex_color


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
        return template_params

    def generate_image(self, settings, device_config):
        sign = settings.get("sign", "aries").lower()
        if sign not in ZODIAC_SIGNS:
            sign = "aries"

        language = settings.get("language", "en")
        if language not in LABELS:
            language = "en"
        labels = LABELS[language]

        # Primary: text color (default black). If user chose a gray, reduce it toward black.
        primary_color_raw = settings.get("primaryColor", "#000000")
        primary_color = _normalize_primary_color(primary_color_raw)

        # Secondary: background color (default white)
        secondary_color = settings.get("secondaryColor", "#FFFFFF")

        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]

        api_key = device_config.load_env_key("API_NINJAS")

        timezone_name = device_config.get_config("timezone", default="America/New_York")
        tz = pytz.timezone(timezone_name)
        today = datetime.now(tz)
        date_str = today.strftime("%Y-%m-%d")

        data = fetch_horoscope(sign, date_str, api_key)

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

        # Truncate and wrap (3-5 lines, ~300 chars max)
        max_chars = 300
        if len(horoscope_text) > max_chars:
            horoscope_text = truncate_text(horoscope_text, max_chars)

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

        template_params = {
            "title": labels["title"],
            "symbol": symbol,
            "sign_display": sign_display,
            "horoscope_text": horoscope_text,
            "primary_color": primary_color,
            "secondary_color": secondary_color,
            "date_display": date_display,
            "plugin_settings": settings,
        }

        image = self.render_image(
            dimensions, "daily_horoscope.html", "daily_horoscope.css", template_params
        )

        if not image:
            raise RuntimeError("Failed to render horoscope image.")
        return image
