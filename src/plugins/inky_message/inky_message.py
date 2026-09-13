import html
import logging
import re
from datetime import datetime
from html.parser import HTMLParser

import pytz

from plugins.base_plugin.base_plugin import BasePlugin

logger = logging.getLogger(__name__)

BASE_FONT_SIZE_RATIO = 0.14

FONT_SIZE_RATIOS = {
    "small": 0.55,
    "medium": 0.75,
    "large": 1.0,
    "extra-large": 1.35,
}

FONT_TAG_SIZES = {
    "1": "small",
    "2": "small",
    "3": "medium",
    "4": "medium",
    "5": "large",
    "6": "large",
    "7": "extra-large",
}

DEFAULT_TIME_FORMAT = "12h"
UNSAFE_TAGS = {"base", "embed", "iframe", "link", "meta", "object", "script", "style"}
MARKUP_PATTERN = re.compile(r"<\s*/?\s*[a-z][^>]*>", re.IGNORECASE)


class _MessageHTMLSanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.output = []
        self.stack = []
        self.drop_depth = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if self.drop_depth:
            if tag in UNSAFE_TAGS:
                self.drop_depth += 1
            return
        if tag in UNSAFE_TAGS:
            self.drop_depth = 1
            return

        emitted_tag = None
        if tag in {"p", "div", "strong", "b", "em", "i", "u"}:
            emitted_tag = "strong" if tag == "b" else "em" if tag == "i" else tag
            self.output.append(f"<{emitted_tag}>")
        elif tag == "br":
            self.output.append("<br>")
        elif tag == "span":
            size = self._attribute(attrs, "data-inky-size")
            if size in FONT_SIZE_RATIOS:
                emitted_tag = "span"
                self.output.append(f'<span data-inky-size="{size}">')
        elif tag == "font":
            size = FONT_TAG_SIZES.get(self._attribute(attrs, "size"))
            if size:
                emitted_tag = "span"
                self.output.append(f'<span data-inky-size="{size}">')

        self.stack.append((tag, emitted_tag))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if self.drop_depth:
            if tag in UNSAFE_TAGS:
                self.drop_depth -= 1
            return

        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] != tag:
                continue
            closing_tags = self.stack[index:]
            del self.stack[index:]
            for _, emitted_tag in reversed(closing_tags):
                if emitted_tag:
                    self.output.append(f"</{emitted_tag}>")
            return

    def handle_data(self, data):
        if not self.drop_depth:
            self.output.append(html.escape(data, quote=False))

    def handle_comment(self, data):
        return

    def _attribute(self, attrs, name):
        for attribute_name, value in attrs:
            if attribute_name.lower() == name:
                return value
        return None

    def get_html(self):
        for _, emitted_tag in reversed(self.stack):
            if emitted_tag:
                self.output.append(f"</{emitted_tag}>")
        return "".join(self.output)


def sanitize_message_html(value):
    """Return only the editor's supported markup and escaped text."""
    if value is None:
        return ""

    value = str(value).replace("\r\n", "\n").replace("\r", "\n")
    if not value:
        return ""

    if not MARKUP_PATTERN.search(value):
        return html.escape(value, quote=False).replace("\n", "<br>")

    parser = _MessageHTMLSanitizer()
    parser.feed(value)
    parser.close()
    return parser.get_html()


def _as_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def format_timestamp(current_datetime, time_format=DEFAULT_TIME_FORMAT, today=None):
    if time_format == "24h":
        time_text = current_datetime.strftime("%H:%M")
    else:
        time_text = current_datetime.strftime("%I:%M %p").lstrip("0")

    reference_date = today or current_datetime.date()
    if current_datetime.date() == reference_date:
        date_text = "Today"
    else:
        date_text = f"{current_datetime.strftime('%b')} {current_datetime.day},"
    return f"{date_text} {time_text}"


def _get_local_datetime(device_config):
    timezone_name = device_config.get_config("timezone") or "UTC"
    try:
        timezone = pytz.timezone(str(timezone_name))
    except (AttributeError, ValueError, pytz.UnknownTimeZoneError):
        timezone = pytz.UTC
    return datetime.now(timezone)


class InkyMessage(BasePlugin):
    def generate_settings_template(self):
        template_params = super().generate_settings_template()
        template_params["style_settings"] = False
        return template_params

    def generate_image(self, settings, device_config):
        settings = settings or {}
        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]

        message_html = sanitize_message_html(settings.get("message"))
        show_timestamp = _as_bool(settings.get("showTimestamp"), default=True)
        timestamp = ""
        if show_timestamp:
            current_datetime = _get_local_datetime(device_config)
            time_format = device_config.get_config("time_format") or DEFAULT_TIME_FORMAT
            timestamp = format_timestamp(current_datetime, time_format)

        base_font_size = max(1, round(min(dimensions) * BASE_FONT_SIZE_RATIO))
        render_settings = {
            "selectedFrame": "None",
            "backgroundOption": "color",
            "backgroundColor": "#ffffff",
            "textColor": "#000000",
            "topMargin": "0",
            "bottomMargin": "0",
            "leftMargin": "0",
            "rightMargin": "0",
        }

        template_params = {
            "message_html": message_html,
            "base_font_size": base_font_size,
            "show_timestamp": show_timestamp,
            "timestamp": timestamp,
            "plugin_settings": render_settings,
        }

        image = self.render_image(dimensions, "inky_message.html", "inky_message.css", template_params)
        if not image:
            logger.error("Failed to render Inky Message image")
            raise RuntimeError("Failed to render message, please check logs.")
        return image