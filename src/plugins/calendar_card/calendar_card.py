import datetime
from PIL import Image, ImageDraw
from plugins.base_plugin.base_plugin import BasePlugin
from utils.app_utils import get_font

class CalendarCardPlugin(BasePlugin):
    def generate_image(self, settings, device_config):
        dimensions = device_config.get_resolution()
        width, height = dimensions

        today = datetime.datetime.now()
        month = today.strftime('%B').upper()
        weekday = today.strftime('%A')
        day = str(today.day)

        img = Image.new('RGB', (width, height), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)

        # Scale font sizes relative to the smallest dimension
        base = min(width, height)
        font_month = get_font("Jost", int(base * 0.11))
        font_weekday = get_font("Jost", int(base * 0.14))
        font_day = get_font("Jost", int(base * 0.44))

        def text_size(text, font):
            bbox = font.getbbox(text)
            return bbox[2] - bbox[0], bbox[3] - bbox[1]

        # Calculate total content height to center vertically
        _, h_month = text_size(month, font_month)
        _, h_weekday = text_size(weekday, font_weekday)
        _, h_day = text_size(day, font_day)
        gap1 = int(base * 0.04)
        gap2 = int(base * 0.05)
        total_h = h_month + gap1 + h_weekday + gap2 + h_day
        y = (height - total_h) // 2
        cx = width // 2

        # Month (gray)
        w, _ = text_size(month, font_month)
        draw.text((cx - w // 2, y), month, fill=(120, 120, 120), font=font_month)
        y += h_month + gap1

        # Weekday (black)
        w, _ = text_size(weekday, font_weekday)
        draw.text((cx - w // 2, y), weekday, fill=(0, 0, 0), font=font_weekday)
        y += h_weekday + gap2

        # Day (red)
        w, _ = text_size(day, font_day)
        draw.text((cx - w // 2, y), day, fill=(255, 0, 0), font=font_day)

        return img
