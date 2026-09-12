import calendar as calendar_module
from datetime import datetime, timedelta
from pathlib import Path

import pytz
from PIL import Image, ImageColor, ImageDraw, ImageFont

from plugins.base_plugin.base_plugin import BasePlugin
from plugins.simple_calendar.simple_calendar import LOCALE_DATA
from utils.app_utils import get_font


LANGUAGE_OPTIONS = (
    ("nl", "Dutch"),
    ("en", "English"),
    ("fr", "French"),
    ("de", "German"),
    ("id", "Indonesian"),
    ("it", "Italian"),
    ("pt", "Portuguese"),
    ("es", "Spanish"),
)

PRIMARY_COLOR_HEX = "#2457a6"
HIGHLIGHT_COLOR_HEX = "#e61a1a"
PRIMARY_COLOR = ImageColor.getrgb(PRIMARY_COLOR_HEX)
HIGHLIGHT_COLOR = ImageColor.getrgb(HIGHLIGHT_COLOR_HEX)
MUTED_COLOR = (185, 203, 226)
HIGHLIGHT_DAY_FONT_PATH = Path(__file__).resolve().parent / "fonts" / "SF-Pro-Display-Semibold.otf"


class DuoCalendar(BasePlugin):
    def generate_settings_template(self):
        template_params = super().generate_settings_template()
        template_params["style_settings"] = False
        template_params["language_options"] = LANGUAGE_OPTIONS
        template_params["primary_color"] = PRIMARY_COLOR_HEX
        template_params["highlight_color"] = HIGHLIGHT_COLOR_HEX
        return template_params

    def generate_image(self, settings, device_config):
        settings = settings if isinstance(settings, dict) else {}

        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]

        timezone_name = device_config.get_config(
            "timezone", default="America/New_York"
        )
        try:
            timezone = pytz.timezone(timezone_name)
        except (pytz.UnknownTimeZoneError, AttributeError):
            timezone = pytz.timezone("America/New_York")

        current_datetime = datetime.now(timezone)
        selected_date = self._get_selected_date(settings, current_datetime)
        language = self._get_locale_key(
            settings.get("language") or settings.get("locale", "en")
        )
        primary_color = self._parse_color(
            settings.get("primaryColor"), PRIMARY_COLOR
        )
        highlight_color = self._parse_color(
            settings.get("highlightColor"), HIGHLIGHT_COLOR
        )
        show_highlight_day = self._parse_boolean(
            settings.get("showHighlightDay"), default=True
        )
        return self._render_calendar(
            dimensions,
            selected_date,
            current_datetime,
            LOCALE_DATA[language],
            primary_color,
            highlight_color,
            show_highlight_day,
        )

    def _render_calendar(
        self,
        dimensions,
        selected_date,
        current_datetime,
        locale_data,
        primary_color,
        highlight_color,
        show_highlight_day,
    ):
        width, height = dimensions
        image = Image.new("RGB", dimensions, "white")
        draw = ImageDraw.Draw(image)

        minimum_dimension = min(width, height)
        side_padding = max(int(width * 0.055), 12)
        top_padding = max(int(height * 0.055), 12)
        month_font_size = max(int(minimum_dimension * 0.09), 22)
        day_font_size = max(int(minimum_dimension * 0.065), 18)
        weekday_font_size = day_font_size

        month_font = get_font("Jost", month_font_size)
        time_font = get_font("Jost", month_font_size)
        weekday_font = get_font("Jost", weekday_font_size)
        day_font = get_font("Jost", day_font_size)

        month_name = locale_data["months"][selected_date.month - 1].capitalize()
        draw.text(
            (side_padding, top_padding),
            month_name,
            fill=highlight_color,
            font=month_font,
            anchor="la",
        )

        time_text = f"{current_datetime.hour % 12 or 12}:{current_datetime.minute:02d}"
        draw.text(
            (width - side_padding, top_padding),
            time_text,
            fill=highlight_color,
            font=time_font,
            anchor="ra",
        )

        header_y = top_padding + month_font_size * 1.7
        grid_top = header_y + weekday_font_size * 1.4
        grid_bottom = height - max(int(height * 0.045), 10)
        grid_width = width - 2 * side_padding
        column_width = grid_width / 7
        month_grid = calendar_module.Calendar(firstweekday=6).monthdatescalendar(
            selected_date.year, selected_date.month
        )
        while len(month_grid) < 6:
            next_week_start = month_grid[-1][-1] + timedelta(days=1)
            month_grid.append(
                [next_week_start + timedelta(days=day_offset) for day_offset in range(7)]
            )
        row_height = (grid_bottom - grid_top) / len(month_grid)

        if show_highlight_day:
            background_day_font = ImageFont.truetype(
                str(HIGHLIGHT_DAY_FONT_PATH),
                max(int((grid_bottom - grid_top) * 1.22), 80),
            )
            draw.text(
                (
                    width / 2,
                    grid_top + (grid_bottom - grid_top) / 2 - row_height * 0.28,
                ),
                str(selected_date.day),
                fill=highlight_color,
                font=background_day_font,
                anchor="mm",
            )

        for index, label in enumerate(locale_data["headers"]):
            center_x = side_padding + column_width * (index + 0.5)
            draw.text(
                (center_x, header_y),
                label,
                fill=primary_color,
                font=weekday_font,
                anchor="ma",
            )

        for week_index, week in enumerate(month_grid):
            center_y = grid_top + row_height * (week_index + 0.5)
            for weekday_index, day in enumerate(week):
                center_x = side_padding + column_width * (weekday_index + 0.5)
                is_outside_month = day.month != selected_date.month
                is_selected = day == selected_date
                day_color = MUTED_COLOR if is_outside_month else primary_color

                if is_selected:
                    circle_radius = int(min(column_width, row_height) * 0.45)
                    draw.ellipse(
                        (
                            center_x - circle_radius,
                            center_y - circle_radius,
                            center_x + circle_radius,
                            center_y + circle_radius,
                        ),
                        fill=primary_color,
                    )
                    day_color = "white"

                draw.text(
                    (center_x, center_y),
                    str(day.day),
                    fill=day_color,
                    font=day_font,
                    anchor="mm",
                )

        return image

    @staticmethod
    def _get_selected_date(settings, current_datetime):
        custom_date = settings.get("customDate")
        if not custom_date:
            return current_datetime.date()

        try:
            return datetime.strptime(str(custom_date), "%Y-%m-%d").date()
        except ValueError as error:
            raise RuntimeError("Invalid date. Use YYYY-MM-DD.") from error

    @staticmethod
    def _get_locale_key(language):
        language = str(language or "en").strip().lower()
        return language if language in LOCALE_DATA else "en"

    @staticmethod
    def _parse_boolean(value, default=False):
        if value is None or value == "":
            return default
        return str(value).strip().lower() in {"true", "1", "on", "yes"}

    @staticmethod
    def _parse_color(value, fallback):
        if not value:
            return fallback

        try:
            return ImageColor.getrgb(str(value))[:3]
        except (TypeError, ValueError):
            return fallback