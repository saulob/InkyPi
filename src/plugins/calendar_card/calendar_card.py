import datetime
import json
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from plugins.base_plugin.base_plugin import BasePlugin
from plugins.calendar.constants import LOCALE_MAP
from utils.app_utils import get_font, resolve_path

UNSUPPORTED_TEXT = 'not supported'
JOST_FONT_PATH = resolve_path("static/fonts/Jost.ttf")
KNOWN_UNSUPPORTED_FONT_LOCALES = {
    'ar',
    'ar-dz',
    'ar-kw',
    'ar-ly',
    'ar-ma',
    'ar-sa',
    'ar-tn',
    'bn',
    'el',
    'fa',
    'he',
    'hi',
    'hy-am',
    'ja',
    'ka',
    'km',
    'ko',
    'ne',
    'si-lk',
    'ta-in',
    'th',
    'ug',
    'zh-cn',
    'zh-tw'
}


@lru_cache(maxsize=None)
def _missing_glyph_signature(font_path, size):
    font = ImageFont.truetype(font_path, size)
    mask = font.getmask('\U00013000')
    return mask.size, bytes(mask)


def _glyph_signature(font, value):
    mask = font.getmask(value)
    return mask.size, bytes(mask)


def font_supports_text(font, text, font_path=None):
    content = str(text or '')
    if not content.strip():
        return False

    missing_signature = None
    if font_path:
        try:
            missing_signature = _missing_glyph_signature(font_path, font.size)
        except Exception:
            missing_signature = None

    for char in content:
        if char.isspace():
            continue
        try:
            signature = _glyph_signature(font, char)
        except Exception:
            return False
        if signature[0][0] <= 0:
            return False
        if missing_signature and signature == missing_signature:
            return False

    return True


def normalize_display_text(value, uppercase=False):
    text = str(value or '').strip()
    if not text:
        return text
    if text.casefold() == UNSUPPORTED_TEXT:
        return UNSUPPORTED_TEXT
    if uppercase:
        return text.upper()
    return capitalize_first_letter(text)


def capitalize_first_letter(value):
    text = str(value or '').strip()
    if not text:
        return text
    return text[0].upper() + text[1:]

class CalendarCardPlugin(BasePlugin):
    def generate_settings_template(self):
        template_params = super().generate_settings_template()
        sorted_map = dict(sorted(LOCALE_MAP.items(), key=lambda item: item[1]))
        template_params['locale_map'] = sorted_map
        template_params['font_unsupported_locales_json'] = json.dumps(sorted(KNOWN_UNSUPPORTED_FONT_LOCALES))
        return template_params

    def generate_image(self, settings, device_config):
        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]
        width, height = dimensions

        today = datetime.datetime.now()

        default_months = [
            'January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'
        ]
        default_weekdays = [
            'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'
        ]

        month_names = default_months
        weekday_names = default_weekdays

        month_names_json = settings.get('monthNames')
        weekday_names_json = settings.get('weekdayNames')


        def has_blank(arr, expected_len):
            # Accept only lists of correct length, all non-empty, all strings
            if not isinstance(arr, list) or len(arr) != expected_len:
                return True
            for v in arr:
                if not isinstance(v, str) or not v.strip():
                    return True
            return False

        if month_names_json:
            try:
                parsed_months = json.loads(month_names_json)
                if not has_blank(parsed_months, 12):
                    month_names = parsed_months
            except (TypeError, ValueError, json.JSONDecodeError):
                pass

        if weekday_names_json:
            try:
                parsed_weekdays = json.loads(weekday_names_json)
                if not has_blank(parsed_weekdays, 7):
                    weekday_names = parsed_weekdays
            except (TypeError, ValueError, json.JSONDecodeError):
                pass

        # Fallback: if any month or weekday is blank, use English
        if has_blank(month_names, 12):
            month_names = default_months
        if has_blank(weekday_names, 7):
            weekday_names = default_weekdays

        selected_language = str(settings.get('language') or 'en').strip().lower()
        month = normalize_display_text(month_names[today.month - 1], uppercase=True)
        weekday = normalize_display_text(weekday_names[today.weekday()])
        day = str(today.day)
        default_month = normalize_display_text(default_months[today.month - 1], uppercase=True)
        default_weekday = normalize_display_text(default_weekdays[today.weekday()])

        img = Image.new('RGB', (width, height), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)

        # Scale font sizes relative to the smallest dimension
        base = min(width, height)

        def pick_font(text, size):
            font = get_font("Jost", size)
            if font_supports_text(font, text, JOST_FONT_PATH):
                return font
            return get_font("Jost", size)

        month_font = get_font("Jost", int(base * 0.11))
        weekday_font = get_font("Jost", int(base * 0.14))
        if selected_language != 'en':
            month_supported = font_supports_text(month_font, month, JOST_FONT_PATH)
            weekday_supported = font_supports_text(weekday_font, weekday, JOST_FONT_PATH)
            if not month_supported or not weekday_supported:
                month = UNSUPPORTED_TEXT
                weekday = UNSUPPORTED_TEXT
        elif month == UNSUPPORTED_TEXT or weekday == UNSUPPORTED_TEXT:
            month = default_month
            weekday = default_weekday

        font_month = pick_font(month, int(base * 0.11))
        font_weekday = pick_font(weekday, int(base * 0.14))
        font_day = pick_font(day, int(base * 0.50))

        def text_size(text, font):
            bbox = font.getbbox(text)
            return bbox[2] - bbox[0], bbox[3] - bbox[1]

        # Calculate total content height and center visually (shifted up)
        _, h_month = text_size(month, font_month)
        _, h_weekday = text_size(weekday, font_weekday)
        _, h_day = text_size(day, font_day)
        gap1 = int(base * 0.04)
        gap2 = int(base * 0.01)
        total_h = h_month + gap1 + h_weekday + gap2 + h_day
        y = (height - total_h) // 2 - int(base * 0.12)
        cx = width // 2

        # Month (light gray)
        w, _ = text_size(month, font_month)
        month_y = y - int(base * 0.02)
        draw.text((cx - w // 2, month_y), month, fill=(150, 150, 150), font=font_month)
        y += h_month + gap1

        # Weekday (red)
        w, _ = text_size(weekday, font_weekday)
        weekday_y = y - int(base * 0.015)
        draw.text((cx - w // 2, weekday_y), weekday, fill=(255, 59, 48), font=font_weekday)
        y += h_weekday + gap2

        # Day (black)
        w, _ = text_size(day, font_day)
        day_y = y - int(base * 0.01)
        draw.text((cx - w // 2, day_y), day, fill=(0, 0, 0), font=font_day)

        return img
