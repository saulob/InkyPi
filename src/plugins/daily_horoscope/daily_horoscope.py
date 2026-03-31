from plugins.base_plugin.base_plugin import BasePlugin
from utils.http_client import get_http_session
from datetime import datetime
import logging
import os
import pytz

logger = logging.getLogger(__name__)

API_NINJAS_URL = "https://api.api-ninjas.com/v1/horoscope"

SUPPORTED_LANGUAGES = {
    "nl": "Dutch",
    "en": "English",
    "fr": "French",
    "de": "German",
    "id": "Indonesian",
    "it": "Italian",
    "pt": "Portuguese",
    "es": "Spanish",
}

ZODIAC_SIGNS = [
    "aries", "taurus", "gemini", "cancer", "leo", "virgo",
    "libra", "scorpio", "sagittarius", "capricorn", "aquarius", "pisces"
]

LABELS = {
    "en": {
        "title": "Daily Horoscope",
        "fallback": "No horoscope available today.",
    },
}

# Sign name translations keyed by language code then English sign name.
SIGN_NAMES = {
    "de": {
        "aries": "Widder", "taurus": "Stier", "gemini": "Zwillinge",
        "cancer": "Krebs", "leo": "Löwe", "virgo": "Jungfrau",
        "libra": "Waage", "scorpio": "Skorpion", "sagittarius": "Schütze",
        "capricorn": "Steinbock", "aquarius": "Wassermann", "pisces": "Fische",
    },
    "es": {
        "aries": "Aries", "taurus": "Tauro", "gemini": "Géminis",
        "cancer": "Cáncer", "leo": "Leo", "virgo": "Virgo",
        "libra": "Libra", "scorpio": "Escorpio", "sagittarius": "Sagitario",
        "capricorn": "Capricornio", "aquarius": "Acuario", "pisces": "Piscis",
    },
    "fr": {
        "aries": "Bélier", "taurus": "Taureau", "gemini": "Gémeaux",
        "cancer": "Cancer", "leo": "Lion", "virgo": "Vierge",
        "libra": "Balance", "scorpio": "Scorpion", "sagittarius": "Sagittaire",
        "capricorn": "Capricorne", "aquarius": "Verseau", "pisces": "Poissons",
    },
    "id": {
        "aries": "Aries", "taurus": "Taurus", "gemini": "Gemini",
        "cancer": "Cancer", "leo": "Leo", "virgo": "Virgo",
        "libra": "Libra", "scorpio": "Scorpio", "sagittarius": "Sagitarius",
        "capricorn": "Capricorn", "aquarius": "Aquarius", "pisces": "Pisces",
    },
    "it": {
        "aries": "Ariete", "taurus": "Toro", "gemini": "Gemelli",
        "cancer": "Cancro", "leo": "Leone", "virgo": "Vergine",
        "libra": "Bilancia", "scorpio": "Scorpione", "sagittarius": "Sagittario",
        "capricorn": "Capricorno", "aquarius": "Acquario", "pisces": "Pesci",
    },
    "nl": {
        "aries": "Ram", "taurus": "Stier", "gemini": "Tweelingen",
        "cancer": "Kreeft", "leo": "Leeuw", "virgo": "Maagd",
        "libra": "Weegschaal", "scorpio": "Schorpioen", "sagittarius": "Boogschutter",
        "capricorn": "Steenbok", "aquarius": "Waterman", "pisces": "Vissen",
    },
    "pt": {
        "aries": "Áries", "taurus": "Touro", "gemini": "Gêmeos",
        "cancer": "Câncer", "leo": "Leão", "virgo": "Virgem",
        "libra": "Libra", "scorpio": "Escorpião", "sagittarius": "Sagitário",
        "capricorn": "Capricórnio", "aquarius": "Aquário", "pisces": "Peixes",
    },
}

# Month names for date formatting, keyed by language code.
MONTH_NAMES = {
    "de": ["Januar", "Februar", "März", "April", "Mai", "Juni",
           "Juli", "August", "September", "Oktober", "November", "Dezember"],
    "es": ["enero", "febrero", "marzo", "abril", "mayo", "junio",
           "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"],
    "fr": ["janvier", "février", "mars", "avril", "mai", "juin",
           "juillet", "août", "septembre", "octobre", "novembre", "décembre"],
    "id": ["Januari", "Februari", "Maret", "April", "Mei", "Juni",
           "Juli", "Agustus", "September", "Oktober", "November", "Desember"],
    "it": ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
           "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"],
    "nl": ["januari", "februari", "maart", "april", "mei", "juni",
           "juli", "augustus", "september", "oktober", "november", "december"],
    "pt": ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
           "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"],
}


def _format_date(dt, language):
    """Format a date according to language conventions."""
    months = MONTH_NAMES.get(language)
    if months:
        month_name = months[dt.month - 1]
        # day month year for most languages
        if language == "en":
            return dt.strftime("%B %d, %Y")
        return f"{dt.day} de {month_name} de {dt.year}" if language in ("pt", "es") else f"{dt.day} {month_name} {dt.year}"
    # English default
    return dt.strftime("%B %d, %Y")


def _get_sign_display(sign, language):
    """Return the translated sign name, uppercased."""
    lang_signs = SIGN_NAMES.get(language)
    if lang_signs:
        return lang_signs.get(sign, sign).upper()
    return sign.upper()


def _translate_text(text, target_lang):
    """Translate text from English to target language using Argos Translate."""
    if not text or target_lang == "en":
        return text
    try:
        import argostranslate.package
        import argostranslate.translate

        installed = argostranslate.package.get_installed_packages()
        pkg_exists = any(
            p.from_code == "en" and p.to_code == target_lang
            for p in installed
        )

        if not pkg_exists:
            logger.info(f"Downloading Argos Translate package: en -> {target_lang}")
            argostranslate.package.update_package_index()
            available = argostranslate.package.get_available_packages()
            pkg = next(
                (p for p in available if p.from_code == "en" and p.to_code == target_lang),
                None,
            )
            if pkg is None:
                logger.warning(f"No Argos Translate package available for en -> {target_lang}")
                return text
            argostranslate.package.install_from_path(pkg.download())
            logger.info(f"Installed Argos Translate package: en -> {target_lang}")

        translated = argostranslate.translate.translate(text, "en", target_lang)
        return translated
    except Exception as e:
        logger.error(f"Translation failed (en -> {target_lang}): {e}")
        return text




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
        return template_params

    def _icon_path(self, sign):
        return self.get_plugin_dir(os.path.join("icons", f"{sign}.png"))

    def generate_image(self, settings, device_config):
        sign = settings.get("sign", "aries").lower()
        if sign not in ZODIAC_SIGNS:
            sign = "aries"

        language = str(settings.get("language", "en")).strip() or "en"

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

        # Translate only the horoscope text via Argos Translate
        if language != "en" and horoscope_text != labels["fallback"]:
            logger.info(f"Translating horoscope text to {SUPPORTED_LANGUAGES.get(language, language)}")
            horoscope_text = _translate_text(horoscope_text, language)

        # Date display: prefer API date, fallback to system
        if api_date:
            try:
                date_display = _format_date(datetime.strptime(api_date, "%Y-%m-%d"), language)
            except Exception:
                date_display = _format_date(today, language)
        else:
            date_display = _format_date(today, language)

        sign_display = _get_sign_display(sign, language)
        icon_path = self._icon_path(sign)

        # Do not pass internal flags to the template
        template_settings = dict(settings)
        template_settings.pop("_manual_update", None)

        template_params = {
            "title": labels["title"],
            "icon_path": icon_path,
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
