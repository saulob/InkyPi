from plugins.base_plugin.base_plugin import BasePlugin
from utils.http_client import get_http_session
from datetime import datetime
import os
import json
import logging

logger = logging.getLogger(__name__)


class CryptoTracker(BasePlugin):
    CACHE_TTL_SECONDS = 180  # 3 minutes

    def generate_settings_template(self):
        template_params = super().generate_settings_template()
        template_params['style_settings'] = False
        return template_params

    def _read_cache(self):
        cache_file = os.path.join(self.get_plugin_dir(), 'cache.json')
        if not os.path.isfile(cache_file):
            return None
        try:
            with open(cache_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.debug(f"Failed to read cache: {e}")
            return None

    def _write_cache(self, obj):
        cache_file = os.path.join(self.get_plugin_dir(), 'cache.json')
        try:
            with open(cache_file, 'w') as f:
                json.dump(obj, f)
        except Exception as e:
            logger.debug(f"Failed to write cache: {e}")

    def _cache_valid(self, cache_obj):
        if not cache_obj:
            return False
        try:
            ts = cache_obj.get('ts')
            age = (datetime.utcnow().timestamp() - ts)
            return age < self.CACHE_TTL_SECONDS
        except Exception:
            return False

    def generate_image(self, settings, device_config):
        logger.info("=== CryptoTracker: generating image ===")

        # Parse settings: prefer coin_1/coin_2/coin_3 fields; fallback to older 'coins' field
        coins = []
        for i in range(1, 4):
            key = f'coin_{i}'
            val = settings.get(key)
            if val and isinstance(val, str) and val.strip():
                coins.append(val.strip().lower())

        if not coins:
            # backward compatibility with comma-separated field
            coins_raw = settings.get('coins') or 'bitcoin,ethereum,solana'
            coins = [c.strip().lower() for c in coins_raw.split(',') if c.strip()]

        # Ensure at least defaults and limit to 3, avoid duplicates while filling defaults
        defaults = ['bitcoin', 'ethereum', 'solana']
        final = []
        for c in coins:
            if c not in final:
                final.append(c)
            if len(final) >= 3:
                break
        for d in defaults:
            if len(final) >= 3:
                break
            if d not in final:
                final.append(d)
        coins = final[:3]

        # Normalize quote currency to lowercase for consistent API keys
        vs_currency = settings.get('vs_currency') or 'usd'
        if isinstance(vs_currency, str):
            vs_currency = vs_currency.strip().lower()
        else:
            vs_currency = str(vs_currency).lower()

        show_24h = settings.get('show_24h_change', 'true') in ('true', True, 'True')
        show_symbol = settings.get('show_symbol', 'true') in ('true', True, 'True')
        try:
            decimal_places = int(settings.get('decimal_places', 2))
        except Exception:
            decimal_places = 2
        # enforce allowed range 0..4
        decimal_places = max(0, min(4, decimal_places))

        # Try cache - only use if it contains data for the requested vs_currency
        cache = self._read_cache()
        use_cache = False
        data = {}
        if self._cache_valid(cache):
            cache_data = cache.get('data', {})
            cache_vs = cache.get('vs')
            # if cache records a different requested currency, ignore cache
            if cache_vs and cache_vs != vs_currency:
                cache_data = {}
            
            # ensure cache contains price keys for the requested currency for all coins
            has_currency = True
            for c in coins:
                entry = cache_data.get(c)
                if not entry:
                    has_currency = False
                    break
                # check for currency key or any 24h change key matching currency
                if vs_currency not in entry and not any(k.lower().startswith(vs_currency) for k in entry.keys()):
                    has_currency = False
                    break
            if has_currency:
                logger.debug("Using cached CoinGecko data for currency %s", vs_currency)
                data = cache_data
                use_cache = True

        if not use_cache:
            # Build request
            ids = ','.join(coins)
            params = {
                'ids': ids,
                'vs_currencies': vs_currency,
                'include_24hr_change': 'true'
            }

            session = get_http_session()
            headers = {'User-Agent': session.headers.get('User-Agent')}

            try:
                url = 'https://api.coingecko.com/api/v3/simple/price'
                logger.debug(f"Requesting CoinGecko: ids={ids} vs={vs_currency}")
                response = session.get(url, params=params, headers=headers, timeout=10)
                if response.status_code != 200:
                    logger.error(f"CoinGecko API error: {response.status_code} {response.text}")
                    raise RuntimeError("Failed to retrieve cryptocurrency prices from CoinGecko.")

                data = response.json()
                # Write cache with returned data and record which currency was requested
                self._write_cache({'ts': datetime.utcnow().timestamp(), 'data': data, 'vs': vs_currency})
            except Exception as e:
                logger.error(f"CoinGecko request failed: {e}")
                raise RuntimeError("Failed to retrieve data from CoinGecko.")

        # Prepare lines for up to 3 coins
        rows = []
        for c in coins:
            entry = data.get(c)
            # Try to find a local icon for the coin
            icon_path = self._get_icon_path(c)
            # Friendly display names and tickers for common coins
            TICKER_MAP = {
                'bitcoin': 'BTC',
                'ethereum': 'ETH',
                'solana': 'SOL',
                'litecoin': 'LTC',
                'ripple': 'XRP',
                'dogecoin': 'DOGE'
            }
            NAME_MAP = {
                'bitcoin': 'Bitcoin',
                'ethereum': 'Ethereum',
                'solana': 'Solana',
                'litecoin': 'Litecoin',
                'ripple': 'XRP',
                'dogecoin': 'Dogecoin'
            }
            if not entry:
                rows.append({
                    'coin': c,
                    'display_name': NAME_MAP.get(c, c.replace('-', ' ').title()),
                    'symbol': (TICKER_MAP.get(c, c[:3].upper()) if show_symbol else ''),
                    'price': 'N/A',
                    'change': None,
                    'raw_change': None,
                    'icon': icon_path
                })
                continue

            # Read price and 24h change using the selected quote currency keys
            price = None
            change = None
            if isinstance(entry, dict):
                # price key should be the currency code (e.g., 'usd' or 'brl')
                price = entry.get(vs_currency)

                # robust fallback: check keys case-insensitively
                if price is None:
                    for k, v in entry.items():
                        if k.lower() == vs_currency:
                            price = v
                            break

                # change key normally is '<currency>_24h_change'
                change_key = f"{vs_currency}_24h_change"
                change = entry.get(change_key)
                if change is None:
                    # fallback: find any key that contains '24h' (case-insensitive)
                    for k, v in entry.items():
                        if '24h' in k.lower():
                            change = v
                            break

            if price is None:
                price_display = 'N/A'
            else:
                price_display = f"{price:,.{decimal_places}f}"

            if change is None:
                change_display = 'N/A'
            else:
                sign = '+' if change >= 0 else '-'
                change_display = f"{sign}{abs(change):.{decimal_places}f}%"

            rows.append({
                'coin': c,
                'display_name': NAME_MAP.get(c, c.replace('-', ' ').title()),
                'symbol': (TICKER_MAP.get(c, c[:3].upper()) if show_symbol else ''),
                'price': price_display,
                'change': (None if change is None else change_display),
                'raw_change': change,
                'icon': icon_path
            })

        # Render via template
        dimensions = device_config.get_resolution()
        if device_config.get_config('orientation') == 'vertical':
            dimensions = dimensions[::-1]

        template_params = {
            'title': 'Crypto Tracker',
            'rows': rows,
            'vs_currency': vs_currency.upper(),
            'show_24h': show_24h,
            'show_symbol': show_symbol,
            'plugin_settings': settings
        }

        image = self.render_image(dimensions, 'crypto_tracker.html', 'crypto_tracker.css', template_params)
        logger.info("=== CryptoTracker: image generation complete ===")
        return image

    def _get_icon_path(self, coin):
        # Try to find a static icon for the coin in static/icons/crypto/
        # If not found, return None (template will fallback to badge)
        static_dir = os.path.join('static', 'icons', 'crypto')
        # Try PNG and SVG
        for ext in ('.png', '.svg'):
            rel_path = os.path.join(static_dir, f'{coin}{ext}')
            abs_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', rel_path)
            if os.path.isfile(abs_path):
                # Return as web path for template
                return f'/static/icons/crypto/{coin}{ext}'
        return None
