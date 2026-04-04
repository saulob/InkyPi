"""
Movie of the Day Plugin for InkyPi
Fetches a random movie from TMDB and displays the poster, title, year, and rating.
For the API key, set `THE_MOVIE_DB={API_KEY}` in your .env file.
"""

from plugins.base_plugin.base_plugin import BasePlugin
from PIL import Image, ImageDraw, ImageFont
from utils.app_utils import get_font
from utils.http_client import get_http_session
import logging
import math
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
        """Compose a polished movie card with a compact score panel."""
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

        margin = max(14, int(dim * 0.038))
        poster_area_w = int(width * 0.37)
        poster_inner_gap = max(6, int(dim * 0.01))
        poster_left = margin // 2
        poster_right = poster_area_w - poster_inner_gap
        poster_max_w = poster_right - poster_left
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
            poster_x = poster_left + (poster_max_w - poster_img.width) // 2
            poster_y = (height - poster_img.height) // 2
            image.paste(poster_img, (poster_x, poster_y))
        else:
            self._draw_poster_placeholder(
                draw, poster_left, margin, poster_right, height - margin, dim
            )

        divider_x = poster_right + poster_inner_gap
        draw.line(
            [(divider_x, margin), (divider_x, height - margin)],
            fill=(185, 185, 185), width=2
        )

        gap_after_divider = int(dim * 0.032)
        text_x = divider_x + gap_after_divider
        text_max_w = width - text_x - margin

        header_font = get_font("Jost", int(dim * 0.034)) or ImageFont.load_default()
        title_font = get_font("Jost", int(dim * 0.086), "bold") or ImageFont.load_default()
        year_font = get_font("Jost", int(dim * 0.05)) or ImageFont.load_default()

        title_lines = self._wrap_text(draw, title, text_max_w, title_font, max_lines=2)
        _, header_h = self._measure_text(draw, "Movie of the Day", header_font)
        _, title_text_h = self._measure_text(draw, "Ag", title_font)
        _, year_h = self._measure_text(draw, year, year_font)
        title_line_h = title_text_h + int(dim * 0.006)
        title_block_h = len(title_lines) * title_line_h

        score_metrics = self._get_score_panel_metrics(draw, rating, dim)
        score_panel_w = min(text_max_w, score_metrics["panel_min_w"])
        score_panel_h = score_metrics["panel_h"]

        gap_xs = int(dim * 0.006)
        gap_s  = int(dim * 0.010)
        gap_m  = int(dim * 0.026)  # larger gap before score card to prevent overlap

        total_h = header_h + gap_xs + title_block_h + gap_s + year_h + gap_m + score_panel_h
        # Bias upward: start at 40% of available slack rather than 50% (center)
        slack = max(0, height - total_h)
        cur_y = max(margin, int(slack * 0.38))

        draw.text((text_x, cur_y), "Movie of the Day", font=header_font, fill=(155, 155, 155))
        cur_y += header_h + gap_xs

        for line in title_lines:
            draw.text((text_x, cur_y), line, font=title_font, fill=(10, 10, 10))
            cur_y += title_line_h
        cur_y += gap_s

        draw.text((text_x, cur_y), year, font=year_font, fill=(125, 125, 125))
        cur_y += year_h + gap_m

        # Pass text_x as the anchor — panel content aligns with title/year
        self._draw_score_panel(draw, text_x, cur_y, score_panel_w, rating, dim, score_metrics)

        return image

    def _draw_score_panel(self, draw, x, y, panel_w, rating, dim, metrics=None):
        """Draw the score card. x is the content left edge (aligns with title/year)."""
        if metrics is None:
            metrics = self._get_score_panel_metrics(draw, rating, dim)

        label_font = metrics["label_font"]
        score_font = metrics["score_font"]
        label_text = metrics["label_text"]
        score_text = metrics["score_text"]
        label_h    = metrics["label_h"]
        score_h    = metrics["score_h"]
        pad_x      = metrics["pad_x"]
        pad_y      = metrics["pad_y"]
        inner_gap  = metrics["inner_gap"]
        star_size  = metrics["star_size"]
        star_gap   = metrics["star_gap"]
        panel_h    = metrics["panel_h"]

        # Card rect bleeds left by pad_x so that content (inner_x=x) lines up
        # with title and year which are also drawn at x.
        card_x0 = x - pad_x
        card_x1 = card_x0 + panel_w
        radius = int(dim * 0.018)
        draw.rounded_rectangle(
            [card_x0, y, card_x1, y + panel_h],
            radius=radius,
            fill=(246, 246, 246),
            outline=(208, 208, 208),
            width=1,
        )

        inner_x = x          # perfectly aligned with title / year
        cur_y   = y + pad_y

        # "User Score" label
        draw.text((inner_x, cur_y), label_text, font=label_font, fill=(150, 150, 150))
        cur_y += label_h + inner_gap

        # Bold numeric rating
        draw.text((inner_x, cur_y), score_text, font=score_font, fill=(12, 12, 12))

        # Stars aligned to same x as rating number
        if rating:
            stars_y = cur_y + score_h + inner_gap
            filled_stars = max(0, min(5, round(rating / 2)))
            for index in range(5):
                star_x = inner_x + index * (star_size + star_gap)
                if index < filled_stars:
                    self._draw_star(
                        draw, star_x, stars_y, star_size,
                        fill=(18, 18, 18), outline=(18, 18, 18), outline_width=1,
                    )
                else:
                    self._draw_star(
                        draw, star_x, stars_y, star_size,
                        fill=(220, 220, 220), outline=(145, 145, 145), outline_width=1,
                    )

    def _get_score_panel_metrics(self, draw, rating, dim):
        """Measure score panel pieces so the content block can be centered accurately."""
        label_font = get_font("Jost", int(dim * 0.034)) or ImageFont.load_default()
        score_font = get_font("Jost", int(dim * 0.095), "bold") or ImageFont.load_default()

        label_text = "User Score"
        score_text = f"{rating:.1f}/10" if rating else "N/A"
        label_w, label_h = self._measure_text(draw, label_text, label_font)
        score_w, score_h = self._measure_text(draw, score_text, score_font)

        # Fixed comfortable star size
        star_size = int(dim * 0.048)
        star_gap  = max(4, int(dim * 0.009))

        pad_x     = int(dim * 0.022)
        pad_y     = int(dim * 0.016)
        inner_gap = int(dim * 0.009)

        star_row_w = 5 * star_size + 4 * star_gap if rating else 0
        content_w  = max(score_w, label_w, star_row_w)
        panel_min_w = content_w + pad_x * 2

        panel_h = pad_y * 2 + label_h + inner_gap + score_h
        if rating:
            panel_h += inner_gap + star_size

        return {
            "label_font": label_font,
            "score_font": score_font,
            "label_text": label_text,
            "score_text": score_text,
            "label_w": label_w,
            "label_h": label_h,
            "score_w": score_w,
            "score_h": score_h,
            "pad_x": pad_x,
            "pad_y": pad_y,
            "inner_gap": inner_gap,
            "star_size": star_size,
            "star_gap": star_gap,
            "panel_min_w": panel_min_w,
            "panel_h": panel_h,
        }

    def _get_star_row_layout(self, target_width, dim):
        """Kept for compatibility; star layout is now computed in _get_score_panel_metrics."""
        star_size = int(dim * 0.04)
        star_gap  = max(3, int(dim * 0.008))
        return star_size, star_gap

    @staticmethod
    def _draw_star(draw, x, y, size, fill=None, outline=None, outline_width=1):
        """Draw a 5-point star polygon at (x, y) with given size."""
        cx = x + size // 2
        cy = y + size // 2
        outer_r = size // 2
        inner_r = int(outer_r * 0.38)
        points = []
        for i in range(10):
            r = outer_r if i % 2 == 0 else inner_r
            angle = math.radians(-90 + i * 36)
            points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
        draw.polygon(
            points,
            fill=fill,
            outline=outline,
            width=outline_width,
        )

    def _draw_poster_placeholder(self, draw, x0, y0, x1, y1, dim):
        """Draw a placeholder rectangle when poster is unavailable."""
        draw.rounded_rectangle([x0, y0, x1, y1], radius=int(dim * 0.02),
                               outline=(200, 200, 200), width=2)
        cx = (x0 + x1) // 2
        cy = (y0 + y1) // 2
        label_font = get_font("Jost", int(dim * 0.035)) or ImageFont.load_default()
        draw.text((cx, cy), "No Poster", font=label_font, fill=(180, 180, 180), anchor="mm")

    def _wrap_text(self, draw, text, max_width, font, max_lines=2):
        """Word-wrap text, truncating at a word boundary with ellipsis on the last line."""
        words = text.split()
        if not words:
            return [""]

        lines = []
        i = 0
        while i < len(words):
            line_words = []
            while i < len(words):
                test_line = " ".join(line_words + [words[i]])
                bbox = draw.textbbox((0, 0), test_line, font=font)
                if bbox[2] - bbox[0] <= max_width:
                    line_words.append(words[i])
                    i += 1
                else:
                    break

            if not line_words:
                # Single word too long to fit — force it onto a line
                line_words = [words[i]]
                i += 1

            is_last_allowed = len(lines) >= max_lines - 1
            has_more_words = i < len(words)

            if is_last_allowed and has_more_words:
                # Truncate this line at a word boundary with ellipsis
                while line_words:
                    candidate = " ".join(line_words) + "…"
                    bbox = draw.textbbox((0, 0), candidate, font=font)
                    if bbox[2] - bbox[0] <= max_width:
                        lines.append(candidate)
                        return lines
                    line_words.pop()
                lines.append("…")
                return lines

            lines.append(" ".join(line_words))
            if len(lines) >= max_lines:
                break

        return lines if lines else [text[:20] + "…"]

    @staticmethod
    def _measure_text(draw, text, font):
        """Return (width, advance_h) where advance_h is bbox[3]: distance from the
        draw-origin to the visual bottom of the text. This is the correct amount
        to advance cur_y so the next element starts below the rendered pixels."""
        bbox = draw.textbbox((0, 0), text or " ", font=font)
        return bbox[2] - bbox[0], bbox[3]
