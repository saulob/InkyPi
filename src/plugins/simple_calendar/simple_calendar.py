import calendar
import unicodedata
from datetime import datetime

import pytz
from PIL import Image, ImageColor, ImageDraw

from plugins.base_plugin.base_plugin import BasePlugin
from utils.app_utils import get_font

LOCALE_DATA = {
    "de": {
        "weekday_abbrev": ["MO", "DI", "MI", "DO", "FR", "SA", "SO"],
        "headers": ["S", "M", "D", "M", "D", "F", "S"],
        "months": ["JANUAR", "FEBRUAR", "MÄRZ", "APRIL", "MAI", "JUNI", "JULI", "AUGUST", "SEPTEMBER", "OKTOBER", "NOVEMBER", "DEZEMBER"],
    },
    "en": {
        "weekday_abbrev": ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"],
        "headers": ["S", "M", "T", "W", "T", "F", "S"],
        "months": ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"],
    },
    "es": {
        "weekday_abbrev": ["LUN", "MAR", "MIÉ", "JUE", "VIE", "SÁB", "DOM"],
        "headers": ["D", "L", "M", "M", "J", "V", "S"],
        "months": ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"],
    },
    "fr": {
        "weekday_abbrev": ["LUN", "MAR", "MER", "JEU", "VEN", "SAM", "DIM"],
        "headers": ["D", "L", "M", "M", "J", "V", "S"],
        "months": ["JANVIER", "FÉVRIER", "MARS", "AVRIL", "MAI", "JUIN", "JUILLET", "AOÛT", "SEPTEMBRE", "OCTOBRE", "NOVEMBRE", "DÉCEMBRE"],
    },
    "id": {
        "weekday_abbrev": ["SEN", "SEL", "RAB", "KAM", "JUM", "SAB", "MIN"],
        "headers": ["M", "S", "S", "R", "K", "J", "S"],
        "months": ["JANUARI", "FEBRUARI", "MARET", "APRIL", "MEI", "JUNI", "JULI", "AGUSTUS", "SEPTEMBER", "OKTOBER", "NOVEMBER", "DESEMBER"],
    },
    "it": {
        "weekday_abbrev": ["LUN", "MAR", "MER", "GIO", "VEN", "SAB", "DOM"],
        "headers": ["D", "L", "M", "M", "G", "V", "S"],
        "months": ["GENNAIO", "FEBBRAIO", "MARZO", "APRILE", "MAGGIO", "GIUGNO", "LUGLIO", "AGOSTO", "SETTEMBRE", "OTTOBRE", "NOVEMBRE", "DICEMBRE"],
    },
    "nl": {
        "weekday_abbrev": ["MAA", "DIN", "WOE", "DON", "VRI", "ZAT", "ZON"],
        "headers": ["Z", "M", "D", "W", "D", "V", "Z"],
        "months": ["JANUARI", "FEBRUARI", "MAART", "APRIL", "MEI", "JUNI", "JULI", "AUGUSTUS", "SEPTEMBER", "OKTOBER", "NOVEMBER", "DECEMBER"],
    },
    "pt": {
        "weekday_abbrev": ["SEG", "TER", "QUA", "QUI", "SEX", "SÁB", "DOM"],
        "headers": ["D", "S", "T", "Q", "Q", "S", "S"],
        "months": ["JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO", "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"],
    },
}

# ---------------------------------------------------------------------------
# Dot-matrix glyph definitions (5 wide × 7 tall for digits, variable for letters)
# Each glyph is a list of (row, col) positions where a dot should be drawn.
# ---------------------------------------------------------------------------

_DIGIT_W, _DIGIT_H = 5, 7

_DIGIT_PATTERNS = {
    "0": [
        "01110",
        "10001",
        "10011",
        "10101",
        "11001",
        "10001",
        "01110",
    ],
    "1": [
        "00100",
        "01100",
        "00100",
        "00100",
        "00100",
        "00100",
        "01110",
    ],
    "2": [
        "01110",
        "10001",
        "00001",
        "00110",
        "01000",
        "10000",
        "11111",
    ],
    "3": [
        "01110",
        "10001",
        "00001",
        "00110",
        "00001",
        "10001",
        "01110",
    ],
    "4": [
        "00010",
        "00110",
        "01010",
        "10010",
        "11111",
        "00010",
        "00010",
    ],
    "5": [
        "11111",
        "10000",
        "11110",
        "00001",
        "00001",
        "10001",
        "01110",
    ],
    "6": [
        "01110",
        "10001",
        "10000",
        "11110",
        "10001",
        "10001",
        "01110",
    ],
    "7": [
        "11111",
        "00001",
        "00010",
        "00100",
        "01000",
        "01000",
        "01000",
    ],
    "8": [
        "01110",
        "10001",
        "10001",
        "01110",
        "10001",
        "10001",
        "01110",
    ],
    "9": [
        "01110",
        "10001",
        "10001",
        "01111",
        "00001",
        "10001",
        "01110",
    ],
}

# 5×7 dot-matrix letter patterns for weekday abbreviations
_LETTER_W, _LETTER_H = 5, 7

_LETTER_PATTERNS = {
    "S": [
        "01110",
        "10001",
        "10000",
        "01110",
        "00001",
        "10001",
        "01110",
    ],
    "A": [
        "01110",
        "10001",
        "10001",
        "11111",
        "10001",
        "10001",
        "10001",
    ],
    "T": [
        "11111",
        "00100",
        "00100",
        "00100",
        "00100",
        "00100",
        "00100",
    ],
    "M": [
        "10001",
        "11011",
        "10101",
        "10101",
        "10001",
        "10001",
        "10001",
    ],
    "O": [
        "01110",
        "10001",
        "10001",
        "10001",
        "10001",
        "10001",
        "01110",
    ],
    "N": [
        "10001",
        "11001",
        "10101",
        "10011",
        "10001",
        "10001",
        "10001",
    ],
    "U": [
        "10001",
        "10001",
        "10001",
        "10001",
        "10001",
        "10001",
        "01110",
    ],
    "E": [
        "11111",
        "10000",
        "10000",
        "11110",
        "10000",
        "10000",
        "11111",
    ],
    "W": [
        "10001",
        "10001",
        "10001",
        "10101",
        "10101",
        "11011",
        "10001",
    ],
    "D": [
        "11100",
        "10010",
        "10001",
        "10001",
        "10001",
        "10010",
        "11100",
    ],
    "H": [
        "10001",
        "10001",
        "10001",
        "11111",
        "10001",
        "10001",
        "10001",
    ],
    "F": [
        "11111",
        "10000",
        "10000",
        "11110",
        "10000",
        "10000",
        "10000",
    ],
    "R": [
        "11110",
        "10001",
        "10001",
        "11110",
        "10010",
        "10001",
        "10001",
    ],
    "I": [
        "01110",
        "00100",
        "00100",
        "00100",
        "00100",
        "00100",
        "01110",
    ],
    "P": [
        "11110",
        "10001",
        "10001",
        "11110",
        "10000",
        "10000",
        "10000",
    ],
    "Q": [
        "01110",
        "10001",
        "10001",
        "10001",
        "10001",
        "10011",
        "01111",
    ],
    "B": [
        "11110",
        "10001",
        "10001",
        "11110",
        "10001",
        "10001",
        "11110",
    ],
    "G": [
        "01110",
        "10001",
        "10000",
        "10111",
        "10001",
        "10001",
        "01110",
    ],
    "J": [
        "00111",
        "00010",
        "00010",
        "00010",
        "00010",
        "10010",
        "01100",
    ],
    "K": [
        "10001",
        "10010",
        "10100",
        "11000",
        "10100",
        "10010",
        "10001",
    ],
    "L": [
        "10000",
        "10000",
        "10000",
        "10000",
        "10000",
        "10000",
        "11111",
    ],
    "V": [
        "10001",
        "10001",
        "10001",
        "10001",
        "10001",
        "01010",
        "00100",
    ],
    "X": [
        "10001",
        "10001",
        "01010",
        "00100",
        "01010",
        "10001",
        "10001",
    ],
    "Z": [
        "11111",
        "00001",
        "00010",
        "00100",
        "01000",
        "10000",
        "11111",
    ],
}

def _get_dot_positions(char, reserve_accent_row=False):
    """Return list of (row, col) positions for a character glyph."""
    accent_positions = []
    base_char = char.upper()

    if base_char == "Á":
        base_char = "A"
        accent_positions = [(0, 3)]
    elif base_char == "É":
        base_char = "E"
        accent_positions = [(0, 3)]

    patterns = _DIGIT_PATTERNS if base_char.isdigit() else _LETTER_PATTERNS
    rows = patterns.get(base_char.upper(), [])
    positions = []
    for r, row_str in enumerate(rows):
        for c, ch in enumerate(row_str):
            if ch == "1":
                positions.append((r + (1 if reserve_accent_row else 0), c))

    positions.extend(accent_positions)

    return positions


def _draw_dotmatrix_text(draw, text, center_x, center_y, dot_radius, dot_spacing,
                         fill, glyph_w=5, glyph_h=7, char_gap_dots=1.5):
    """Draw a string of dot-matrix characters centred at (center_x, center_y)."""

    cell = dot_radius * 2 + dot_spacing
    char_width_px = glyph_w * cell
    gap_px = char_gap_dots * cell
    total_width = len(text) * char_width_px + (len(text) - 1) * gap_px
    accent_row = any(ch.upper() in {"Á", "É"} for ch in text)
    total_height = (glyph_h + (1 if accent_row else 0)) * cell

    start_x = center_x - total_width / 2
    start_y = center_y - total_height / 2

    for i, ch in enumerate(text):
        ox = start_x + i * (char_width_px + gap_px)
        oy = start_y
        for r, c in _get_dot_positions(ch, reserve_accent_row=accent_row):
            cx = ox + c * cell + dot_radius
            cy = oy + r * cell + dot_radius
            draw.ellipse(
                [cx - dot_radius, cy - dot_radius,
                 cx + dot_radius, cy + dot_radius],
                fill=fill,
            )


class SimpleCalendar(BasePlugin):

    def generate_settings_template(self):
        template_params = super().generate_settings_template()
        template_params['style_settings'] = False
        return template_params

    def generate_image(self, settings, device_config):
        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]

        timezone_name = device_config.get_config("timezone", default="America/New_York")
        tz = pytz.timezone(timezone_name)
        selected_date = self._get_selected_date(settings, tz)
        language = self._get_locale_key(settings.get("language") or settings.get("locale", "en"))
        locale_data = LOCALE_DATA.get(language)

        primary_color = self._parse_color(settings.get("primaryColor"), (230, 26, 26))
        highlight_color = self._parse_color(settings.get("highlightColor"), (163, 13, 13))
        layout_position = settings.get("layoutPosition", "left").lower()

        return self._render_calendar(dimensions, selected_date, primary_color, highlight_color, locale_data, language, layout_position)

    # ------------------------------------------------------------------
    # Core rendering
    # ------------------------------------------------------------------

    def _render_calendar(self, dimensions, now, primary_color, highlight_color, locale_data, language, layout_position="left"):
        W, H = dimensions

        # Colours
        dark = primary_color
        light_bg = (245, 245, 245)
        white = (255, 255, 255)
        text_color = (56, 56, 56)

        img = Image.new("RGB", (W, H), white)
        draw = ImageDraw.Draw(img)

        # Card geometry — generous margin, large rounded card
        margin_x = int(W * 0.04)
        margin_y = int(H * 0.06)
        card_left = margin_x
        card_top = margin_y
        card_right = W - margin_x
        card_bottom = H - margin_y
        card_w = card_right - card_left
        card_h = card_bottom - card_top
        corner_r = int(min(card_w, card_h) * 0.06)

        # Draw the full card background (light)
        draw.rounded_rectangle(
            [card_left, card_top, card_right, card_bottom],
            radius=corner_r,
            fill=light_bg,
        )

        # --- Panel and calendar bounds based on layout_position ---
        aspect = card_w / max(card_h, 1)

        panel_ratio = 0.38 if aspect >= 1.0 else 0.30
        panel_px = int(card_w * panel_ratio)
        if layout_position == "left":
            p_left, p_top, p_right, p_bottom = card_left, card_top, card_left + panel_px, card_bottom
            c_left, c_top, c_right, c_bottom = p_right, card_top, card_right, card_bottom
        else:  # right
            p_left, p_top, p_right, p_bottom = card_right - panel_px, card_top, card_right, card_bottom
            c_left, c_top, c_right, c_bottom = card_left, card_top, p_left, card_bottom

        cal_w = c_right - c_left
        cal_h = c_bottom - c_top
        cal_cx = c_left + cal_w // 2

        # --- Draw dark panel with rounded corners only on outer card edges ---
        if layout_position == "left":
            draw.rounded_rectangle(
                [p_left, p_top, p_right + corner_r, p_bottom],
                radius=corner_r,
                fill=dark,
            )
            draw.rectangle([p_right, p_top, p_right + corner_r, p_bottom], fill=light_bg)
        else:  # right
            draw.rounded_rectangle(
                [p_left - corner_r, p_top, p_right, p_bottom],
                radius=corner_r,
                fill=dark,
            )
            draw.rectangle([p_left - corner_r, p_top, p_left, p_bottom], fill=light_bg)

        # === DOT-MATRIX CONTENT (inside dark panel) ===
        panel_w = p_right - p_left
        panel_h = p_bottom - p_top
        panel_cx = p_left + panel_w // 2
        panel_cy = p_top + panel_h // 2

        day_str = str(now.day)
        weekday_str = self._get_weekday_abbrev(now, locale_data, language)

        # Vertical stack: day number above, weekday abbrev below
        avail_h = panel_h * 0.96
        avail_w = panel_w * 0.94

        n_day = len(day_str)
        # Fixed 2-digit reference column count so both 1-digit and 2-digit days
        # use the same stable bounding box and identical dot sizing.
        _DAY_DIGITS_REF = 2
        day_glyph_cols = _DIGIT_W * _DAY_DIGITS_REF + 1.5 * max(_DAY_DIGITS_REF - 1, 0)
        n_wk = len(weekday_str)
        wk_glyph_cols = _LETTER_W * n_wk + 0.9 * max(n_wk - 1, 0)

        DAY_SCALE = 1.85
        WK_SCALE = 0.85
        GAP_SCALE = 1.2
        total_u = _DIGIT_H * DAY_SCALE + GAP_SCALE + _LETTER_H * WK_SCALE

        u_from_h = avail_h / total_u
        u_from_day_w = (avail_w / (day_glyph_cols * DAY_SCALE)) if day_glyph_cols else u_from_h
        u_from_wk_w = (avail_w / (wk_glyph_cols * WK_SCALE)) if wk_glyph_cols else u_from_h
        u = min(u_from_h, u_from_day_w, u_from_wk_w)

        day_dot_r = max(int(u * DAY_SCALE * 0.39), 2)
        day_dot_spacing = max(int(u * DAY_SCALE * 0.22), 1)
        wk_dot_r = max(int(u * WK_SCALE * 0.39), 1)
        wk_dot_spacing = max(int(u * WK_SCALE * 0.22), 1)

        day_cell = day_dot_r * 2 + day_dot_spacing
        wk_cell = wk_dot_r * 2 + wk_dot_spacing
        gap = max(int(u * GAP_SCALE), 4)

        day_block_h = _DIGIT_H * day_cell
        wk_block_h = _LETTER_H * wk_cell
        total_content_h = day_block_h + gap + wk_block_h
        content_top = panel_cy - total_content_h // 2

        day_center_y = content_top + day_block_h // 2
        wk_center_y = content_top + day_block_h + gap + wk_block_h // 2
        if any(ch in {"Á", "É"} for ch in weekday_str.upper()):
            wk_center_y -= int(wk_cell * 0.45)

        # Slightly tighter inter-digit gap for 2-digit days improves visual balance.
        day_char_gap = 1.5 if n_day == 1 else 1.0
        _draw_dotmatrix_text(
            draw, day_str, panel_cx, day_center_y,
            day_dot_r, day_dot_spacing, white,
            glyph_w=_DIGIT_W, glyph_h=_DIGIT_H,
            char_gap_dots=day_char_gap,
        )
        _draw_dotmatrix_text(
            draw, weekday_str, panel_cx, wk_center_y,
            wk_dot_r, wk_dot_spacing, white,
            glyph_w=_LETTER_W, glyph_h=_LETTER_H,
            char_gap_dots=0.9,
        )

        # === CALENDAR CONTENT (inside light area) ===
        grid_side_pad = int(cal_w * 0.04)
        grid_left = c_left + grid_side_pad
        grid_right_edge = c_right - grid_side_pad
        grid_w = grid_right_edge - grid_left
        col_w = grid_w / 7

        month_font_size = max(int(col_w * 0.76), 12)
        year_font_size = max(int(col_w * 0.52), 9)
        header_font_size = max(int(col_w * 0.40), 9)
        day_font_size = max(int(col_w * 0.56), 10)

        month_font = get_font("Jost", month_font_size, "bold")
        year_font = get_font("Jost", year_font_size)
        header_font = get_font("Jost", header_font_size)
        day_font = get_font("Jost", day_font_size)

        top_pad = int(cal_h * 0.045)
        month_y = c_top + top_pad

        # Month and year
        month_name = self._get_month_name(now, locale_data, language)
        year_text = str(now.year)
        month_bbox = draw.textbbox((0, 0), month_name, font=month_font)
        year_bbox = draw.textbbox((0, 0), year_text, font=year_font)
        month_width = month_bbox[2] - month_bbox[0]
        header_gap = max(int(col_w * 0.4), 8)
        total_width = month_width + header_gap + (year_bbox[2] - year_bbox[0])
        header_left = cal_cx - total_width / 2

        baseline_y = month_y + month_font.getmetrics()[0]
        title_lift = max(int(month_font_size * 0.30), 8)

        draw.text(
            (header_left, baseline_y - title_lift), month_name,
            fill=text_color, font=month_font, anchor="ls",
        )
        year_y = baseline_y - int(month_font_size * 0.15) - title_lift
        draw.text(
            (header_left + month_width + header_gap, year_y),
            year_text,
            fill=(120, 120, 120), font=year_font, anchor="ls",
        )

        # Weekday header row
        header_labels = self._get_weekday_headers(locale_data, language)
        header_y = month_y + int(month_font_size * 1.4)

        for i, label in enumerate(header_labels):
            x = grid_left + col_w * i + col_w / 2
            draw.text(
                (x, header_y), label,
                fill=(155, 155, 155), font=header_font, anchor="mt",
            )

        # Month day grid
        grid_top_y = header_y + int(header_font_size * 1.4)
        available_grid_h = c_bottom - grid_top_y - int(cal_h * 0.015)

        cal_grid = calendar.Calendar(firstweekday=6).monthdayscalendar(now.year, now.month)
        num_weeks = len(cal_grid)
        row_h = available_grid_h / num_weeks

        today_circle_r = int(min(col_w, row_h) * 0.46)

        for week_idx, week in enumerate(cal_grid):
            row_cy = grid_top_y + row_h * week_idx + row_h / 2
            for dow, day in enumerate(week):
                if day == 0:
                    continue
                col_cx = grid_left + col_w * dow + col_w / 2

                if day == now.day:
                    draw.ellipse(
                        [col_cx - today_circle_r, row_cy - today_circle_r,
                         col_cx + today_circle_r, row_cy + today_circle_r],
                        fill=highlight_color,
                    )
                    draw.text(
                        (col_cx, row_cy), str(day),
                        fill=white, font=day_font, anchor="mm",
                    )
                else:
                    draw.text(
                        (col_cx, row_cy), str(day),
                        fill=text_color, font=day_font, anchor="mm",
                    )

        return img
    @staticmethod
    def _get_selected_date(settings, tz):
        custom_date = settings.get("customDate")
        if custom_date:
            return datetime.strptime(custom_date, "%Y-%m-%d").date()

        return datetime.now(tz).date()

    @staticmethod
    def _get_locale_key(language):
        language = str(language or "en").strip().lower()
        return language if language in LOCALE_DATA else "en"

    @staticmethod
    def _strip_accents(text):
        normalized = unicodedata.normalize("NFKD", text)
        return "".join(char for char in normalized if not unicodedata.combining(char))

    def _get_weekday_abbrev(self, now, locale_data, language):
        if locale_data:
            return locale_data["weekday_abbrev"][now.weekday()].upper()
        return now.strftime("%a").upper()[:3]

    def _get_month_name(self, now, locale_data, language):
        if locale_data:
            return locale_data["months"][now.month - 1]
        return self._strip_accents(now.strftime("%B").upper())

    def _get_weekday_headers(self, locale_data, language):
        if locale_data:
            return locale_data["headers"]
        return ["S", "M", "T", "W", "T", "F", "S"]

    @staticmethod
    def _parse_color(value, fallback):
        if not value:
            return fallback

        try:
            return ImageColor.getrgb(value)
        except Exception:
            return fallback
