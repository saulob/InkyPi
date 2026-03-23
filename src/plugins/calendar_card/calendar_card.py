import datetime

from PIL import Image, ImageDraw

from plugins.base_plugin.base_plugin import BasePlugin
from utils.app_utils import get_font

# Hardcoded locale data for Latin-script languages commonly used by the InkyPi
# community (hobbyists/tech in Europe and Americas). Jost font supports accented chars.
LOCALE_DATA = {
    "da": {
        "months": ["Januar", "Februar", "Marts", "April", "Maj", "Juni",
                    "Juli", "August", "September", "Oktober", "November", "December"],
        "weekdays": ["Mandag", "Tirsdag", "Onsdag", "Torsdag", "Fredag", "Lørdag", "Søndag"],
    },
    "de": {
        "months": ["Januar", "Februar", "März", "April", "Mai", "Juni",
                    "Juli", "August", "September", "Oktober", "November", "Dezember"],
        "weekdays": ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"],
    },
    "en": {
        "months": ["January", "February", "March", "April", "May", "June",
                    "July", "August", "September", "October", "November", "December"],
        "weekdays": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    },
    "es": {
        "months": ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"],
        "weekdays": ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"],
    },
    "fr": {
        "months": ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
                    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"],
        "weekdays": ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"],
    },
    "it": {
        "months": ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
                    "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"],
        "weekdays": ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"],
    },
    "nb": {
        "months": ["Januar", "Februar", "Mars", "April", "Mai", "Juni",
                    "Juli", "August", "September", "Oktober", "November", "Desember"],
        "weekdays": ["Mandag", "Tirsdag", "Onsdag", "Torsdag", "Fredag", "Lørdag", "Søndag"],
    },
    "nl": {
        "months": ["Januari", "Februari", "Maart", "April", "Mei", "Juni",
                    "Juli", "Augustus", "September", "Oktober", "November", "December"],
        "weekdays": ["Maandag", "Dinsdag", "Woensdag", "Donderdag", "Vrijdag", "Zaterdag", "Zondag"],
    },
    "pt": {
        "months": ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
                    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"],
        "weekdays": ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"],
    },
    "sv": {
        "months": ["Januari", "Februari", "Mars", "April", "Maj", "Juni",
                    "Juli", "Augusti", "September", "Oktober", "November", "December"],
        "weekdays": ["Måndag", "Tisdag", "Onsdag", "Torsdag", "Fredag", "Lördag", "Söndag"],
    },
}


class CalendarCardPlugin(BasePlugin):
    def generate_image(self, settings, device_config):
        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]
        width, height = dimensions

        today = datetime.datetime.now()

        language = str(settings.get("language") or "en").strip().lower()
        locale = LOCALE_DATA.get(language, LOCALE_DATA["en"])

        month = locale["months"][today.month - 1].upper()
        weekday = locale["weekdays"][today.weekday()]
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
