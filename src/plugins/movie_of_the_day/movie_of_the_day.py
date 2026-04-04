"""
Movie of the Day Plugin for InkyPi
Fetches a random movie from TMDB and displays the poster, title, year, and rating.
For the API key, set `THE_MOVIE_DB={API_KEY}` in your .env file.
"""

from plugins.base_plugin.base_plugin import BasePlugin
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
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
        """Compose the e-paper layout with poster on one side and text on the other."""
        width, height = dimensions

        title = movie.get("title", "Unknown Title")
        release_date = movie.get("release_date", "")
        year = release_date[:4] if release_date else "N/A"
        rating = movie.get("vote_average", 0)
        rating_str = f"{rating:.1f}/10" if rating else "N/A"
        poster_path = movie.get("poster_path")

        # Create base image (white background for e-paper)
        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)

        # Layout: poster on the left, text on the right
        poster_width = int(width * 0.35)
        text_x = poster_width + int(width * 0.04)
        text_width = width - text_x - int(width * 0.04)
        padding = int(height * 0.08)

        # Load and place poster
        if poster_path:
            try:
                poster_url = f"{TMDB_IMAGE_BASE}{poster_path}"
                poster_img = self.image_loader.from_url(
                    poster_url, (poster_width, height), timeout_ms=20000
                )
                if poster_img:
                    # Resize poster to fit the left column keeping aspect ratio
                    poster_img.thumbnail(
                        (poster_width - padding, height - padding * 2),
                        Image.LANCZOS,
                    )
                    poster_x = (poster_width - poster_img.width) // 2
                    poster_y = (height - poster_img.height) // 2
                    image.paste(poster_img, (poster_x, poster_y))
            except Exception as e:
                logger.warning(f"Failed to load poster: {e}")
                self._draw_poster_placeholder(draw, poster_width, height, padding)
        else:
            self._draw_poster_placeholder(draw, poster_width, height, padding)

        # Load fonts
        title_font = self._load_font(int(height * 0.07))
        detail_font = self._load_font(int(height * 0.05))

        # Draw title (with word wrapping)
        title_y = padding
        title_y = self._draw_wrapped_text(
            draw, title, text_x, title_y, text_width, title_font, fill="black"
        )

        # Draw year
        title_y += int(height * 0.04)
        draw.text((text_x, title_y), year, font=detail_font, fill="gray")
        title_y += int(height * 0.07)

        # Draw rating with star
        draw.text((text_x, title_y), f"★ {rating_str}", font=detail_font, fill="black")

        return image

    def _draw_poster_placeholder(self, draw, poster_width, height, padding):
        """Draw a placeholder rectangle when poster is unavailable."""
        x0 = padding
        y0 = padding
        x1 = poster_width - padding
        y1 = height - padding
        draw.rectangle([x0, y0, x1, y1], outline="gray", width=2)
        # Draw a small film icon placeholder
        cx = (x0 + x1) // 2
        cy = (y0 + y1) // 2
        placeholder_font = self._load_font(int(height * 0.04))
        draw.text((cx, cy), "No Poster", font=placeholder_font, fill="gray", anchor="mm")

    def _load_font(self, size):
        """Load a font, falling back to default if needed."""
        import os
        fonts_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "static", "fonts"
        )

        # Try available fonts from the project's fonts directory
        for font_name in ["Jost-SemiBold.ttf", "Jost.ttf", "Napoli.ttf"]:
            font_path = os.path.join(fonts_dir, font_name)
            if os.path.exists(font_path):
                try:
                    return ImageFont.truetype(font_path, size)
                except Exception:
                    continue

        return ImageFont.load_default()

    def _draw_wrapped_text(self, draw, text, x, y, max_width, font, fill="black"):
        """Draw text with word wrapping. Returns the y position after the last line."""
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

        if current_line:
            lines.append(current_line)

        line_height = font.size + int(font.size * 0.3)
        for line in lines:
            draw.text((x, y), line, font=font, fill=fill)
            y += line_height

        return y
