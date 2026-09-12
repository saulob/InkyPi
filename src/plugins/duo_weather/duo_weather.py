import logging
import os
import re
import unicodedata

import pytz
import requests
import datetime

from plugins.weather.weather import UNITS, Weather

logger = logging.getLogger(__name__)

REVERSE_GEOCODE_URL = (
    "https://nominatim.openstreetmap.org/reverse"
    "?lat={lat}&lon={long}&format=jsonv2&addressdetails=1&zoom=10"
)

# Simple in-memory cache for reverse-geocoded titles to avoid hitting Nominatim
# on every refresh. Keys are rounded coordinate pairs to tolerate tiny changes.
REVERSE_GEOCODE_CACHE = {}
# TTL for successful reverse geocode results (seconds)
REVERSE_GEOCODE_SUCCESS_TTL = 7 * 24 * 60 * 60  # 7 days
# TTL for failed attempts (seconds) to avoid tight retry loops
REVERSE_GEOCODE_FAIL_TTL = 60 * 60  # 1 hour
REVERSE_GEOCODE_ROUND_DECIMALS = 4

HOURLY_POINT_COUNT = 6
HOURLY_STEP_HOURS = 2

QUICK_LOCATION_LABELS = {
    "52.3676,4.9041": "Amsterdam",
    "52.5200,13.4050": "Berlin",
    "-34.6037,-58.3816": "Buenos Aires",
    "-6.2088,106.8456": "Jakarta",
    "51.5074,-0.1278": "London",
    "40.4168,-3.7038": "Madrid",
    "40.7128,-74.0060": "New York",
    "48.8566,2.3522": "Paris",
    "-22.9068,-43.1729": "Rio de Janeiro",
    "41.9028,12.4964": "Rome",
    "-23.5505,-46.6333": "São Paulo",
    "35.6762,139.6503": "Tokyo",
}

QUICK_LOCATION_COORDS = {
    city: tuple(map(float, coords.split(",")))
    for coords, city in QUICK_LOCATION_LABELS.items()
}

LANGUAGE_LABELS = {
    "de": {
        "now": "JETZT",
        "high": "H",
        "low": "T",
        "days": ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"],
        "conditions": {
            "clear": "Klar",
            "mostly_sunny": "Meist sonnig",
            "mostly_clear": "Meist klar",
            "partly_cloudy": "Teilweise bewölkt",
            "cloudy": "Bewölkt",
            "overcast": "Bedeckt",
            "fog": "Nebel",
            "icy_fog": "Eisnebel",
            "drizzle": "Nieselregen",
            "rain": "Regen",
            "heavy_rain": "Starker Regen",
            "freezing_rain": "Gefrierender Regen",
            "snow": "Schnee",
            "thunderstorm": "Gewitter",
        },
    },
    "en": {
        "now": "NOW",
        "high": "H",
        "low": "L",
        "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "conditions": {
            "clear": "Clear",
            "mostly_sunny": "Mostly Sunny",
            "mostly_clear": "Mostly Clear",
            "partly_cloudy": "Partly Cloudy",
            "cloudy": "Cloudy",
            "overcast": "Overcast",
            "fog": "Fog",
            "icy_fog": "Icy Fog",
            "drizzle": "Drizzle",
            "rain": "Rain",
            "heavy_rain": "Heavy Rain",
            "freezing_rain": "Freezing Rain",
            "snow": "Snow",
            "thunderstorm": "Thunderstorm",
        },
    },
    "es": {
        "now": "AHORA",
        "high": "M",
        "low": "m",
        "days": ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"],
        "conditions": {
            "clear": "Despejado",
            "mostly_sunny": "Mayormente soleado",
            "mostly_clear": "Mayormente despejado",
            "partly_cloudy": "Parcialmente nublado",
            "cloudy": "Nublado",
            "overcast": "Cubierto",
            "fog": "Niebla",
            "icy_fog": "Niebla helada",
            "drizzle": "Llovizna",
            "rain": "Lluvia",
            "heavy_rain": "Lluvia intensa",
            "freezing_rain": "Lluvia helada",
            "snow": "Nieve",
            "thunderstorm": "Tormenta",
        },
    },
    "fr": {
        "now": "MAINT",
        "high": "M",
        "low": "m",
        "days": ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"],
        "conditions": {
            "clear": "Clair",
            "mostly_sunny": "Plutôt ensoleillé",
            "mostly_clear": "Plutôt dégagé",
            "partly_cloudy": "Partiellement nuageux",
            "cloudy": "Nuageux",
            "overcast": "Couvert",
            "fog": "Brouillard",
            "icy_fog": "Brouillard givrant",
            "drizzle": "Bruine",
            "rain": "Pluie",
            "heavy_rain": "Forte pluie",
            "freezing_rain": "Pluie verglaçante",
            "snow": "Neige",
            "thunderstorm": "Orage",
        },
    },
    "id": {
        "now": "SEK",
        "high": "T",
        "low": "R",
        "days": ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"],
        "conditions": {
            "clear": "Cerah",
            "mostly_sunny": "Cerah berawan",
            "mostly_clear": "Cerah",
            "partly_cloudy": "Berawan sebagian",
            "cloudy": "Berawan",
            "overcast": "Mendung",
            "fog": "Kabut",
            "icy_fog": "Kabut es",
            "drizzle": "Gerimis",
            "rain": "Hujan",
            "heavy_rain": "Hujan lebat",
            "freezing_rain": "Hujan beku",
            "snow": "Salju",
            "thunderstorm": "Badai petir",
        },
    },
    "it": {
        "now": "ORA",
        "high": "M",
        "low": "m",
        "days": ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"],
        "conditions": {
            "clear": "Sereno",
            "mostly_sunny": "Prevalentemente soleggiato",
            "mostly_clear": "Prevalentemente sereno",
            "partly_cloudy": "Parzialmente nuvoloso",
            "cloudy": "Nuvoloso",
            "overcast": "Coperto",
            "fog": "Nebbia",
            "icy_fog": "Nebbia gelata",
            "drizzle": "Pioggerella",
            "rain": "Pioggia",
            "heavy_rain": "Pioggia intensa",
            "freezing_rain": "Pioggia gelata",
            "snow": "Neve",
            "thunderstorm": "Temporale",
        },
    },
    "nl": {
        "now": "NU",
        "high": "H",
        "low": "L",
        "days": ["Ma", "Di", "Wo", "Do", "Vr", "Za", "Zo"],
        "conditions": {
            "clear": "Helder",
            "mostly_sunny": "Overwegend zonnig",
            "mostly_clear": "Overwegend helder",
            "partly_cloudy": "Gedeeltelijk bewolkt",
            "cloudy": "Bewolkt",
            "overcast": "Zwaar bewolkt",
            "fog": "Mist",
            "icy_fog": "IJsmist",
            "drizzle": "Motregen",
            "rain": "Regen",
            "heavy_rain": "Zware regen",
            "freezing_rain": "IJzel",
            "snow": "Sneeuw",
            "thunderstorm": "Onweer",
        },
    },
    "pt": {
        "now": "AGORA",
        "high": "M",
        "low": "m",
        "days": ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"],
        "conditions": {
            "clear": "Limpo",
            "mostly_sunny": "Predominantemente ensolarado",
            "mostly_clear": "Predominantemente limpo",
            "partly_cloudy": "Parcialmente nublado",
            "cloudy": "Nublado",
            "overcast": "Encoberto",
            "fog": "Neblina",
            "icy_fog": "Névoa gelada",
            "drizzle": "Garoa",
            "rain": "Chuva",
            "heavy_rain": "Chuva forte",
            "freezing_rain": "Chuva congelante",
            "snow": "Neve",
            "thunderstorm": "Tempestade",
        },
    },
}

# month names for a handful of supported languages; keep capitalized first letter
MONTH_NAMES = {
    "en": [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ],
    "pt": [
        "janeiro",
        "fevereiro",
        "março",
        "abril",
        "maio",
        "junho",
        "julho",
        "agosto",
        "setembro",
        "outubro",
        "novembro",
        "dezembro",
    ],
    "es": [
        "enero",
        "febrero",
        "marzo",
        "abril",
        "mayo",
        "junio",
        "julio",
        "agosto",
        "septiembre",
        "octubre",
        "noviembre",
        "diciembre",
    ],
    "fr": [
        "janvier",
        "février",
        "mars",
        "avril",
        "mai",
        "juin",
        "juillet",
        "août",
        "septembre",
        "octobre",
        "novembre",
        "décembre",
    ],
    "de": [
        "Januar",
        "Februar",
        "März",
        "April",
        "Mai",
        "Juni",
        "Juli",
        "August",
        "September",
        "Oktober",
        "November",
        "Dezember",
    ],
    "it": [
        "gennaio",
        "febbraio",
        "marzo",
        "aprile",
        "maggio",
        "giugno",
        "luglio",
        "agosto",
        "settembre",
        "ottobre",
        "novembre",
        "dicembre",
    ],
    "nl": [
        "januari",
        "februari",
        "maart",
        "april",
        "mei",
        "juni",
        "juli",
        "augustus",
        "september",
        "oktober",
        "november",
        "december",
    ],
    "id": [
        "Januari",
        "Februari",
        "Maret",
        "April",
        "Mei",
        "Juni",
        "Juli",
        "Agustus",
        "September",
        "Oktober",
        "November",
        "Desember",
    ],
}

ICON_CONDITION_KEYS = {
    "01d": "clear",
    "01n": "clear",
    "022d": "mostly_sunny",
    "022n": "mostly_clear",
    "02d": "partly_cloudy",
    "02n": "partly_cloudy",
    "03d": "cloudy",
    "03n": "cloudy",
    "04d": "overcast",
    "04n": "overcast",
    "09d": "heavy_rain",
    "09n": "heavy_rain",
    "10d": "rain",
    "10n": "rain",
    "11d": "thunderstorm",
    "11n": "thunderstorm",
    "13d": "snow",
    "13n": "snow",
    "48d": "icy_fog",
    "48n": "icy_fog",
    "50d": "fog",
    "50n": "fog",
    "51d": "drizzle",
    "51n": "drizzle",
    "53d": "rain",
    "53n": "rain",
    "56d": "freezing_rain",
    "56n": "freezing_rain",
    "57d": "freezing_rain",
    "57n": "freezing_rain",
    "71d": "snow",
    "71n": "snow",
    "73d": "snow",
    "73n": "snow",
    "77d": "snow",
    "77n": "snow",
}

SKY_BY_CONDITION = {
    "clear": "clear",
    "mostly_sunny": "clear",
    "mostly_clear": "clear",
    "partly_cloudy": "partly-cloudy",
    "cloudy": "cloudy",
    "overcast": "cloudy",
    "fog": "fog",
    "icy_fog": "fog",
    "drizzle": "rain",
    "rain": "rain",
    "heavy_rain": "rain",
    "freezing_rain": "rain",
    "snow": "snow",
    "thunderstorm": "storm",
}


def format_localized_date(language, dt):
    """Return a short localized date string for the given language and datetime.

    Examples:
      en -> "March 25, 2026"
      pt -> "25 de março de 2026"
      fr/de/it/nl/es/id -> "25 mars 2026"
    """
    lang = (language or "").lower()
    # Support full locale codes like en-US or de-DE by normalizing to the short prefix
    short = lang.split("-")[0].split("_")[0]
    months = MONTH_NAMES.get(short, MONTH_NAMES.get("en"))
    raw_month = months[dt.month - 1]

    day = dt.day
    year = dt.year

    # Capitalization rules
    # - English: capitalize month (e.g., March)
    # - French: lowercase month (e.g., mars)
    # - Other languages: use the form provided in MONTH_NAMES
    if short == "en":
        month = raw_month[0].upper() + raw_month[1:]
    elif short == "fr":
        month = raw_month.lower()
    else:
        month = raw_month

    # Formatting rules per language
    if short == "en":
        # Month Day, Year -> March 25, 2026
        return f"{month} {day}, {year}"

    if short in ("fr", "de", "it", "nl", "es", "id"):
        # Day Month Year -> 25 mars 2026 (no commas/connectors)
        return f"{day} {month} {year}"

    if short == "pt":
        # Portuguese: Day de month de Year -> 25 de março de 2026
        return f"{day} de {month} de {year}"

    # Fallback: use English-style month-first formatting
    return f"{month} {day}, {year}"


def get_language_labels(language):
    lang = (language or "").lower()
    # exact key
    if lang in LANGUAGE_LABELS:
        return LANGUAGE_LABELS[lang]
    # try prefix like en-US -> en
    short = lang.split("-")[0].split("_")[0]
    if short in LANGUAGE_LABELS:
        return LANGUAGE_LABELS[short]
    # fallback to English
    return LANGUAGE_LABELS["en"]


def is_valid_title(value):
    if value is None:
        return False

    title = str(value).strip()
    if len(title) < 2:
        return False

    # Require at least one letter/number to avoid titles like "," or "'".
    return bool(re.search(r"\w", title, flags=re.UNICODE))


def is_supported_title(value):
    if not is_valid_title(value):
        return False

    title = str(value).strip()
    has_letter = False

    for char in title:
        if not char.isalpha():
            continue

        has_letter = True
        if "LATIN" not in unicodedata.name(char, ""):
            return False

    return has_letter


class DuoWeather(Weather):
    def generate_settings_template(self):
        template_params = super().generate_settings_template()
        template_params['api_key'] = {
            "required": True,
            "service": "OpenWeatherMap",
            "expected_key": "OPEN_WEATHER_MAP_SECRET"
        }
        return template_params

    def generate_image(self, settings, device_config):
        lat_value = settings.get("latitude")
        long_value = settings.get("longitude")
        if lat_value in (None, "") or long_value in (None, ""):
            raise RuntimeError("Latitude and Longitude are required.")

        # Validate and parse numeric coordinates with clear error messages.
        try:
            lat = float(str(lat_value).strip())
            long = float(str(long_value).strip())
        except (ValueError, TypeError):
            raise RuntimeError("Latitude and Longitude must be valid numeric values.")

        # Range checks: latitude [-90, 90], longitude [-180, 180]
        if not (-90.0 <= lat <= 90.0):
            raise RuntimeError("Latitude must be between -90 and 90.")
        if not (-180.0 <= long <= 180.0):
            raise RuntimeError("Longitude must be between -180 and 180.")

        units = settings.get("units")
        if units not in UNITS:
            raise RuntimeError("Units are required.")

        language = str(settings.get("language", "en")).strip() or "en"
        weather_provider = settings.get("weatherProvider", "OpenMeteo")
        timezone_name = device_config.get_config("timezone", default="America/New_York")
        time_format = device_config.get_config("time_format", default="12h")
        local_tz = pytz.timezone(timezone_name)

        try:
            template_params, provider_tz, api_key = self._get_template_params(
                weather_provider,
                settings,
                units,
                lat,
                long,
                local_tz,
                time_format,
                device_config,
            )
        except Exception as exc:
            logger.error("%s request failed: %s", weather_provider, exc)
            raise RuntimeError(f"{weather_provider} request failure, please check logs.") from exc

        title = self._resolve_title_with_fallback(settings, weather_provider, lat, long, api_key)

        forecast = template_params.get("forecast", [])
        if not forecast:
            raise RuntimeError("Forecast data unavailable.")

        current_day = forecast[0]
        forecast_days = max(1, min(4, int(settings.get("forecastDays", 4))))
        forecast_rows = forecast[1:1 + forecast_days] if len(forecast) > 1 else forecast[:forecast_days]
        labels = get_language_labels(language)

        # Use the provider timezone that was returned from _get_template_params.
        # This matches the timezone used to parse the forecast and respects the
        # user's `weatherTimeZone` selection (locationTimeZone vs device timezone).
        now = datetime.datetime.now(provider_tz)
        localized_date = format_localized_date(language, now)

        # Keep weekday indexes aligned with calendar dates for future layout variants.
        logger.debug("Duo Weather NOW date: %s (%s)", now.strftime("%Y-%m-%d"), now.strftime("%A"))
        for i, row in enumerate(forecast_rows):
            target_date = now + datetime.timedelta(days=i + 1)
            row["weekday_index"] = target_date.weekday()  # Monday=0 .. Sunday=6
            logger.debug(
                "  Forecast row %d: %s (%s) weekday_index=%d",
                i + 1, target_date.strftime("%Y-%m-%d"), target_date.strftime("%A"), row["weekday_index"],
            )

        current_icon = template_params.get("current_day_icon", "")
        condition_key, is_night = self._condition_from_icon(current_icon)
        if condition_key == "mostly_sunny" and is_night:
            condition_key = "mostly_clear"
        condition_label = labels.get("conditions", {}).get(condition_key, labels.get("conditions", {}).get("cloudy", "Cloudy"))
        hourly_points = self._select_hourly_points(
            template_params.get("hourly_forecast", []),
            now,
            count=HOURLY_POINT_COUNT,
        )

        template_params.update(
            {
                "title": title,
                "current_label": labels["now"],
                "date": localized_date,
                "current_time": self._format_clock(now, time_format),
                "current_condition": condition_label,
                "current_high": current_day["high"],
                "current_low": current_day["low"],
                "high_label": labels.get("high", "H"),
                "low_label": labels.get("low", "L"),
                "forecast_rows": self._localize_forecast_rows(forecast_rows, labels),
                "forecast_days": len(forecast_rows),
                "hourly_points": hourly_points,
                "sky_theme": self._sky_theme(condition_key, is_night),
                "is_night": is_night,
                "provider_timezone": provider_tz.zone,
                "plugin_settings": settings,
                "show_icons": settings.get("showIcons", "true") != "false",
                "color_icons": settings.get("colorIcons", "false") == "true",
            }
        )

        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]

        image = self.render_image(dimensions, "duo_weather.html", "duo_weather.css", template_params)
        if not image:
            raise RuntimeError("Failed to take screenshot, please check logs.")
        return image

    def _localize_forecast_rows(self, forecast_rows, labels):
        localized_rows = []
        # English abbreviations and full names used as fallback mapping
        EN_ABBR = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        EN_FULL = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        for row in forecast_rows:
            row_copy = dict(row)
            weekday_index = row_copy.get("weekday_index")

            # If weekday_index not present, try to derive it from the day label
            if weekday_index is None:
                day_lbl = str(row_copy.get("day", "")).strip()
                if day_lbl:
                    # try to match common 3-letter English abbreviations
                    for idx, abbr in enumerate(EN_ABBR):
                        if day_lbl.startswith(abbr) or day_lbl.lower().startswith(abbr.lower()):
                            weekday_index = idx
                            break
                    else:
                        # try full English name
                        for idx, full in enumerate(EN_FULL):
                            if day_lbl.lower().startswith(full.lower()):
                                weekday_index = idx
                                break

            if isinstance(weekday_index, int):
                row_copy["day"] = labels["days"][weekday_index % 7]

            localized_rows.append(row_copy)

        return localized_rows

    def _get_template_params(
        self,
        weather_provider,
        settings,
        units,
        lat,
        long,
        local_tz,
        time_format,
        device_config,
    ):
        timezone_selection = settings.get("weatherTimeZone", "locationTimeZone")
        api_key = None

        if weather_provider == "OpenWeatherMap":
            api_key = device_config.load_env_key("OPEN_WEATHER_MAP_SECRET")
            if not api_key:
                raise RuntimeError("Open Weather Map API Key not configured.")

            weather_data = self.get_weather_data(api_key, units, lat, long)
            aqi_data = self.get_air_quality(api_key, lat, long)
            tz = self.parse_timezone(weather_data) if timezone_selection == "locationTimeZone" else local_tz
            template_params = self.parse_weather_data(weather_data, aqi_data, tz, units, time_format, lat)
            return template_params, tz, api_key

        if weather_provider == "OpenMeteo":
            weather_data = self.get_open_meteo_data(lat, long, units, 5)
            aqi_data = self.get_open_meteo_air_quality(lat, long)
            tz = self.parse_open_meteo_timezone(weather_data) if timezone_selection == "locationTimeZone" else local_tz
            template_params = self.parse_open_meteo_data(weather_data, aqi_data, tz, units, time_format, lat)
            return template_params, tz, api_key

        raise RuntimeError(f"Unknown weather provider: {weather_provider}")

    def _resolve_title(self, settings, weather_provider, lat, long, api_key):
        title_selection = settings.get("titleSelection", "location")
        custom_title = (settings.get("customTitle") or "").strip()

        if title_selection == "custom":
            if not custom_title:
                raise RuntimeError("Custom title is required.")
            return custom_title

        if weather_provider == "OpenWeatherMap":
            return self.get_location(api_key, lat, long)

        return self.get_reverse_geocoded_location(lat, long)

    def _resolve_title_with_fallback(self, settings, weather_provider, lat, long, api_key):
        try:
            title = self._resolve_title(settings, weather_provider, lat, long, api_key)
            if is_supported_title(title):
                return title
        except Exception as exc:
            logger.warning("Duo Weather title resolution failed, using fallback: %s", exc)

        quick_location = (settings.get("quickLocation") or "").strip()
        quick_location_label = QUICK_LOCATION_LABELS.get(quick_location)
        if quick_location_label:
            return quick_location_label

        matched_city = self._match_quick_location_by_coordinates(lat, long)
        if matched_city:
            return matched_city

        return self.format_coordinates(lat, long)

    def _match_quick_location_by_coordinates(self, lat, long, tolerance=0.02):
        for city, (city_lat, city_long) in QUICK_LOCATION_COORDS.items():
            if abs(lat - city_lat) <= tolerance and abs(long - city_long) <= tolerance:
                return city
        return None

    def parse_open_meteo_timezone(self, weather_data):
        timezone_name = weather_data.get("timezone")
        if not timezone_name:
            raise RuntimeError("Timezone not found in weather data.")

        logger.info("Using timezone from Open-Meteo data: %s", timezone_name)
        return pytz.timezone(timezone_name)

    def get_reverse_geocoded_location(self, lat, long):
        # Use rounded coordinates as cache key to avoid tiny float differences
        key = (round(float(lat), REVERSE_GEOCODE_ROUND_DECIMALS), round(float(long), REVERSE_GEOCODE_ROUND_DECIMALS))

        now_ts = datetime.datetime.now().timestamp()
        cached = REVERSE_GEOCODE_CACHE.get(key)
        if cached:
            age = now_ts - cached.get("ts", 0)
            if cached.get("title") and age < REVERSE_GEOCODE_SUCCESS_TTL:
                return cached["title"]
            if cached.get("failed") and age < REVERSE_GEOCODE_FAIL_TTL:
                # recent failure — avoid retrying too quickly
                return self.format_coordinates(lat, long)

        headers = {"User-Agent": "InkyPi Duo Weather/1.0 (+https://github.com/inkypi)"}
        try:
            response = requests.get(
                REVERSE_GEOCODE_URL.format(lat=lat, long=long),
                headers=headers,
                timeout=30,
            )
        except Exception as exc:
            logger.warning("Reverse geocode request failed: %s", exc)
            # store a failed marker to avoid hammering the service
            REVERSE_GEOCODE_CACHE[key] = {"failed": True, "ts": now_ts}
            return self.format_coordinates(lat, long)

        if not 200 <= response.status_code < 300:
            logger.warning("Failed to reverse geocode location: %s", response.content)
            REVERSE_GEOCODE_CACHE[key] = {"failed": True, "ts": now_ts}
            return self.format_coordinates(lat, long)

        try:
            location_data = response.json()
        except Exception as exc:
            logger.warning("Invalid JSON from reverse geocode: %s", exc)
            REVERSE_GEOCODE_CACHE[key] = {"failed": True, "ts": now_ts}
            return self.format_coordinates(lat, long)

        address = location_data.get("address", {})

        city = (
            address.get("city")
            or address.get("town")
            or address.get("village")
            or address.get("municipality")
            or address.get("county")
        )
        region = address.get("state") or address.get("country")

        if city and region:
            title = f"{city}, {region}"
        elif city:
            title = city
        elif region:
            title = region
        else:
            display_name = location_data.get("display_name", "")
            if display_name:
                title = ", ".join(display_name.split(", ")[:2])
            else:
                title = self.format_coordinates(lat, long)

        # Cache successful result
        REVERSE_GEOCODE_CACHE[key] = {"title": title, "ts": now_ts}
        return title

    def format_coordinates(self, lat, long):
        return f"{lat:.2f}, {long:.2f}"

    def _condition_from_icon(self, icon_path):
        icon_name = os.path.splitext(os.path.basename(icon_path or ""))[0].lower()
        is_night = icon_name.endswith("n")
        condition_key = ICON_CONDITION_KEYS.get(icon_name, "cloudy")
        return condition_key, is_night

    def _sky_theme(self, condition_key, is_night):
        sky = SKY_BY_CONDITION.get(condition_key, "cloudy")
        if is_night:
            return f"{sky}-night"
        return sky

    def _format_clock(self, dt, time_format):
        if time_format == "24h":
            return dt.strftime("%H:%M")
        return dt.strftime("%I:%M").lstrip("0") or "0:00"

    def _compact_hour_label(self, time_label):
        label = str(time_label or "").strip()
        if not label:
            return label
        compact = label.replace(" ", "")
        compact = compact.replace(".M.", "M").replace("a.m.", "AM").replace("p.m.", "PM")
        compact = compact.replace("A.M.", "AM").replace("P.M.", "PM")
        compact = compact.replace("am", "AM").replace("pm", "PM")
        return compact

    def _select_hourly_points(self, hourly_forecast, now, count=HOURLY_POINT_COUNT):
        # Provider parsers already start hourly data at the current hour.
        # Prefer remaining hours of the same day, then sample ~2-hour steps.
        if not hourly_forecast:
            return []

        points = []
        for hour in hourly_forecast:
            point = dict(hour)
            point["time"] = self._compact_hour_label(point.get("time"))
            try:
                point["temperature"] = int(round(float(point.get("temperature", 0))))
            except (TypeError, ValueError):
                point["temperature"] = 0
            points.append(point)

        remaining_today = max(1, 24 - int(getattr(now, "hour", 0)))
        today_points = points[: min(remaining_today, len(points))]
        source = today_points if len(today_points) >= count else points

        if len(source) <= count:
            return source

        stepped = source[::HOURLY_STEP_HOURS]
        if len(stepped) >= count:
            return stepped[:count]
        return source[:count]
