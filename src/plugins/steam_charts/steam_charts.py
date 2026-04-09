from plugins.base_plugin.base_plugin import BasePlugin
from utils.http_client import get_http_session
import concurrent.futures
import logging
import html
import re
import time

logger = logging.getLogger(__name__)

STEAMCHARTS_HOME_URL = "https://steamcharts.com"
STEAMCHARTS_TOP_URL = "https://steamcharts.com/top"
STEAMCHARTS_CHART_URL = "https://steamcharts.com/app/{appid}/chart-data.json"
STEAM_CAPSULE_URL = "https://cdn.akamai.steamstatic.com/steam/apps/{appid}/capsule_sm_120.jpg"

CHART_MODES = {
    "new_trending": {
        "label": "Trending",
        "source": "steamcharts_trending",
    },
    "top_sellers": {
        "label": "Top Sellers",
        "source": "steamcharts_top",
    },
    "most_played": {
        "label": "Most Played",
        "source": "steamcharts_top",
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

        mode_config = CHART_MODES.get(mode)
        if not mode_config:
            raise RuntimeError(f"Unknown chart mode: {mode}")

        games = self._fetch_games(mode_config["source"], items_count)

        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]

        template_params = {
            "title": "STEAM CHARTS",
            "subtitle": mode_config["label"],
            "games": games,
            "show_images": show_images,
            "plugin_settings": settings,
        }

        return self.render_image(
            dimensions, "steam_charts.html", "steam_charts.css", template_params
        )

    def _fetch_games(self, source, count):
        """Fetch game list and enrich with sparkline data from steamcharts."""
        if source == "steamcharts_trending":
            games = self._scrape_steamcharts_trending(count)
        else:
            games = self._scrape_steamcharts_top(count)

        chart_data = self._fetch_chart_data_batch([g["app_id"] for g in games])

        for game in games:
            app_id = game["app_id"]
            stats = chart_data.get(app_id, {})
            game["sparkline_svg"] = stats.get("sparkline_svg")
            if "change_24h_fmt" not in game:
                game["change_24h_fmt"] = self._format_change(stats.get("change_24h"))
            if "current_players_fmt" not in game:
                game["current_players_fmt"] = self._format_count(
                    stats.get("current_players")
                )

        return games

    def _scrape_steamcharts_trending(self, count):
        """Scrape the Trending section from steamcharts.com homepage."""
        try:
            session = get_http_session()
            resp = session.get(STEAMCHARTS_HOME_URL, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to fetch steamcharts trending: {e}")
            raise RuntimeError("Unable to fetch Steam trending data. Please try again later.")

        trending_block = re.search(r"Trending.*?Top Records", resp.text, re.DOTALL)
        if not trending_block:
            raise RuntimeError("Trending section not found on steamcharts.com.")

        rows = re.findall(r"<tr[^>]*>.*?</tr>", trending_block.group(0), re.DOTALL)
        games = []
        for row in rows:
            appid_match = re.search(r"/app/(\d+)", row)
            if not appid_match:
                continue
            app_id = int(appid_match.group(1))
            tds = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
            tds_clean = [
                re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", td)).strip()
                for td in tds
            ]
            if len(tds_clean) < 4:
                continue
            name = tds_clean[0]
            change_fmt = html.unescape(tds_clean[1])
            players_raw = tds_clean[3]
            try:
                players_int = int(players_raw.replace(",", ""))
                players_fmt = self._format_count(players_int)
            except ValueError:
                players_fmt = "--"

            games.append({
                "rank": len(games) + 1,
                "app_id": app_id,
                "name": name,
                "image": STEAM_CAPSULE_URL.format(appid=app_id),
                "change_24h_fmt": change_fmt,
                "current_players_fmt": players_fmt,
            })
            if len(games) >= count:
                break

        if not games:
            raise RuntimeError("No trending games found on steamcharts.com.")

        return games

    def _scrape_steamcharts_top(self, count):
        """Scrape the top games table from steamcharts.com/top."""
        try:
            session = get_http_session()
            resp = session.get(STEAMCHARTS_TOP_URL, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to fetch steamcharts top: {e}")
            raise RuntimeError("Unable to fetch Steam top games. Please try again later.")

        rows = re.findall(r"<tr[^>]*>.*?</tr>", resp.text, re.DOTALL)
        games = []
        for row in rows:
            appid_match = re.search(r"/app/(\d+)", row)
            if not appid_match:
                continue
            app_id = int(appid_match.group(1))
            tds = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
            tds_clean = [
                re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", td)).strip()
                for td in tds
            ]
            if len(tds_clean) < 3:
                continue
            name = tds_clean[1]
            try:
                players_int = int(tds_clean[2].replace(",", ""))
                players_fmt = self._format_count(players_int)
            except ValueError:
                players_fmt = "--"

            games.append({
                "rank": len(games) + 1,
                "app_id": app_id,
                "name": name,
                "image": STEAM_CAPSULE_URL.format(appid=app_id),
                "current_players_fmt": players_fmt,
            })
            if len(games) >= count:
                break

        if not games:
            raise RuntimeError("No top games found on steamcharts.com.")

        return games

    def _fetch_chart_data_batch(self, app_ids):
        """Fetch hourly chart data for multiple games in parallel."""
        results = {}

        def fetch_one(app_id):
            return app_id, self._fetch_chart_stats(app_id)

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(fetch_one, aid): aid for aid in app_ids}
            for future in concurrent.futures.as_completed(futures):
                try:
                    aid, stats = future.result()
                    results[aid] = stats
                except Exception as e:
                    logger.warning(f"Chart data fetch failed for an app: {e}")
                    results[futures[future]] = {}

        return results

    def _fetch_chart_stats(self, app_id):
        """Fetch hourly data from steamcharts and compute sparkline + 24h change."""
        try:
            session = get_http_session()
            url = STEAMCHARTS_CHART_URL.format(appid=app_id)
            resp = session.get(url, timeout=8)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning(f"Failed chart data for app {app_id}: {e}")
            return {}

        if not data:
            return {}

        now_ms = time.time() * 1000
        cutoff_48h_ms = now_ms - 48 * 3600 * 1000
        cutoff_24h_ms = now_ms - 24 * 3600 * 1000

        recent_48h = [p for p in data if p[0] >= cutoff_48h_ms]

        current_players = recent_48h[-1][1] if recent_48h else data[-1][1]

        change_24h = None
        if len(data) >= 2:
            target_24h = min(data, key=lambda p: abs(p[0] - cutoff_24h_ms))
            if target_24h[1] > 0:
                change_24h = ((current_players - target_24h[1]) / target_24h[1]) * 100

        sparkline_svg = self._generate_sparkline_svg(recent_48h)

        return {
            "current_players": current_players,
            "change_24h": change_24h,
            "sparkline_svg": sparkline_svg,
        }

    @staticmethod
    def _generate_sparkline_svg(data_points, width=120, height=30):
        """Generate inline SVG polyline string from [[timestamp_ms, count]] pairs."""
        if not data_points or len(data_points) < 2:
            return None

        counts = [p[1] for p in data_points]
        min_c, max_c = min(counts), max(counts)

        if max_c == min_c:
            y = height / 2
            return f'<polyline points="0,{y} {width},{y}" />'

        points = []
        for i, c in enumerate(counts):
            x = (i / (len(counts) - 1)) * width
            y = height - ((c - min_c) / (max_c - min_c)) * (height - 2) - 1
            points.append(f"{x:.1f},{y:.1f}")

        return '<polyline points="{}" />'.format(" ".join(points))

    @staticmethod
    def _format_count(count):
        """Format player count with thousands separator."""
        if count is None:
            return "--"
        return f"{count:,}"

    @staticmethod
    def _format_change(change):
        """Format 24h change as signed percentage."""
        if change is None:
            return "--"
        sign = "+" if change >= 0 else ""
        return f"{sign}{change:.1f}%"
