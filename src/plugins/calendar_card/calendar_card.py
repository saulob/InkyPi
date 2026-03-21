import datetime
import json

from PIL import Image, ImageDraw

from plugins.base_plugin.base_plugin import BasePlugin
from plugins.calendar.constants import LOCALE_MAP
from utils.app_utils import get_font


def capitalize_first_letter(value):
    text = str(value or '').strip()
    if not text:
        return text
    return text[0].upper() + text[1:]

class CalendarCardPlugin(BasePlugin):
    def generate_settings_template(self):
        template_params = super().generate_settings_template()
        template_params['locale_map'] = LOCALE_MAP
        return template_params

    def generate_image(self, settings, device_config):
        dimensions = device_config.get_resolution()
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

        if month_names_json:
            try:
                parsed_months = json.loads(month_names_json)
                if isinstance(parsed_months, list) and len(parsed_months) == 12:
                    month_names = parsed_months
            except (TypeError, ValueError, json.JSONDecodeError):
                pass

        if weekday_names_json:
            try:
                parsed_weekdays = json.loads(weekday_names_json)
                if isinstance(parsed_weekdays, list) and len(parsed_weekdays) == 7:
                    weekday_names = parsed_weekdays
            except (TypeError, ValueError, json.JSONDecodeError):
                pass

        month = str(month_names[today.month - 1]).upper()
        weekday = capitalize_first_letter(weekday_names[today.weekday()])
        day = str(today.day)

        img = Image.new('RGB', (width, height), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)

        # Scale font sizes relative to the smallest dimension
        base = min(width, height)
        font_month = get_font("Jost", int(base * 0.11))
        font_weekday = get_font("Jost", int(base * 0.14))
        font_day = get_font("Jost", int(base * 0.50))

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
