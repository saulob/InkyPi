import datetime
from PIL import Image, ImageDraw, ImageFont
from plugins.base_plugin.base_plugin import BasePlugin

class CalendarCardPlugin(BasePlugin):
    def generate_settings_template(self):
        template_params = super().generate_settings_template()
        template_params['style_settings'] = True
        return template_params

    def generate_image(self, settings, device_config):
        dimensions = device_config.get_resolution()
        width, height = dimensions

        today = datetime.datetime.now()
        month = today.strftime('%B').upper()
        weekday = today.strftime('%A')
        day = today.day

        img = Image.new('RGB', (width, height), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)

        fallback_regular = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

        # Scale font sizes relative to the smallest dimension
        scale = min(width, height) / 250
        month_size = int(28 * scale)
        weekday_size = int(34 * scale)
        day_size = int(110 * scale)

        font_month = ImageFont.truetype(fallback_regular, month_size)
        font_weekday = ImageFont.truetype(fallback_regular, weekday_size)
        font_day = ImageFont.truetype(fallback_regular, day_size)

        def get_text_size(text, font):
            bbox = font.getbbox(text)
            return bbox[2] - bbox[0], bbox[3] - bbox[1]

        # Visual layout: centered calendar card
        x_center = width // 2

        # Calculate total content height to center vertically
        _, h_month = get_text_size(month, font_month)
        _, h_weekday = get_text_size(weekday, font_weekday)
        _, h_day = get_text_size(str(day), font_day)
        spacing_1 = int(18 * scale)
        spacing_2 = int(24 * scale)
        total_height = h_month + spacing_1 + h_weekday + spacing_2 + h_day
        y_offset = (height - total_height) // 2

        # Month (top, gray)
        w_month, _ = get_text_size(month, font_month)
        draw.text((x_center - w_month // 2, y_offset), month, fill=(120, 120, 120), font=font_month)
        y_offset += h_month + spacing_1

        # Weekday (middle, black)
        w_weekday, _ = get_text_size(weekday, font_weekday)
        draw.text((x_center - w_weekday // 2, y_offset), weekday, fill=(0, 0, 0), font=font_weekday)
        y_offset += h_weekday + spacing_2

        # Day (large, red)
        w_day, _ = get_text_size(str(day), font_day)
        draw.text((x_center - w_day // 2, y_offset), str(day), fill=(255, 0, 0), font=font_day)

        return img
