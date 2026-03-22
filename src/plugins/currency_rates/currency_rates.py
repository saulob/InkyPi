from plugins.base_plugin.base_plugin import BasePlugin
from utils.http_client import get_http_session
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

FRANKFURTER_BASE_URL = "https://api.frankfurter.dev/v1"
FRANKFURTER_LATEST_URL = FRANKFURTER_BASE_URL + "/latest?base={base}&symbols={target}"
FRANKFURTER_TIMESERIES_URL = FRANKFURTER_BASE_URL + "/{start}..{end}?base={base}&symbols={target}"
FRANKFURTER_CURRENCIES_URL = FRANKFURTER_BASE_URL + "/currencies"

FALLBACK_CURRENCIES = {
    "EUR": "Euro",
    "USD": "United States Dollar",
    "BRL": "Brazilian Real",
    "GBP": "British Pound",
    "JPY": "Japanese Yen",
    "CAD": "Canadian Dollar",
    "AUD": "Australian Dollar",
    "CHF": "Swiss Franc",
    "CNY": "Chinese Renminbi Yuan",
}

CURRENCY_SYMBOLS = {
    "BRL": "R$",
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "JPY": "¥",
    "AUD": "A$",
    "CAD": "C$",
    "CHF": "CHF",
    "CNY": "¥",
}


def fetch_supported_currencies():
    """Fetch supported currencies from the API, with local fallback."""
    try:
        session = get_http_session()
        response = session.get(FRANKFURTER_CURRENCIES_URL, timeout=15)
        if 200 <= response.status_code < 300:
            return response.json()
    except Exception as e:
        logger.warning(f"Failed to fetch currency list from API: {e}")
    return FALLBACK_CURRENCIES


def fetch_rate(base, target):
    """Fetch the latest exchange rate for base/target pair."""
    session = get_http_session()
    url = FRANKFURTER_LATEST_URL.format(base=base, target=target)
    response = session.get(url, timeout=30)
    if not 200 <= response.status_code < 300:
        logger.error(f"Failed to fetch rate for {base}/{target}: {response.status_code}")
        raise RuntimeError(f"Failed to fetch rate for {base}/{target}")
    data = response.json()
    return data["rates"][target]


def fetch_recent_rates(base, target):
    """Fetch a short time-series window and return the two latest rates."""
    today = datetime.now().date()
    start = today - timedelta(days=10)
    session = get_http_session()
    url = FRANKFURTER_TIMESERIES_URL.format(
        start=start.strftime("%Y-%m-%d"),
        end=today.strftime("%Y-%m-%d"),
        base=base,
        target=target,
    )
    response = session.get(url, timeout=30)
    if not 200 <= response.status_code < 300:
        logger.warning(f"Failed to fetch time-series for {base}/{target}: {response.status_code}")
        return None, None
    data = response.json()
    rates = data.get("rates", {})
    if len(rates) < 2:
        logger.warning(f"Not enough data points for {base}/{target}")
        return None, None
    sorted_dates = sorted(rates.keys())
    latest = rates[sorted_dates[-1]][target]
    previous = rates[sorted_dates[-2]][target]
    return latest, previous


def calculate_percentage(current, previous):
    """Calculate percentage change between current and previous values."""
    if previous is None or previous == 0:
        return None
    return ((current - previous) / previous) * 100


def format_value(value):
    """Format a rate value with 2 decimal places."""
    return f"{value:,.2f}"


def format_percentage(value):
    """Format percentage with + or - sign, 2 decimal places."""
    if value is None:
        return None
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f}%"


def get_currency_symbol(currency_code):
    """Get the symbol for a currency code, fallback to code if not found."""
    return CURRENCY_SYMBOLS.get(currency_code, currency_code)


class CurrencyRates(BasePlugin):
    def generate_settings_template(self):
        template_params = super().generate_settings_template()
        template_params["currencies"] = fetch_supported_currencies()
        return template_params

    def generate_image(self, settings, device_config):
        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]

        title = (
            settings.get("customTitle")
            or settings.get("title")
            or "Currency Rates"
        ).strip()

        pairs = [
            {
                "from": settings.get("from_currency_1", "EUR"),
                "to": settings.get("to_currency_1", "USD"),
            },
            {
                "from": settings.get("from_currency_2", "USD"),
                "to": settings.get("to_currency_2", "EUR"),
            },
        ]

        currency_data = []
        for pair in pairs:
            base = pair["from"]
            target = pair["to"]
            label = f"{base}/{target}"
            symbol = get_currency_symbol(target)
            try:
                current, previous = fetch_recent_rates(base, target)
                if current is None:
                    current = fetch_rate(base, target)
                pct = calculate_percentage(current, previous)
                currency_data.append({
                    "label": label,
                    "value": format_value(current),
                    "symbol": symbol,
                    "percentage": format_percentage(pct),
                    "positive": pct is not None and pct >= 0,
                })
            except Exception as e:
                logger.error(f"Error fetching {label}: {e}")
                currency_data.append({
                    "label": label,
                    "value": "—",
                    "symbol": symbol,
                    "percentage": None,
                    "positive": True,
                })

        if all(c["value"] == "—" for c in currency_data):
            raise RuntimeError("Failed to fetch any currency data. Check your connection.")

        template_params = {
            "title": title,
            "currencies": currency_data,
            "plugin_settings": settings,
        }

        image = self.render_image(
            dimensions, "currency_rates.html", "currency_rates.css", template_params
        )

        if not image:
            raise RuntimeError("Failed to render currency rates image.")
        return image
