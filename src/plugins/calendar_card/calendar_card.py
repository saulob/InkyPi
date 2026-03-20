import datetime
from PIL import Image, ImageDraw, ImageFont
from plugins.base_plugin.base_plugin import BasePlugin

class CalendarCardPlugin(BasePlugin):
    def generate_settings_template(self):
        template_params = super().generate_settings_template()
        template_params['style_settings'] = True
        return template_params

    def render(self, width=250, height=250, settings=None):
        """
        Render a calendar card image with the current day, month, and weekday, visually styled like the iPhone calendar icon.
        """
        today = datetime.datetime.now()
        month = today.strftime('%B').upper()
        weekday = today.strftime('%A')
        day = today.day

        img = Image.new('RGB', (width, height), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)

        # Font paths (adjust as needed for your system)
        # Font paths (adjust as needed)
        sf_pro_text_medium = "/usr/share/fonts/truetype/sf-pro/SF-Pro-Text-Medium.ttf"
        sf_pro_text_regular = "/usr/share/fonts/truetype/sf-pro/SF-Pro-Text-Regular.ttf"
        sf_pro_text_light = "/usr/share/fonts/truetype/sf-pro/SF-Pro-Text-Light.ttf"
        sf_pro_display_light = "/usr/share/fonts/truetype/sf-pro/SF-Pro-Display-Light.ttf"
        sf_pro_display_thin = "/usr/share/fonts/truetype/sf-pro/SF-Pro-Display-Thin.ttf"
        helvetica_neue = "/usr/share/fonts/truetype/helvetica/HelveticaNeue-Light.ttf"
        inter_medium = "/usr/share/fonts/truetype/inter/Inter-Medium.ttf"
        inter_regular = "/usr/share/fonts/truetype/inter/Inter-Regular.ttf"
        inter_light = "/usr/share/fonts/truetype/inter/Inter-Light.ttf"
        roboto_medium = "/usr/share/fonts/truetype/roboto/Roboto-Medium.ttf"
        roboto_regular = "/usr/share/fonts/truetype/roboto/Roboto-Regular.ttf"
        roboto_light = "/usr/share/fonts/truetype/roboto/Roboto-Light.ttf"
        roboto_thin = "/usr/share/fonts/truetype/roboto/Roboto-Thin.ttf"
        avenir_regular = "/usr/share/fonts/truetype/avenir/Avenir-Regular.ttf"
        fallback_bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        fallback_regular = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        fallback_light = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

        # Month: SF Pro Text Medium > SF Pro Text Regular > Inter Medium > Roboto Medium > Avenir Regular > fallback
        try:
            font_month = ImageFont.truetype(sf_pro_text_medium, 28)
        except:
            try:
                font_month = ImageFont.truetype(sf_pro_text_regular, 28)
            except:
                try:
                    font_month = ImageFont.truetype(inter_medium, 28)
                except:
                    try:
                        font_month = ImageFont.truetype(roboto_medium, 28)
                    except:
                        try:
                            font_month = ImageFont.truetype(avenir_regular, 28)
                        except:
                            font_month = ImageFont.truetype(fallback_regular, 28)

        # Weekday: SF Pro Text Regular > Inter Regular > Roboto Regular > Avenir Regular > fallback
        try:
            font_weekday = ImageFont.truetype(sf_pro_text_regular, 34)
        except:
            try:
                font_weekday = ImageFont.truetype(inter_regular, 34)
            except:
                try:
                    font_weekday = ImageFont.truetype(roboto_regular, 34)
                except:
                    try:
                        font_weekday = ImageFont.truetype(avenir_regular, 34)
                    except:
                        font_weekday = ImageFont.truetype(fallback_regular, 34)

        # Day: SF Pro Display Light > SF Pro Display Thin > Helvetica Neue > Inter Light > Roboto Light > Roboto Thin > fallback
        try:
            font_day = ImageFont.truetype(sf_pro_display_light, 110)
        except:
            try:
                font_day = ImageFont.truetype(sf_pro_display_thin, 110)
            except:
                try:
                    font_day = ImageFont.truetype(helvetica_neue, 110)
                except:
                    try:
                        font_day = ImageFont.truetype(inter_light, 110)
                    except:
                        try:
                            font_day = ImageFont.truetype(roboto_light, 110)
                        except:
                            try:
                                font_day = ImageFont.truetype(roboto_thin, 110)
                            except:
                                font_day = ImageFont.truetype(fallback_light, 110)

        def get_text_size(text, font):
            bbox = font.getbbox(text)
            width = bbox[2] - bbox[0]
            height = bbox[3] - bbox[1]
            return width, height


        # Visual layout: iPhone calendar icon style
        y_offset = 50  # Adjusted starting position
        x_center = width // 2
        x_shift = 0  # Center text horizontally

        # Month (top, gray, SF Pro Text Medium)
        w_month, h_month = get_text_size(month, font_month)
        draw.text((x_center - w_month // 2 + x_shift, y_offset), month, fill=(120, 120, 120), font=font_month)
        y_offset += h_month + 18  # Adjusted vertical spacing

        # Weekday (middle, black, SF Pro Text Regular)
        w_weekday, h_weekday = get_text_size(weekday, font_weekday)
        draw.text((x_center - w_weekday // 2 + x_shift, y_offset), weekday, fill=(0, 0, 0), font=font_weekday)
        y_offset += h_weekday + 24  # Adjusted vertical spacing

        # Day (big, SF Pro Display Light, red)
        w_day, h_day = get_text_size(str(day), font=font_day)
        draw.text((x_center - w_day // 2 + x_shift, y_offset), str(day), fill=(255, 0, 0), font=font_day)

        return img

    def get_image(self):
        return self.render(settings=getattr(self, 'settings', None))

    def generate_image(self, settings, device_config):
        """
        Required by the InkyPi plugin system. Returns the generated calendar card image.
        """
        return self.render(settings=settings)
