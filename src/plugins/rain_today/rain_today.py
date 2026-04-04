import logging
import datetime

import pytz
import requests

from plugins.base_plugin.base_plugin import BasePlugin

logger = logging.getLogger(__name__)

OPEN_METEO_RAIN_URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude={lat}&longitude={long}"
    "&hourly=weather_code,temperature_2m,precipitation,precipitation_probability,"
    "relative_humidity_2m"
    "&current=temperature_2m,weather_code,is_day,precipitation,relative_humidity_2m"
    "&timezone=auto&forecast_days=2"
)

OPEN_METEO_UNIT_PARAMS = {
    "standard": "temperature_unit=celsius&precipitation_unit=mm",
    "metric": "temperature_unit=celsius&precipitation_unit=mm",
    "imperial": "temperature_unit=fahrenheit&precipitation_unit=inch",
}

REVERSE_GEOCODE_URL = (
    "https://nominatim.openstreetmap.org/reverse"
    "?lat={lat}&lon={long}&format=jsonv2&addressdetails=1&zoom=10"
)

REVERSE_GEOCODE_CACHE = {}
REVERSE_GEOCODE_SUCCESS_TTL = 7 * 24 * 60 * 60
REVERSE_GEOCODE_FAIL_TTL = 60 * 60
REVERSE_GEOCODE_ROUND_DECIMALS = 4

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

# ---------------------------------------------------------------------------
# Locale data – same languages as Mini Weather
# ---------------------------------------------------------------------------
LOCALE_DATA = {
    "de": {
        "drizzle": "Nieselregen",
        "light_rain": "Leichter Regen",
        "rain": "Regen",
        "heavy_rain": "Starkregen",
        "showers": "Schauer",
        "freezing_drizzle": "Gefrierender Nieselregen",
        "freezing_rain": "Gefrierender Regen",
        "thunderstorm": "Gewitter",
        "no_rain": "Kein Regen",
        "chance": "{pct}% Wahrscheinlichkeit",
        "ends_at": "Endet um {time}",
        "no_end": "Kein Ende absehbar",
        "humidity": "Feuchtigkeit",
        "precipitation": "Niederschlag",
    },
    "en": {
        "drizzle": "Drizzle",
        "light_rain": "Light Rain",
        "rain": "Rain",
        "heavy_rain": "Heavy Rain",
        "showers": "Showers",
        "freezing_drizzle": "Freezing Drizzle",
        "freezing_rain": "Freezing Rain",
        "thunderstorm": "Thunderstorm",
        "no_rain": "No Rain",
        "chance": "{pct}% chance",
        "ends_at": "Ends at {time}",
        "no_end": "No end in sight",
        "humidity": "Humidity",
        "precipitation": "Precipitation",
    },
    "es": {
        "drizzle": "Llovizna",
        "light_rain": "Lluvia ligera",
        "rain": "Lluvia",
        "heavy_rain": "Lluvia intensa",
        "showers": "Chubascos",
        "freezing_drizzle": "Llovizna helada",
        "freezing_rain": "Lluvia helada",
        "thunderstorm": "Tormenta",
        "no_rain": "Sin lluvia",
        "chance": "{pct}% de probabilidad",
        "ends_at": "Termina a las {time}",
        "no_end": "Sin fin a la vista",
        "humidity": "Humedad",
        "precipitation": "Precipitación",
    },
    "fr": {
        "drizzle": "Bruine",
        "light_rain": "Pluie légère",
        "rain": "Pluie",
        "heavy_rain": "Forte pluie",
        "showers": "Averses",
        "freezing_drizzle": "Bruine verglaçante",
        "freezing_rain": "Pluie verglaçante",
        "thunderstorm": "Orage",
        "no_rain": "Pas de pluie",
        "chance": "{pct}% de chance",
        "ends_at": "Fin à {time}",
        "no_end": "Pas de fin en vue",
        "humidity": "Humidité",
        "precipitation": "Précipitation",
    },
    "id": {
        "drizzle": "Gerimis",
        "light_rain": "Hujan Ringan",
        "rain": "Hujan",
        "heavy_rain": "Hujan Lebat",
        "showers": "Hujan Lokal",
        "freezing_drizzle": "Gerimis Beku",
        "freezing_rain": "Hujan Beku",
        "thunderstorm": "Badai Petir",
        "no_rain": "Tidak Hujan",
        "chance": "{pct}% kemungkinan",
        "ends_at": "Berakhir pukul {time}",
        "no_end": "Belum diketahui",
        "humidity": "Kelembapan",
        "precipitation": "Presipitasi",
    },
    "it": {
        "drizzle": "Pioggerella",
        "light_rain": "Pioggia leggera",
        "rain": "Pioggia",
        "heavy_rain": "Pioggia forte",
        "showers": "Rovesci",
        "freezing_drizzle": "Pioggerella gelata",
        "freezing_rain": "Pioggia gelata",
        "thunderstorm": "Temporale",
        "no_rain": "Nessuna pioggia",
        "chance": "{pct}% probabilità",
        "ends_at": "Finisce alle {time}",
        "no_end": "Nessuna fine in vista",
        "humidity": "Umidità",
        "precipitation": "Precipitazione",
    },
    "nl": {
        "drizzle": "Motregen",
        "light_rain": "Lichte regen",
        "rain": "Regen",
        "heavy_rain": "Zware regen",
        "showers": "Buien",
        "freezing_drizzle": "Ijzel",
        "freezing_rain": "Ijsregen",
        "thunderstorm": "Onweer",
        "no_rain": "Geen regen",
        "chance": "{pct}% kans",
        "ends_at": "Eindigt om {time}",
        "no_end": "Geen einde in zicht",
        "humidity": "Vochtigheid",
        "precipitation": "Neerslag",
    },
    "pt": {
        "drizzle": "Chuvisco",
        "light_rain": "Chuva leve",
        "rain": "Chuva",
        "heavy_rain": "Chuva forte",
        "showers": "Pancadas",
        "freezing_drizzle": "Chuvisco congelante",
        "freezing_rain": "Chuva congelante",
        "thunderstorm": "Trovoada",
        "no_rain": "Sem chuva",
        "chance": "{pct}% de chance",
        "ends_at": "Termina às {time}",
        "no_end": "Sem previsão de parar",
        "humidity": "Humidade",
        "precipitation": "Precipitação",
    },
}

# ---------------------------------------------------------------------------
# WMO weather code → rain description key
# ---------------------------------------------------------------------------
RAIN_CODE_MAP = {
    51: "drizzle",
    53: "drizzle",
    55: "drizzle",
    56: "freezing_drizzle",
    57: "freezing_drizzle",
    61: "light_rain",
    63: "rain",
    65: "heavy_rain",
    66: "freezing_rain",
    67: "freezing_rain",
    80: "showers",
    81: "showers",
    82: "heavy_rain",
    95: "thunderstorm",
    96: "thunderstorm",
    99: "thunderstorm",
}

# Precipitation probability and mm/h thresholds to consider rain "ended"
RAIN_END_PROB_THRESHOLD = 10
RAIN_END_PRECIP_THRESHOLD = 0.1


def _get_locale(language):
    lang = (language or "en").lower().split("-")[0].split("_")[0]
    return LOCALE_DATA.get(lang, LOCALE_DATA["en"])


class RainToday(BasePlugin):

    # ------------------------------------------------------------------
    # Settings template
    # ------------------------------------------------------------------
    def generate_settings_template(self):
        template_params = super().generate_settings_template()
        template_params['api_key'] = {
            "required": True,
            "service": "OpenWeatherMap",
            "expected_key": "OPEN_WEATHER_MAP_SECRET"
        }
        return template_params

    # ------------------------------------------------------------------
    # Main image generation
    # ------------------------------------------------------------------
    def generate_image(self, settings, device_config):
        lat_value = settings.get("latitude")
        long_value = settings.get("longitude")
        if lat_value in (None, "") or long_value in (None, ""):
            raise RuntimeError("Latitude and Longitude are required.")

        try:
            lat = float(str(lat_value).strip())
            long = float(str(long_value).strip())
        except (ValueError, TypeError):
            raise RuntimeError("Latitude and Longitude must be valid numeric values.")

        if not (-90.0 <= lat <= 90.0):
            raise RuntimeError("Latitude must be between -90 and 90.")
        if not (-180.0 <= long <= 180.0):
            raise RuntimeError("Longitude must be between -180 and 180.")

        units = settings.get("units", "imperial")
        language = str(settings.get("language", "en")).strip() or "en"

        timezone_name = device_config.get_config("timezone", default="America/New_York")
        time_format = device_config.get_config("time_format", default="12h")
        local_tz = pytz.timezone(timezone_name)

        # Fetch weather data from Open-Meteo
        weather_data = self._fetch_weather(lat, long, units)
        tz = self._parse_timezone(weather_data, local_tz)
        now = datetime.datetime.now(tz)

        # Parse current conditions
        current = weather_data.get("current", {})
        hourly = weather_data.get("hourly", {})

        temperature_conversion = 273.15 if units == "standard" else 0.0
        current_temp = round(current.get("temperature_2m", 0) + temperature_conversion)
        current_humidity = current.get("relative_humidity_2m", 0)
        current_precip = current.get("precipitation", 0.0)
        weather_code = current.get("weather_code", 0)

        locale = _get_locale(language)

        # Rain description from weather code
        rain_key = RAIN_CODE_MAP.get(weather_code, "no_rain")
        rain_description = locale.get(rain_key, locale["no_rain"])

        # Find current hour index in hourly data
        hour_index = self._find_current_hour_index(hourly, now, tz)

        # Rain probability for current hour
        rain_prob = 0
        if hour_index is not None:
            probs = hourly.get("precipitation_probability", [])
            if hour_index < len(probs) and probs[hour_index] is not None:
                rain_prob = probs[hour_index]

        # Rain end time – always shown when rain is detected
        rain_end_text = ""
        if rain_key != "no_rain":
            rain_end_text = self._infer_rain_end(hourly, hour_index, tz, time_format, locale)

        # Chance text
        chance_text = locale["chance"].format(pct=rain_prob)

        # Precipitation rate – use current value, fallback to hourly
        precip_rate = current_precip
        if precip_rate == 0 and hour_index is not None:
            precips = hourly.get("precipitation", [])
            if hour_index < len(precips) and precips[hour_index] is not None:
                precip_rate = precips[hour_index]

        precip_unit = "in/h" if units == "imperial" else "mm/h"
        precip_display = f"{precip_rate:.1f}" if precip_rate < 10 else f"{round(precip_rate)}"

        # Resolve location title
        title = self._resolve_title(settings, lat, long)

        # Unit symbols
        if units == "metric":
            temp_unit = "°C"
        elif units == "imperial":
            temp_unit = "°F"
        else:
            temp_unit = "K"

        template_params = {
            "title": title,
            "current_temp": str(current_temp),
            "temp_unit": temp_unit,
            "rain_key": rain_key,
            "rain_description": rain_description,
            "chance_text": chance_text,
            "rain_end_text": rain_end_text,
            "humidity": current_humidity,
            "humidity_label": locale["humidity"],
            "precip_display": precip_display,
            "precip_unit": precip_unit,
            "precip_label": locale["precipitation"],
            "plugin_settings": settings,
        }

        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]

        image = self.render_image(dimensions, "rain_today.html", "rain_today.css", template_params)
        if not image:
            raise RuntimeError("Failed to take screenshot, please check logs.")
        return image

    # ------------------------------------------------------------------
    # Open-Meteo API
    # ------------------------------------------------------------------
    def _fetch_weather(self, lat, long, units):
        unit_params = OPEN_METEO_UNIT_PARAMS.get(units, OPEN_METEO_UNIT_PARAMS["metric"])
        url = OPEN_METEO_RAIN_URL.format(lat=lat, long=long) + f"&{unit_params}"
        response = requests.get(url, timeout=30)
        if not 200 <= response.status_code < 300:
            logger.error("Failed to retrieve Open-Meteo data: %s", response.content)
            raise RuntimeError("Failed to retrieve Open-Meteo weather data.")
        return response.json()

    def _parse_timezone(self, weather_data, fallback_tz):
        tz_name = weather_data.get("timezone")
        if tz_name:
            try:
                return pytz.timezone(tz_name)
            except pytz.exceptions.UnknownTimeZoneError:
                pass
        return fallback_tz

    # ------------------------------------------------------------------
    # Hourly helpers
    # ------------------------------------------------------------------
    def _find_current_hour_index(self, hourly, now, tz):
        times = hourly.get("time", [])
        current_hour_str = now.strftime("%Y-%m-%dT%H:00")
        for i, t in enumerate(times):
            if t == current_hour_str:
                return i
        return None

    def _infer_rain_end(self, hourly, hour_index, tz, time_format, locale):
        if hour_index is None:
            return ""

        probs = hourly.get("precipitation_probability", [])
        precips = hourly.get("precipitation", [])
        times = hourly.get("time", [])

        for i in range(hour_index + 1, len(times)):
            prob = probs[i] if i < len(probs) and probs[i] is not None else 0
            precip = precips[i] if i < len(precips) and precips[i] is not None else 0.0

            if prob <= RAIN_END_PROB_THRESHOLD and precip <= RAIN_END_PRECIP_THRESHOLD:
                end_dt = datetime.datetime.fromisoformat(times[i]).replace(tzinfo=tz)
                if time_format == "12h":
                    time_str = end_dt.strftime("%I:%M %p").lstrip("0")
                else:
                    time_str = end_dt.strftime("%H:%M")
                return locale["ends_at"].format(time=time_str)

        return locale["no_end"]

    # ------------------------------------------------------------------
    # Location resolution (reused from Mini Weather patterns)
    # ------------------------------------------------------------------
    def _resolve_title(self, settings, lat, long):
        quick_location = (settings.get("quickLocation") or "").strip()
        label = QUICK_LOCATION_LABELS.get(quick_location)
        if label:
            return label

        matched = self._match_quick_location_by_coordinates(lat, long)
        if matched:
            return matched

        return self._reverse_geocode(lat, long)

    def _match_quick_location_by_coordinates(self, lat, long, tolerance=0.02):
        for city, (city_lat, city_long) in QUICK_LOCATION_COORDS.items():
            if abs(lat - city_lat) <= tolerance and abs(long - city_long) <= tolerance:
                return city
        return None

    def _reverse_geocode(self, lat, long):
        key = (round(float(lat), REVERSE_GEOCODE_ROUND_DECIMALS),
               round(float(long), REVERSE_GEOCODE_ROUND_DECIMALS))
        now_ts = datetime.datetime.now().timestamp()

        cached = REVERSE_GEOCODE_CACHE.get(key)
        if cached:
            age = now_ts - cached.get("ts", 0)
            if cached.get("title") and age < REVERSE_GEOCODE_SUCCESS_TTL:
                return cached["title"]
            if cached.get("failed") and age < REVERSE_GEOCODE_FAIL_TTL:
                return f"{lat:.2f}, {long:.2f}"

        headers = {"User-Agent": "InkyPi Rain Today/1.0 (+https://github.com/inkypi)"}
        try:
            response = requests.get(
                REVERSE_GEOCODE_URL.format(lat=lat, long=long),
                headers=headers,
                timeout=30,
            )
        except Exception as exc:
            logger.warning("Reverse geocode request failed: %s", exc)
            REVERSE_GEOCODE_CACHE[key] = {"failed": True, "ts": now_ts}
            return f"{lat:.2f}, {long:.2f}"

        if not 200 <= response.status_code < 300:
            REVERSE_GEOCODE_CACHE[key] = {"failed": True, "ts": now_ts}
            return f"{lat:.2f}, {long:.2f}"

        try:
            data = response.json()
        except Exception:
            REVERSE_GEOCODE_CACHE[key] = {"failed": True, "ts": now_ts}
            return f"{lat:.2f}, {long:.2f}"

        address = data.get("address", {})
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
            display_name = data.get("display_name", "")
            title = ", ".join(display_name.split(", ")[:2]) if display_name else f"{lat:.2f}, {long:.2f}"

        REVERSE_GEOCODE_CACHE[key] = {"title": title, "ts": now_ts}
        return title
