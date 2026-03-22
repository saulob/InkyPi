import random
import logging
from plugins.base_plugin.base_plugin import BasePlugin

logger = logging.getLogger(__name__)

MOOD_DATA = {
    "happy": {
        "emojis": [
            "\U0001F600", "\U0001F603", "\U0001F604", "\U0001F601",
            "\U0001F606", "\U0001F605", "\U0001F642", "\U0001F643",
            "\U0001F609", "\U0001F60A", "\U0001F607", "\U0001F60D",
            "\U0001F618", "\U0001F60B", "\U0001F61C", "\U0001F92A",
            "\U0001F917", "\U0001F60E", "\U0001F973",
        ],
        "captions": [
            "Good vibes today",
            "Feeling bright",
            "A cheerful moment",
            "Smile mode on",
        ],
    },
    "neutral": {
        "emojis": [
            "\U0001F642", "\U0001F60A", "\U0001F609", "\U0001F610",
            "\U0001F636", "\U0001F611", "\U0001F914", "\U0001F9D0",
            "\U0001F913", "\U0001F60C", "\U0001F644", "\U0001F60F",
            "\U0001F62C", "\U0001F62E", "\U0001F62F", "\U0001F632",
            "\U0001F928", "\U0001F607", "\U0001F643", "\U0001F60E",
        ],
        "captions": [
            "Just cruising",
            "Steady and calm",
            "Nothing dramatic today",
            "Balanced mood",
        ],
    },
    "low_energy": {
        "emojis": [
            "\U0001F634", "\U0001F62A", "\U0001F60C", "\U0001F614",
            "\U0001F615", "\U0001F641", "\u2639\uFE0F", "\U0001F61E",
            "\U0001F61F", "\U0001F613", "\U0001F625", "\U0001F636",
            "\U0001F610", "\U0001F611", "\U0001F612", "\U0001F614",
            "\U0001F62A", "\U0001F634", "\U0001F60C", "\U0001F615",
        ],
        "captions": [
            "Take it slow",
            "Quiet energy today",
            "Easy pace",
            "Recharge mode",
        ],
    },
    "stress": {
        "emojis": [
            "\U0001F624", "\U0001F620", "\U0001F621", "\U0001F623",
            "\U0001F616", "\U0001F62B", "\U0001F629", "\U0001F62C",
            "\U0001F635", "\U0001F635\u200D\U0001F4AB", "\U0001F630",
            "\U0001F628", "\U0001F631", "\U0001F633", "\U0001F613",
            "\U0001F625", "\U0001F644", "\U0001F92F", "\U0001F624",
            "\U0001F620",
        ],
        "captions": [
            "A lot going on",
            "Take a breath",
            "Messy but moving",
            "One step at a time",
        ],
    },
}


class EmojiMood(BasePlugin):
    def generate_image(self, settings, device_config):
        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]

        mood_key = random.choice(list(MOOD_DATA.keys()))
        mood = MOOD_DATA[mood_key]

        emoji = random.choice(mood["emojis"])
        caption = random.choice(mood["captions"])

        template_params = {
            "emoji": emoji,
            "caption": caption,
            "plugin_settings": settings,
        }

        image = self.render_image(
            dimensions, "emoji_mood.html", "emoji_mood.css", template_params
        )
        return image
