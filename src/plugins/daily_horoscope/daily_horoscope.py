from plugins.base_plugin.base_plugin import BasePlugin
from utils.http_client import get_http_session
import hashlib
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

# Remember last API key fingerprint so we can detect changes and invalidate cache
_last_key_fingerprint = None


def _cache_key(sign, date_str, key_fingerprint=None):
    base = f"{sign}:{date_str}"
    if key_fingerprint:
        return f"{base}:{key_fingerprint}"
    return base


def clear_horoscope_cache():
    """Clear the entire in-memory horoscope cache."""
    global _horoscope_cache
    _horoscope_cache.clear()


def set_api_key_fingerprint(api_key):
    """Compute the fingerprint for `api_key`, and if it changed since last seen,
    clear the cache to avoid reusing entries tied to a different key.

    Returns the current fingerprint.
    """
    global _last_key_fingerprint
    if not api_key:
        fingerprint = None
    else:
        fingerprint = hashlib.sha256(api_key.encode()).hexdigest()[:8]

    # If the fingerprint differs from the last seen value, clear the cache.
    # This covers transitions from None->value (adding a key) and value->None
    # (removing a key) so cached entries aren't mistakenly reused.
    if fingerprint != _last_key_fingerprint:
        logger.info("API key fingerprint changed (%s -> %s). Clearing horoscope cache.", _last_key_fingerprint, fingerprint)
        clear_horoscope_cache()

    _last_key_fingerprint = fingerprint
    return fingerprint


def fetch_horoscope(sign, date_str, api_key, force_fetch=False):
    """Fetch horoscope from API Ninjas with daily cache.

    - Uses an in-memory cache keyed by sign, date, and API key fingerprint.
    - If `force_fetch` is True the cache is bypassed and a real request is performed.
    - Raises `RuntimeError` on authorization errors or when forced fetch fails.
    """
    if not api_key:
        logger.warning("API Ninjas key not configured, cannot fetch horoscope.")
        if force_fetch:
            raise RuntimeError("API Ninjas API Key not configured.")
        return None

    # fingerprint the API key so cached entries are scoped per-key
    key_fingerprint = hashlib.sha256(api_key.encode()).hexdigest()[:8]
    key = _cache_key(sign, date_str, key_fingerprint)

    # Only allow cache for automatic refresh (force_fetch=False)
    if not force_fetch and key in _horoscope_cache:
        logger.info("Returning cached horoscope for %s on %s (fingerprint=%s)", sign, date_str, key_fingerprint)
        return _horoscope_cache[key]

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

        # Only cache if we have something useful and only after a successful API response
        if data.get("horoscope"):
            _horoscope_cache[key] = data

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
        return template_params

    def generate_image(self, settings, device_config):
        sign = settings.get("sign", "aries").lower()
        if sign not in ZODIAC_SIGNS:
            sign = "aries"

        language = settings.get("language", "en")
        if language not in LABELS:
            language = "en"
        labels = LABELS[language]

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


        # Sempre atualiza a impressão digital da chave e limpa o cache se necessário
        set_api_key_fingerprint(api_key)

        # Se a chave não estiver configurada, lança erro
        if not api_key:
            logger.error("API Ninjas API Key not configured")
            raise RuntimeError("API Ninjas API Key not configured.")

        try:
            data = fetch_horoscope(sign, date_str, api_key, force_fetch=False)
        except RuntimeError:
            # Propaga erros conhecidos para o sistema de refresh exibir
            raise

        # Se não houver dados, apenas mostra mensagem padrão (sem erro forçado)

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

        # Do not pass internal flags to the template
        template_settings = dict(settings)
        template_settings.pop("_manual_update", None)

        template_params = {
            "title": labels["title"],
            "symbol": symbol,
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
