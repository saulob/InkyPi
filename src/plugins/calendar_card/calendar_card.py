import datetime
from PIL import Image, ImageDraw, ImageFont
from plugins.base_plugin.base_plugin import BasePlugin

class CalendarCardPlugin(BasePlugin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Calendar Card"
        self.description = "Displays a calendar card with the current day."

    def generate_settings_template(self):
        template_params = super().generate_settings_template()
        template_params['style_settings'] = True
        return template_params

    def render(self, width=250, height=250, settings=None):
        """
        Render a calendar card image with the current day, month, and weekday, centered. Exibe o título se fornecido nas configurações.
        """
        today = datetime.datetime.now()
        month = today.strftime('%B').upper()
        weekday = today.strftime('%A')
        day = today.day

        img = Image.new('RGB', (width, height), color=(240, 241, 240))
        draw = ImageDraw.Draw(img)

        # Fonts (adjust the path as needed)
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
        font_month = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        font_weekday = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
        font_day = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 80)

        # Center text (use getbbox for Pillow >=8.0)
        def get_text_size(text, font):
            bbox = font.getbbox(text)
            width = bbox[2] - bbox[0]
            height = bbox[3] - bbox[1]
            return width, height

        y_offset = 20
        # Exibe o título se fornecido nas configurações
        title = None
        if settings and isinstance(settings, dict):
            title = settings.get('title')
        if not title:
            title = "Calendar"
        w_title, h_title = get_text_size(title, font_title)
        draw.text(((width-w_title)/2, y_offset), title, fill=(80,80,80), font=font_title)
        y_offset += h_title + 10

        w_month, h_month = get_text_size(month, font_month)
        w_weekday, h_weekday = get_text_size(weekday, font_weekday)
        w_day, h_day = get_text_size(str(day), font=font_day)

        draw.text(((width-w_month)/2, y_offset), month, fill=(150,150,150), font=font_month)
        y_offset += h_month + 5
        draw.text(((width-w_weekday)/2, y_offset), weekday, fill=(200,0,0), font=font_weekday)
        y_offset += h_weekday + 10
        draw.text(((width-w_day)/2, y_offset), str(day), fill=(30,30,30), font=font_day)

        return img

    def get_image(self):
        return self.render(settings=getattr(self, 'settings', None))

    def generate_image(self, settings, device_config):
        """
        Required by the InkyPi plugin system. Returns the generated calendar card image.
        """
        return self.render(settings=settings)
import datetime
from PIL import Image, ImageDraw, ImageFont
from plugins.base_plugin.base_plugin import BasePlugin

class CalendarCardPlugin(BasePlugin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Calendar Card"
        self.description = "Displays a calendar card with the current day."

    def render(self, width=250, height=250):
        """
        Render a calendar card image with the current day, month, and weekday, centered.
        """
        today = datetime.datetime.now()
        month = today.strftime('%B').upper()
        weekday = today.strftime('%A')
        day = today.day

        img = Image.new('RGB', (width, height), color=(240, 241, 240))
        draw = ImageDraw.Draw(img)

        # Fonts (adjust the path as needed)
        font_month = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        font_weekday = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
        font_day = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 80)


        # Center text (use getbbox for Pillow >=8.0)
        def get_text_size(text, font):
            bbox = font.getbbox(text)
            width = bbox[2] - bbox[0]
            height = bbox[3] - bbox[1]
            return width, height

        w_month, h_month = get_text_size(month, font_month)
        w_weekday, h_weekday = get_text_size(weekday, font_weekday)
        w_day, h_day = get_text_size(str(day), font=font_day)

        y_offset = 30
        draw.text(((width-w_month)/2, y_offset), month, fill=(150,150,150), font=font_month)
        y_offset += h_month + 5
        draw.text(((width-w_weekday)/2, y_offset), weekday, fill=(200,0,0), font=font_weekday)
        y_offset += h_weekday + 10
        draw.text(((width-w_day)/2, y_offset), str(day), fill=(30,30,30), font=font_day)

        return img

    def get_image(self):
        return self.render()

    def generate_image(self, settings, device_config):
        """
        Required by the InkyPi plugin system. Returns the generated calendar card image.
        """
        return self.render()
