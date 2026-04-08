"""
Movie of the Day Plugin for InkyPi
Fetches a random movie from TMDB and displays the poster, title, year, and rating.
For the API key, set `THE_MOVIE_DB={API_KEY}` in your .env file.
"""

import logging
import math
import os
from random import randint

from dotenv import dotenv_values
from PIL import Image, ImageDraw, ImageFont

from plugins.base_plugin.base_plugin import BasePlugin
from utils.app_utils import get_font
from utils.http_client import get_http_session

logger = logging.getLogger(__name__)

TMDB_API_BASE = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"

LETTERBOXD_BG = (20, 24, 28)
LETTERBOXD_TEXT = (255, 255, 255)
LETTERBOXD_MUTED = (131, 153, 175)
LETTERBOXD_DIVIDER = (68, 85, 102)
LETTERBOXD_BAR = (85, 102, 119)
LETTERBOXD_BAR_PEAK = (85, 102, 119)
LETTERBOXD_STAR_FILLED = (255, 255, 255)
LETTERBOXD_STAR_EMPTY_FILL = (20, 25, 80)
LETTERBOXD_STAR_EMPTY_OUTLINE = (68, 85, 102)

DEFAULT_LANGUAGE = "en"

TMDB_LANGUAGE_MAP = {
    "nl": "nl-NL",
    "en": "en-US",
    "fr": "fr-FR",
    "de": "de-DE",
    "id": "id-ID",
    "it": "it-IT",
    "pt-br": "pt-BR",
    "pt-pt": "pt-PT",
    "es": "es-ES",
}

TRANSLATIONS = {
    "en": {
        "movie_of_the_day": "Movie of the Day",
        "user_score": "User Score",
        "ratings": "RATINGS",
        "fans": "FANS",
        "thousand_suffix": "K",
        "million_suffix": "M",
    },
    "nl": {
        "movie_of_the_day": "Film van de Dag",
        "user_score": "Gebruikersscore",
        "ratings": "BEOORDELINGEN",
        "fans": "FANS",
        "thousand_suffix": "K",
        "million_suffix": "M",
    },
    "fr": {
        "movie_of_the_day": "Film du Jour",
        "user_score": "Score des utilisateurs",
        "ratings": "NOTES",
        "fans": "FANS",
        "thousand_suffix": "K",
        "million_suffix": "M",
    },
    "de": {
        "movie_of_the_day": "Film des Tages",
        "user_score": "Nutzerbewertung",
        "ratings": "BEWERTUNGEN",
        "fans": "FANS",
        "thousand_suffix": "K",
        "million_suffix": "M",
    },
    "id": {
        "movie_of_the_day": "Film Hari Ini",
        "user_score": "Skor Pengguna",
        "ratings": "PERINGKAT",
        "fans": "PENGGEMAR",
        "thousand_suffix": "RB",
        "million_suffix": "JT",
    },
    "it": {
        "movie_of_the_day": "Film del giorno",
        "user_score": "Punteggio utenti",
        "ratings": "VALUTAZIONI",
        "fans": "FANS",
        "thousand_suffix": "K",
        "million_suffix": "M",
    },
    "pt-br": {
        "movie_of_the_day": "Filme do Dia",
        "user_score": "Pontuação dos Usuários",
        "ratings": "AVALIAÇÕES",
        "fans": "FÃS",
        "thousand_suffix": " mil",
        "million_suffix": "M",
    },
    "pt-pt": {
        "movie_of_the_day": "Filme do Dia",
        "user_score": "Pontuação dos Utilizadores",
        "ratings": "AVALIAÇÕES",
        "fans": "FÃS",
        "thousand_suffix": " mil",
        "million_suffix": "M",
    },
    "es": {
        "movie_of_the_day": "Película del Día",
        "user_score": "Puntuación de usuarios",
        "ratings": "VALORACIONES",
        "fans": "FANS",
        "thousand_suffix": "K",
        "million_suffix": "M",
    },
}


class MovieOfTheDay(BasePlugin):
    def generate_settings_template(self):
        template_params = super().generate_settings_template()
        env_values = dotenv_values()
        template_params["api_key"] = {
            "required": True,
            "service": "TMDB",
            "expected_key": "THE_MOVIE_DB",
        }
        template_params["api_key_configured"] = bool(
            os.getenv("THE_MOVIE_DB") or env_values.get("THE_MOVIE_DB")
        )
        template_params["style_settings"] = False
        return template_params

    def generate_image(self, settings, device_config):
        logger.info("=== Movie of the Day Plugin: Starting image generation ===")

        api_key = device_config.load_env_key("THE_MOVIE_DB")
        if not api_key:
            logger.error("TMDB API Key not configured")
            raise RuntimeError("TMDB API Key not configured. Set THE_MOVIE_DB in your .env file.")

        language = self._resolve_language(settings)
        tmdb_language = self._get_tmdb_language(language)
        movie = self._fetch_random_movie(api_key, tmdb_language)

        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]

        labels = self._get_labels(language)

        bg_color = self._hex_to_rgb(settings.get("backgroundColor", ""), LETTERBOXD_BG)
        text_color = self._hex_to_rgb(settings.get("textColor", ""), LETTERBOXD_TEXT)
        secondary_text_color = self._hex_to_rgb(settings.get("secondaryTextColor", ""), LETTERBOXD_MUTED)
        bar_color = self._hex_to_rgb(settings.get("barColor", ""), LETTERBOXD_BAR)

        image = self._compose_layout(
            movie,
            dimensions,
            labels,
            bg_color=bg_color,
            text_color=text_color,
            secondary_text_color=secondary_text_color,
            bar_color=bar_color,
        )

        logger.info("=== Movie of the Day Plugin: Image generation complete ===")
        return image

    def _fetch_random_movie(self, api_key, tmdb_language):
        """Fetch a random movie from TMDB discover endpoint."""
        session = get_http_session()
        random_page = randint(1, 100)

        response = session.get(
            f"{TMDB_API_BASE}/discover/movie",
            params={
                "api_key": api_key,
                "sort_by": "popularity.desc",
                "include_adult": "false",
                "vote_count.gte": "100",
                "page": random_page,
                "language": tmdb_language,
            },
        )

        if response.status_code != 200:
            logger.error(f"TMDB API error (status {response.status_code}): {response.text}")
            raise RuntimeError("Failed to retrieve movies from TMDB.")

        data = response.json()
        results = data.get("results", [])
        if not results:
            raise RuntimeError("No movies found from TMDB.")

        movie = results[randint(0, len(results) - 1)]
        logger.info(f"Selected movie: {movie.get('title')} ({movie.get('release_date', 'N/A')})")
        return self._fetch_movie_details(session, api_key, movie, tmdb_language)

    def _fetch_movie_details(self, session, api_key, movie, tmdb_language):
        """Fetch detail payload so future TMDB distribution fields can be used when available."""
        movie_id = movie.get("id")
        if not movie_id:
            return movie

        response = session.get(
            f"{TMDB_API_BASE}/movie/{movie_id}",
            params={"api_key": api_key, "language": tmdb_language},
        )
        if response.status_code != 200:
            logger.warning(
                "TMDB movie detail lookup failed for %s with status %s",
                movie_id,
                response.status_code,
            )
            return movie

        details = response.json()
        if not isinstance(details, dict):
            return movie

        merged_movie = dict(movie)
        merged_movie.update(details)
        return merged_movie

    def _build_rating_distribution(self, movie):
        """Return rating bucket counts from TMDB payload when available, otherwise approximate."""
        direct_distribution = self._extract_rating_distribution(movie)
        if direct_distribution:
            return self._to_star_distribution(direct_distribution)

        rating = movie.get("vote_average") or 0
        vote_count = movie.get("vote_count") or 0
        if rating <= 0 or vote_count <= 0:
            return None

        simulated_distribution = self._simulate_rating_distribution(rating, vote_count, bucket_count=10)
        return self._to_star_distribution(simulated_distribution)

    def _extract_rating_distribution(self, movie):
        """Best-effort parsing for future TMDB distribution-style fields."""
        candidate_keys = (
            "rating_distribution",
            "vote_distribution",
            "rating_counts",
            "ratings_distribution",
        )

        for key in candidate_keys:
            normalized = self._normalize_distribution(movie.get(key))
            if normalized:
                return normalized

        return None

    def _normalize_distribution(self, raw_distribution):
        """Normalize supported distribution shapes into a compact list of bucket counts."""
        if isinstance(raw_distribution, (list, tuple)):
            values = [
                max(0, int(value))
                for value in raw_distribution
                if isinstance(value, (int, float))
            ]
            if len(values) in (5, 10) and any(values):
                return values
            return None

        if not isinstance(raw_distribution, dict):
            return None

        buckets = [0] * 10
        has_values = False
        for score, count in raw_distribution.items():
            if not isinstance(count, (int, float)) or count <= 0:
                continue

            try:
                numeric_score = float(score)
            except (TypeError, ValueError):
                continue

            if numeric_score <= 5:
                numeric_score *= 2

            bucket_index = min(9, max(0, int(math.ceil(numeric_score)) - 1))
            buckets[bucket_index] += int(count)
            has_values = True

        if has_values and any(buckets):
            return buckets
        return None

    def _to_star_distribution(self, distribution):
        """Collapse distributions into five buckets mapped to 1-5 stars."""
        if not distribution:
            return None

        if len(distribution) == 5:
            return distribution if any(distribution) else None

        if len(distribution) != 10:
            return None

        star_distribution = [
            distribution[0] + distribution[1],
            distribution[2] + distribution[3],
            distribution[4] + distribution[5],
            distribution[6] + distribution[7],
            distribution[8] + distribution[9],
        ]
        return star_distribution if any(star_distribution) else None

    def _simulate_rating_distribution(self, rating, vote_count, bucket_count=10):
        """Approximate a histogram using the average score and total votes."""
        vote_count = int(vote_count)
        if vote_count <= 0:
            return None

        mean = max(0.5, min(float(bucket_count) - 0.5, float(rating)))
        sigma = 1.45 if vote_count < 5000 else 1.25
        centers = [index + 0.5 for index in range(bucket_count)]
        weights = [
            math.exp(-((center - mean) ** 2) / (2 * (sigma ** 2)))
            for center in centers
        ]
        total_weight = sum(weights)
        if total_weight <= 0:
            return None

        scaled = [(weight / total_weight) * vote_count for weight in weights]
        counts = [int(value) for value in scaled]
        remainder = vote_count - sum(counts)

        fractional_indices = sorted(
            range(bucket_count),
            key=lambda index: scaled[index] - counts[index],
            reverse=True,
        )
        for index in fractional_indices[:remainder]:
            counts[index] += 1

        return counts if any(counts) else None

    @staticmethod
    def _resolve_language(settings):
        language = str(settings.get("language", DEFAULT_LANGUAGE)).strip().lower()
        if language == "pt":
            language = "pt-br"
        return language if language in TRANSLATIONS else DEFAULT_LANGUAGE

    @staticmethod
    def _get_labels(language):
        return TRANSLATIONS.get(language, TRANSLATIONS[DEFAULT_LANGUAGE])

    @staticmethod
    def _get_tmdb_language(language):
        return TMDB_LANGUAGE_MAP.get(language, TMDB_LANGUAGE_MAP[DEFAULT_LANGUAGE])

    @staticmethod
    def _resolve_movie_title(movie):
        translated_title = str(movie.get("title") or "").strip()
        original_title = str(movie.get("original_title") or "").strip()

        if not translated_title:
            return original_title or "Unknown Title"

        if translated_title == original_title and original_title:
            return original_title

        return translated_title

    @staticmethod
    def _format_vote_count(vote_count, labels):
        """Format large vote counts in a compact UI-friendly style."""
        thousand_suffix = labels.get("thousand_suffix", "K")
        million_suffix = labels.get("million_suffix", "M")

        if vote_count >= 1_000_000:
            value = f"{vote_count / 1_000_000:.1f}".rstrip("0").rstrip(".")
            return f"{value}{million_suffix}"
        if vote_count >= 10_000:
            return f"{vote_count // 1000}{thousand_suffix}"
        if vote_count >= 1_000:
            value = f"{vote_count / 1000:.1f}".rstrip("0").rstrip(".")
            return f"{value}{thousand_suffix}"
        return str(vote_count)

    @staticmethod
    def _hex_to_rgb(hex_color, default):
        """Convert a #rrggbb hex string to an RGB tuple, returning default on failure."""
        try:
            h = str(hex_color).lstrip("#")
            if len(h) == 6:
                return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
        except (ValueError, AttributeError):
            pass
        return default

    def _compose_layout(
        self,
        movie,
        dimensions,
        labels,
        bg_color=LETTERBOXD_BG,
        text_color=LETTERBOXD_TEXT,
        secondary_text_color=LETTERBOXD_MUTED,
        bar_color=LETTERBOXD_BAR,
    ):
        """Compose a dark movie card with compact score and ratings sections."""
        width, height = dimensions
        dim = min(width, height)

        title = self._resolve_movie_title(movie)
        release_date = movie.get("release_date", "")
        year = release_date[:4] if release_date else "N/A"
        rating = movie.get("vote_average", 0)
        vote_count = movie.get("vote_count", 0)
        poster_path = movie.get("poster_path")
        distribution = self._build_rating_distribution(movie)

        image = Image.new("RGB", (width, height), bg_color)
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
            except Exception as exc:
                logger.warning(f"Failed to load poster: {exc}")
                poster_img = None

        if poster_img:
            poster_x = poster_left + (poster_max_w - poster_img.width) // 2
            poster_y = (height - poster_img.height) // 2
            corner_radius = max(10, int(dim * 0.02))
            poster_rgba = poster_img.convert("RGBA")
            rounded_mask = Image.new("L", poster_rgba.size, 0)
            rounded_draw = ImageDraw.Draw(rounded_mask)
            rounded_draw.rounded_rectangle(
                [(0, 0), (poster_rgba.width - 1, poster_rgba.height - 1)],
                radius=corner_radius,
                fill=255,
            )
            image.paste(poster_rgba, (poster_x, poster_y), rounded_mask)
        else:
            self._draw_poster_placeholder(
                draw, poster_left, margin, poster_right, height - margin, dim
            )

        divider_x = poster_right + poster_inner_gap
        draw.line(
            [(divider_x, margin), (divider_x, height - margin)],
            fill=LETTERBOXD_DIVIDER,
            width=2,
        )

        gap_after_divider = int(dim * 0.032)
        text_x = divider_x + gap_after_divider
        text_max_w = width - text_x - margin

        header_font = get_font("Jost", int(dim * 0.0462)) or ImageFont.load_default()
        title_font = get_font("Jost", int(dim * 0.086), "bold") or ImageFont.load_default()
        year_font = get_font("Jost", int(dim * 0.0525)) or ImageFont.load_default()

        title_lines = self._wrap_text(draw, title, text_max_w, title_font, max_lines=3)
        title_line_count = len(title_lines)
        _, header_h = self._measure_text(draw, labels["movie_of_the_day"], header_font)
        _, title_text_h = self._measure_text(draw, "Ag", title_font)
        _, year_h = self._measure_text(draw, year, year_font)
        title_line_h = title_text_h + int(dim * 0.006)
        title_block_h = len(title_lines) * title_line_h

        gap_xs = int(dim * 0.006)
        gap_s = int(dim * 0.010)
        gap_m = int(dim * 0.026)

        top_content_h = header_h + gap_xs + title_block_h + gap_s + year_h + gap_m
        available_score_h = max(0, height - margin * 2 - top_content_h)

        score_panel_w = text_max_w
        score_metrics = self._get_score_panel_metrics(
            draw,
            rating,
            vote_count,
            distribution,
            dim,
            score_panel_w,
            available_score_h,
            title_line_count,
            labels,
        )
        score_panel_h = score_metrics["panel_h"]
        score_panel_h = max(score_panel_h, available_score_h)
        score_metrics["panel_h"] = score_panel_h

        total_h = top_content_h + score_panel_h
        # Top-align the right column with the poster area.
        cur_y = margin

        draw.text((text_x, cur_y), labels["movie_of_the_day"], font=header_font, fill=secondary_text_color)
        cur_y += header_h + gap_xs

        for line in title_lines:
            draw.text((text_x, cur_y), line, font=title_font, fill=text_color)
            cur_y += title_line_h
        cur_y += gap_s

        draw.text((text_x, cur_y), year, font=year_font, fill=secondary_text_color)
        cur_y += year_h + gap_m

        self._draw_score_panel(
            draw,
            text_x,
            cur_y,
            score_panel_w,
            rating,
            vote_count,
            distribution,
            dim,
            score_metrics,
            labels,
            text_color=text_color,
            secondary_text_color=secondary_text_color,
            bar_color=bar_color,
        )

        return image

    def _draw_score_panel(
        self,
        draw,
        x,
        y,
        panel_w,
        rating,
        vote_count,
        distribution,
        dim,
        metrics=None,
        labels=None,
        text_color=LETTERBOXD_TEXT,
        secondary_text_color=LETTERBOXD_MUTED,
        bar_color=LETTERBOXD_BAR,
    ):
        """Draw the score area and optional rating histogram."""
        labels = labels or TRANSLATIONS[DEFAULT_LANGUAGE]

        if metrics is None:
            metrics = self._get_score_panel_metrics(
                draw,
                rating,
                vote_count,
                distribution,
                dim,
                panel_w,
                labels=labels,
            )

        label_font = metrics["label_font"]
        score_font = metrics["score_font"]
        chart_title_font = metrics["chart_title_font"]
        chart_count_font = metrics["chart_count_font"]
        label_text = metrics["label_text"]
        score_text = metrics["score_text"]
        count_text = metrics["count_text"]
        label_h = metrics["label_h"]
        score_h = metrics["score_h"]
        chart_title_h = metrics["chart_title_h"]
        pad_y = metrics["pad_y"]
        inner_gap = metrics["inner_gap"]
        section_gap = metrics["section_gap"]
        header_gap = metrics["header_gap"]
        chart_gap = metrics["chart_gap"]
        chart_h = metrics["chart_h"]
        panel_h = metrics["panel_h"]
        score_block_h = metrics["score_block_h"]
        chart_block_h = metrics["chart_block_h"]

        inner_x = x
        cur_y = y + pad_y

        draw.text((inner_x, cur_y), label_text, font=label_font, fill=secondary_text_color)
        cur_y += label_h + inner_gap

        draw.text((inner_x, cur_y), score_text, font=score_font, fill=text_color)

        if rating:
            star_font = metrics["star_font"]
            star_h = metrics["star_h"]
            stars_y = cur_y + score_h + inner_gap
            filled_stars = max(0, min(5, round(rating / 2)))
            filled_text = "★" * filled_stars
            empty_text = "☆" * (5 - filled_stars)
            cursor_x = inner_x
            if filled_text:
                draw.text((cursor_x, stars_y), filled_text, font=star_font, fill=LETTERBOXD_STAR_FILLED)
                filled_w, _ = self._measure_text(draw, filled_text, star_font)
                cursor_x += filled_w
            if empty_text:
                draw.text((cursor_x, stars_y), empty_text, font=star_font, fill=LETTERBOXD_STAR_EMPTY_OUTLINE)
            cur_y = stars_y + star_h
        else:
            cur_y += score_h

        if distribution:
            extra_space = max(0, panel_h - (score_block_h + chart_block_h))
            cur_y += extra_space + section_gap

            draw.text((inner_x, cur_y), labels["ratings"], font=chart_title_font, fill=secondary_text_color)
            if count_text:
                count_w, _ = self._measure_text(draw, count_text, chart_count_font)
                draw.text(
                    (inner_x + panel_w - count_w, cur_y),
                    count_text,
                    font=chart_count_font,
                    fill=secondary_text_color,
                )

            cur_y += chart_title_h + header_gap
            draw.line(
                [(inner_x, cur_y), (inner_x + panel_w, cur_y)],
                fill=LETTERBOXD_DIVIDER,
                width=1,
            )
            cur_y += chart_gap
            self._draw_rating_histogram(
                draw,
                inner_x,
                cur_y,
                panel_w,
                chart_h,
                distribution,
                dim,
                bar_color=bar_color,
            )

    def _draw_rating_histogram(self, draw, x, y, width, height, distribution, dim, bar_color=LETTERBOXD_BAR):
        """Draw a compact 5-star histogram with stronger bar presence."""
        if not distribution:
            return

        bucket_count = len(distribution)
        bar_gap = max(10, int(dim * 0.02))
        available_width = max(width - bar_gap * (bucket_count - 1), bucket_count)
        bar_width = max(18, available_width // bucket_count)
        max_count = max(distribution)
        if max_count <= 0:
            return

        total_bar_width = bucket_count * bar_width + (bucket_count - 1) * bar_gap
        start_x = x + max(0, (width - total_bar_width) // 2)
        top_pad = max(6, int(dim * 0.012))
        drawable_h = max(1, height - top_pad)
        bottom_y = y + height
        for index, count in enumerate(distribution):
            ratio = count / max_count
            bar_height = max(10, int(drawable_h * ratio)) if count > 0 else 0
            bar_height = min(drawable_h, bar_height)
            bar_x0 = start_x + index * (bar_width + bar_gap)
            bar_y0 = bottom_y - bar_height
            draw.rectangle([bar_x0, bar_y0, bar_x0 + bar_width - 1, bottom_y], fill=bar_color)

    def _get_score_panel_metrics(
        self,
        draw,
        rating,
        vote_count,
        distribution,
        dim,
        panel_w,
        available_score_h=0,
        title_line_count=1,
        labels=None,
    ):
        """Measure score and distribution pieces for vertical layout."""
        labels = labels or TRANSLATIONS[DEFAULT_LANGUAGE]

        label_font = get_font("Jost", int(dim * 0.0374)) or ImageFont.load_default()
        score_font = get_font("Jost", int(dim * 0.095), "bold") or ImageFont.load_default()
        chart_title_font = get_font("Jost", int(dim * 0.0451), "bold") or ImageFont.load_default()
        chart_count_font = get_font("Jost", int(dim * 0.0374), "bold") or ImageFont.load_default()

        label_text = labels["user_score"]
        score_text = f"{rating:.1f}/10" if rating else "N/A"
        count_text = (
            f"{self._format_vote_count(vote_count, labels)} {labels['fans']}"
            if distribution and vote_count
            else ""
        )

        _, label_h = self._measure_text(draw, label_text, label_font)
        _, score_h = self._measure_text(draw, score_text, score_font)
        _, chart_title_h = self._measure_text(draw, labels["ratings"], chart_title_font)

        star_font_size = int(dim * 0.0641)
        try:
            star_font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                star_font_size,
            )
        except (OSError, IOError):
            star_font = get_font("Jost", star_font_size, "bold") or ImageFont.load_default()
        _, star_h = self._measure_text(draw, "★★★★★", star_font)

        pad_y = int(dim * 0.016)
        inner_gap = int(dim * 0.009)
        section_gap = int(dim * 0.012)
        header_gap = int(dim * 0.008)
        chart_gap = int(dim * 0.008)
        base_chart_h = max(int(dim * 0.32), int(panel_w * 0.32))

        title_line_scale = 1.0
        if title_line_count == 2:
            title_line_scale = 0.84
        elif title_line_count >= 3:
            title_line_scale = 0.72

        chart_h = int(base_chart_h * title_line_scale)

        score_block_h = pad_y + label_h + inner_gap + score_h
        if rating:
            score_block_h += inner_gap + star_h

        if available_score_h > 0:
            max_chart_h = max(
                0,
                available_score_h
                - score_block_h
                - section_gap
                - chart_title_h
                - header_gap
                - 1
                - chart_gap,
            )
            if max_chart_h > 0:
                chart_h = min(chart_h, max_chart_h)

        chart_block_h = 0
        if distribution:
            chart_block_h = section_gap + chart_title_h + header_gap + 1 + chart_gap + chart_h

        panel_h = score_block_h + chart_block_h

        return {
            "label_font": label_font,
            "score_font": score_font,
            "chart_title_font": chart_title_font,
            "chart_count_font": chart_count_font,
            "star_font": star_font,
            "star_h": star_h,
            "label_text": label_text,
            "score_text": score_text,
            "count_text": count_text,
            "label_h": label_h,
            "score_h": score_h,
            "chart_title_h": chart_title_h,
            "pad_y": pad_y,
            "inner_gap": inner_gap,
            "section_gap": section_gap,
            "header_gap": header_gap,
            "chart_gap": chart_gap,
            "chart_h": chart_h,
            "score_block_h": score_block_h,
            "chart_block_h": chart_block_h,
            "panel_h": panel_h,
        }



    def _draw_poster_placeholder(self, draw, x0, y0, x1, y1, dim):
        """Draw a placeholder rectangle when poster is unavailable."""
        draw.rounded_rectangle(
            [x0, y0, x1, y1],
            radius=int(dim * 0.02),
            outline=LETTERBOXD_DIVIDER,
            width=2,
        )
        cx = (x0 + x1) // 2
        cy = (y0 + y1) // 2
        label_font = get_font("Jost", int(dim * 0.035)) or ImageFont.load_default()
        draw.text((cx, cy), "No Poster", font=label_font, fill=LETTERBOXD_MUTED, anchor="mm")

    def _wrap_text(self, draw, text, max_width, font, max_lines=2):
        """Word-wrap text, truncating at a word boundary with ellipsis on the last line."""
        words = text.split()
        if not words:
            return [""]

        lines = []
        index = 0
        while index < len(words):
            line_words = []
            while index < len(words):
                test_line = " ".join(line_words + [words[index]])
                bbox = draw.textbbox((0, 0), test_line, font=font)
                if bbox[2] - bbox[0] <= max_width:
                    line_words.append(words[index])
                    index += 1
                else:
                    break

            if not line_words:
                line_words = [words[index]]
                index += 1

            is_last_allowed = len(lines) >= max_lines - 1
            has_more_words = index < len(words)

            if is_last_allowed and has_more_words:
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
        """Return width and vertical advance for consistent stacked layout."""
        bbox = draw.textbbox((0, 0), text or " ", font=font)
        return bbox[2] - bbox[0], bbox[3]
