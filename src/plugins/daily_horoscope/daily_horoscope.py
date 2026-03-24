from plugins.base_plugin.base_plugin import BasePlugin
from utils.http_client import get_http_session
from datetime import datetime
import logging
import pytz

logger = logging.getLogger(__name__)

AZTRO_API_URL = "https://aztro.sameerkumar.website/"

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


def fetch_horoscope(sign, date_str):
    """Fetch horoscope from Aztro API with daily cache."""
    key = _cache_key(sign, date_str)
    if key in _horoscope_cache:
        logger.info("Returning cached horoscope for %s on %s", sign, date_str)
        return _horoscope_cache[key]

    session = get_http_session()
    try:
        response = session.post(AZTRO_API_URL, params={"sign": sign, "day": "today"}, timeout=15)
        if not response.ok:
            logger.error("Aztro API returned status %s", response.status_code)
            return None
        data = response.json()
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


class DailyHoroscope(BasePlugin):
    def generate_settings_template(self):
        template_params = super().generate_settings_template()
        template_params["style_settings"] = True
        template_params["zodiac_signs"] = ZODIAC_SIGNS
        return template_params

    def generate_image(self, settings, device_config):
        sign = settings.get("sign", "aries").lower()
        if sign not in ZODIAC_SIGNS:
            sign = "aries"

        language = settings.get("language", "en")
        if language not in LABELS:
            language = "en"
        labels = LABELS[language]

        primary_color = settings.get("primaryColor", "#000000")
        secondary_color = settings.get("secondaryColor", "#666666")

        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]

        timezone_name = device_config.get_config("timezone", default="America/New_York")
        tz = pytz.timezone(timezone_name)
        today = datetime.now(tz)
        date_str = today.strftime("%Y-%m-%d")

        data = fetch_horoscope(sign, date_str)

        horoscope_text = labels["fallback"]
        mood = ""
        compatibility = ""
        lucky_number = ""

        if data:
            description = data.get("description", "")
            horoscope_text = truncate_text(description) if description else labels["fallback"]
            mood = data.get("mood", "")
            compatibility = data.get("compatibility", "")
            lucky_number = str(data.get("lucky_number", ""))

        symbol = ZODIAC_SYMBOLS.get(sign, "")
        sign_display = sign.capitalize()

        template_params = {
            "title": labels["title"],
            "symbol": symbol,
            "sign_display": sign_display,
            "horoscope_text": horoscope_text,
            "mood": mood,
            "mood_label": labels["mood"],
            "compatibility": compatibility,
            "compatibility_label": labels["compatibility"],
            "lucky_number": lucky_number,
            "lucky_number_label": labels["lucky_number"],
            "love_label": labels["love"],
            "work_label": labels["work"],
            "money_label": labels["money"],
            "primary_color": primary_color,
            "secondary_color": secondary_color,
            "date_display": today.strftime("%B %d, %Y"),
            "plugin_settings": settings,
        }

        image = self.render_image(
            dimensions, "daily_horoscope.html", "daily_horoscope.css", template_params
        )

        if not image:
            raise RuntimeError("Failed to render horoscope image.")
        return image
