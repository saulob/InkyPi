"""
Movie of the Day Plugin for InkyPi
Fetches a random movie from TMDB and displays the poster, title, year, and rating.
For the API key, set `THE_MOVIE_DB={API_KEY}` in your .env file.
"""

from plugins.base_plugin.base_plugin import BasePlugin
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from utils.app_utils import get_font
from utils.http_client import get_http_session
import logging
from random import randint

logger = logging.getLogger(__name__)

TMDB_API_BASE = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"


class MovieOfTheDay(BasePlugin):
    def generate_settings_template(self):
        template_params = super().generate_settings_template()
        template_params['api_key'] = {
            "required": True,
            "service": "TMDB",
            "expected_key": "THE_MOVIE_DB"
        }
        template_params['style_settings'] = False
        return template_params

    def generate_image(self, settings, device_config):
        logger.info("=== Movie of the Day Plugin: Starting image generation ===")

        api_key = device_config.load_env_key("THE_MOVIE_DB")
        if not api_key:
            logger.error("TMDB API Key not configured")
            raise RuntimeError("TMDB API Key not configured. Set THE_MOVIE_DB in your .env file.")

        movie = self._fetch_random_movie(api_key)

        # Get target dimensions
        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]

        image = self._compose_layout(movie, dimensions)

        logger.info("=== Movie of the Day Plugin: Image generation complete ===")
        return image

    def _fetch_random_movie(self, api_key):
        """Fetch a random movie from TMDB discover endpoint."""
        session = get_http_session()

        # Pick a random page (TMDB allows up to 500 pages)
        random_page = randint(1, 100)

        response = session.get(
            f"{TMDB_API_BASE}/discover/movie",
            params={
                "api_key": api_key,
                "sort_by": "popularity.desc",
                "include_adult": "false",
                "vote_count.gte": "100",
                "page": random_page,
            },
        )

        if response.status_code != 200:
            logger.error(f"TMDB API error (status {response.status_code}): {response.text}")
            raise RuntimeError("Failed to retrieve movies from TMDB.")

        data = response.json()
        results = data.get("results", [])

        if not results:
            raise RuntimeError("No movies found from TMDB.")

        # Pick a random movie from the page results
        movie = results[randint(0, len(results) - 1)]
        logger.info(f"Selected movie: {movie.get('title')} ({movie.get('release_date', 'N/A')})")

        return movie

    def _compose_layout(self, movie, dimensions):
        """Compose a balanced card layout: poster left (~38%), text block right."""
        width, height = dimensions
        dim = min(width, height)

        title = movie.get("title", "Unknown Title")
        release_date = movie.get("release_date", "")
        year = release_date[:4] if release_date else "N/A"
        rating = movie.get("vote_average", 0)
        poster_path = movie.get("poster_path")

        # Create base image
        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)

        # --- Margins ---
        margin = int(dim * 0.04)

        # --- Poster: ~38% of total width, full height minus margin ---
        poster_area_w = int(width * 0.38)
        poster_max_w = poster_area_w - margin
        poster_max_h = height - margin * 2

        poster_img = None
        if poster_path:
            try:
                poster_url = f"{TMDB_IMAGE_BASE}{poster_path}"
                poster_img = self.image_loader.from_url(
                    poster_url, (poster_max_w, poster_max_h), timeout_ms=20000
                )
                if poster_img:
                    poster_img.thumbnail((poster_max_w, poster_max_h), Image.LANCZOS)
            except Exception as e:
                logger.warning(f"Failed to load poster: {e}")
                poster_img = None

        if poster_img:
            poster_x = (poster_area_w - poster_img.width) // 2
            poster_y = (height - poster_img.height) // 2
            image.paste(poster_img, (poster_x, poster_y))
        else:
            self._draw_poster_placeholder(draw, margin // 2, margin,
                                          poster_area_w - margin // 2, height - margin, dim)

        # --- Subtle vertical divider ---
        divider_x = poster_area_w
        div_margin_v = int(height * 0.1)
        draw.line(
            [(divider_x, div_margin_v), (divider_x, height - div_margin_v)],
            fill=(210, 210, 210), width=1
        )

        # --- Text block on the right ---
        gap_after_divider = int(dim * 0.035)
        text_x = divider_x + gap_after_divider
        text_max_w = width - text_x - margin

        # Font sizes scaled from dim
        header_font = get_font("Jost", int(dim * 0.032)) or ImageFont.load_default()
        title_font = get_font("Jost", int(dim * 0.082), "bold") or ImageFont.load_default()
        year_font = get_font("Jost", int(dim * 0.048)) or ImageFont.load_default()

        # Measure heights for vertical centering
        title_lines = self._wrap_text(draw, title, text_max_w, title_font, max_lines=2)
        header_h = int(dim * 0.032 * 1.5)
        title_line_h = int(dim * 0.082 * 1.2)
        title_block_h = len(title_lines) * title_line_h
        year_h = int(dim * 0.048 * 1.4)
        score_panel_h = int(dim * 0.22)  # label + score line + stars row
        gap_s = int(dim * 0.018)
        gap_m = int(dim * 0.030)

        total_h = header_h + gap_s + title_block_h + gap_s + year_h + gap_m + score_panel_h
        cur_y = max(margin, (height - total_h) // 2)

        # Header label
        draw.text((text_x, cur_y), "Movie of the Day", font=header_font, fill=(160, 160, 160))
        cur_y += header_h + gap_s

        # Title
        for line in title_lines:
            draw.text((text_x, cur_y), line, font=title_font, fill=(10, 10, 10))
            cur_y += title_line_h
        cur_y += gap_s

        # Year
        draw.text((text_x, cur_y), year, font=year_font, fill=(130, 130, 130))
        cur_y += year_h + gap_m

        # Score panel
        self._draw_score_panel(draw, text_x, cur_y, rating, dim)

        return image

    def _draw_score_panel(self, draw, x, y, rating, dim):
        """Draw a compact score panel: User Score label, score number, and a 5-star row."""
        import math

        label_font = get_font("Jost", int(dim * 0.030)) or ImageFont.load_default()
        score_font = get_font("Jost", int(dim * 0.065), "bold") or ImageFont.load_default()
        gap = int(dim * 0.012)

        # "User Score" label
        draw.text((x, y), "User Score", font=label_font, fill=(150, 150, 150))
        y += int(dim * 0.030 * 1.5) + gap

        # Score number: N.N/10
        if rating:
            score_text = f"{rating:.1f}/10"
        else:
            score_text = "N/A"
        draw.text((x, y), score_text, font=score_font, fill=(20, 20, 20))
        y += int(dim * 0.065 * 1.3) + gap

        # 5-star row drawn as polygons
        if rating:
            star_size = int(dim * 0.035)
            star_gap = int(star_size * 0.35)
            filled_count = rating / 2.0  # 0-5 scale
            for i in range(5):
                sx = x + i * (star_size + star_gap)
                sy = y
                if i < int(filled_count):
                    self._draw_star(draw, sx, sy, star_size, fill=(50, 50, 50))
                elif i < filled_count:
                    # half-filled: draw outline, then filled on top clipped to left half
                    self._draw_star(draw, sx, sy, star_size, fill=None, outline=(50, 50, 50))
                    self._draw_star(draw, sx, sy, star_size, fill=(50, 50, 50))
                else:
                    self._draw_star(draw, sx, sy, star_size, fill=None, outline=(160, 160, 160))

    @staticmethod
    def _draw_star(draw, x, y, size, fill=None, outline=None):
        """Draw a 5-point star polygon at (x, y) with given size."""
        import math
        cx = x + size // 2
        cy = y + size // 2
        outer_r = size // 2
        inner_r = int(outer_r * 0.38)
        points = []
        for i in range(10):
            r = outer_r if i % 2 == 0 else inner_r
            angle = math.radians(-90 + i * 36)
            points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
        if fill:
            draw.polygon(points, fill=fill, outline=outline or fill)
        elif outline:
            draw.polygon(points, outline=outline, width=1)

    def _draw_poster_placeholder(self, draw, x0, y0, x1, y1, dim):
        """Draw a placeholder rectangle when poster is unavailable."""
        draw.rounded_rectangle([x0, y0, x1, y1], radius=int(dim * 0.02),
                               outline=(200, 200, 200), width=2)
        cx = (x0 + x1) // 2
        cy = (y0 + y1) // 2
        label_font = get_font("Jost", int(dim * 0.035)) or ImageFont.load_default()
        draw.text((cx, cy), "No Poster", font=label_font, fill=(180, 180, 180), anchor="mm")

    def _wrap_text(self, draw, text, max_width, font, max_lines=2):
        """Wrap text into lines, truncating with ellipsis if over max_lines."""
        words = text.split()
        lines = []
        current_line = ""

        for word in words:
            test_line = f"{current_line} {word}".strip()
            bbox = draw.textbbox((0, 0), test_line, font=font)
            if bbox[2] - bbox[0] <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
                if len(lines) >= max_lines:
                    break

        if current_line and len(lines) < max_lines:
            lines.append(current_line)

        # Truncate last line with ellipsis if we ran out of space
        if len(lines) >= max_lines and words:
            last = lines[max_lines - 1]
            remaining_words = words[sum(len(l.split()) for l in lines):]
            if remaining_words:
                while last:
                    candidate = last + "…"
                    bbox = draw.textbbox((0, 0), candidate, font=font)
                    if bbox[2] - bbox[0] <= max_width:
                        lines[max_lines - 1] = candidate
                        break
                    last = last.rsplit(" ", 1)[0] if " " in last else last[:-1]
            lines = lines[:max_lines]

        return lines if lines else [text[:20] + "…"]
