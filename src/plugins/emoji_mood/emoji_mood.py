import random
import logging
from plugins.base_plugin.base_plugin import BasePlugin

logger = logging.getLogger(__name__)

TWEMOJI_BASE_URL = "https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/svg"


def _emoji_to_twemoji_url(emoji):
    """Convert a Unicode emoji string to a Twemoji CDN SVG URL."""
    codepoints = "-".join(
        f"{ord(c):x}" for c in emoji if ord(c) != 0xFE0F
    )
    return f"{TWEMOJI_BASE_URL}/{codepoints}.svg"

MOOD_DATA = {
    "happy": {
        "emojis": [
            "😀", "😃", "😄", "😁", "😆", "😅", "🙂", "😊", "😇", "🥳",
        ],
        "captions": [
            "Good vibes today",
            "Feeling bright",
            "A cheerful moment",
            "Smile mode on",
            "Everything feels right",
            "Light and easy day",
            "Positive energy",
            "Keep smiling",
            "Good mood activated",
            "Today is a good day",
        ],
    },
    "neutral": {
        "emojis": [
            "🙂", "😐", "😶", "😑", "🤔", "🧐", "🤓", "😌", "🙄", "😏",
        ],
        "captions": [
            "Just cruising",
            "Steady and calm",
            "Nothing dramatic today",
            "Balanced mood",
            "Taking it easy",
            "All good, no rush",
            "Simple day ahead",
            "Calm and collected",
            "Neutral vibes",
            "Going with the flow",
        ],
    },
    "low_energy": {
        "emojis": [
            "😴", "😪", "😌", "😔", "😕", "😞", "😟", "😓", "😥", "🫠",
        ],
        "captions": [
            "Take it slow",
            "Quiet energy today",
            "Easy pace",
            "Recharge mode",
            "Low battery vibes",
            "Rest a bit more",
            "Slow but steady",
            "Take a break",
            "Energy saving mode",
            "Just getting through",
        ],
    },
    "stress": {
        "emojis": [
            "😤", "😠", "😡", "😣", "😖", "😫", "😩", "🤯", "😵", "😵‍💫",
        ],
        "captions": [
            "A lot going on",
            "Take a breath",
            "Messy but moving",
            "One step at a time",
            "Too much today",
            "Keep pushing",
            "Stay strong",
            "Breathe and focus",
            "Handling chaos",
            "Survive and move",
        ],
    },
    "fun": {
        "emojis": [
            "🎮", "🎲", "🎉", "🎈", "🍕", "🍔", "🌭", "🍟", "🎬", "🎥",
        ],
        "captions": [
            "Time to have fun",
            "Play mode on",
            "Enjoy the moment",
            "Just for fun",
            "Take a break and play",
            "Good time ahead",
            "Relax and enjoy",
            "Fun vibes only",
            "Let loose a bit",
            "Today is for fun",
        ],
    },
    "weird": {
        "emojis": [
            "🤡", "👽", "👻", "💀", "👹", "👺", "🤖", "👾", "🥸", "💩",
        ],
        "captions": [
            "Feeling weird today",
            "Something is off",
            "Strange vibes",
            "Not a normal day",
            "Embrace the chaos",
            "A bit unusual",
            "Weird but okay",
            "Glitch in the mood",
            "Unexpected energy",
            "Just roll with it",
        ],
    },
    "sick": {
        "emojis": [
            "🤢", "🤮", "😷", "🤒", "🤕", "🥴", "😵", "🤧", "🥶", "🥵",
        ],
        "captions": [
            "Not feeling great",
            "Take care today",
            "Rest and recover",
            "Slow down and heal",
            "Body needs a break",
            "Easy day today",
            "Take it easy",
            "Recovery mode",
            "Be gentle with yourself",
            "Time to rest",
        ],
    },
    "focus": {
        "emojis": [
            "🤓", "🧐", "💻", "📈", "🎯", "🚀", "🧠", "🕹️", "⏳", "📊",
        ],
        "captions": [
            "Focus mode on",
            "Time to get things done",
            "Locked in",
            "Deep work time",
            "Stay sharp",
            "No distractions",
            "Get in the zone",
            "Productive day ahead",
            "Eyes on the goal",
            "Let’s build something",
        ],
    },
    "adventure": {
        "emojis": [
            "✈️", "🌍", "🌞", "🚀", "🗺️", "🎒", "🏝️", "🌄", "🌌", "🧭",
        ],
        "captions": [
            "Ready for adventure",
            "Explore something new",
            "Let’s go somewhere",
            "New horizons today",
            "Break the routine",
            "Adventure awaits",
            "Time to explore",
            "Go beyond",
            "Try something different",
            "See the world",
        ],
    },
    "love": {
        "emojis": [
            "❤️", "💖", "💘", "💞", "🥰", "😍", "😘", "😽", "💕", "❤️‍🔥",
        ],
        "captions": [
            "Love is in the air",
            "Feeling the love",
            "Heart full today",
            "Spread some love",
            "Warm and happy",
            "Sweet vibes",
            "Love mode on",
            "All about love",
            "Good feelings inside",
            "Share the love",
        ],
    },
}


class EmojiMood(BasePlugin):
    def generate_image(self, settings, device_config):
        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]

        # Determine selected mode from plugin settings
        # settings can come from the UI as strings; accept 'mode' or 'Mode' keys
        mode_value = None
        if isinstance(settings, dict):
            mode_value = settings.get("mode") or settings.get("Mode")
        if not mode_value:
            mode_value = "random"

        mode_key = str(mode_value).lower()

        if mode_key == "random":
            mood_key = random.choice(list(MOOD_DATA.keys()))
        else:
            # if the selected mode exists as a mood key, use it; otherwise default to random
            mood_key = mode_key if mode_key in MOOD_DATA else random.choice(list(MOOD_DATA.keys()))

        mood = MOOD_DATA[mood_key]

        emoji = random.choice(mood["emojis"])
        caption = random.choice(mood["captions"])
        # Debug: append chosen mood key to the caption so it's visible in renders
        caption = f"{caption} - {mood_key}"

        # Extract primary (text) and secondary (background) colors from settings
        primary_color = "#000000"  # default: black
        secondary_color = "#ffffff"  # default: white
        if isinstance(settings, dict):
            primary_color = settings.get("primaryColor") or "#000000"
            secondary_color = settings.get("secondaryColor") or "#ffffff"

        template_params = {
            "emoji": emoji,
            "twemoji_url": _emoji_to_twemoji_url(emoji),
            "caption": caption,
            "primaryColor": primary_color,
            "secondaryColor": secondary_color,
            "plugin_settings": settings,
        }

        image = self.render_image(
            dimensions, "emoji_mood.html", "emoji_mood.css", template_params
        )
        return image
