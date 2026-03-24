import random
import logging
from datetime import datetime
from plugins.base_plugin.base_plugin import BasePlugin

logger = logging.getLogger(__name__)

TWEMOJI_BASE_URL = "https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/svg"


def _emoji_to_twemoji_url(emoji):
    """Convert a Unicode emoji string to a Twemoji CDN SVG URL."""
    codepoints = "-".join(
        f"{ord(c):x}" for c in emoji if ord(c) != 0xFE0F
    )
    return f"{TWEMOJI_BASE_URL}/{codepoints}.svg"


def _get_smart_mood():
    """Select a mood based on current time and day of week with weighted probabilities.
    
    Returns a dict with:
    - mood: selected mood key
    - time_period: morning/afternoon/evening/night
    - weekday_name: Monday/Tuesday/etc
    - selected_weight: weight value of chosen mood
    """
    now = datetime.now()
    hour = now.hour
    weekday = now.weekday()  # 0=Monday, 6=Sunday
    
    # For late night hours (00:00-04:59), use previous day for weekday-based weighting
    # to make mood selection feel more natural for late night usage
    if hour < 5:
        weekday = (weekday - 1) % 7
    
    weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekday_name = weekday_names[weekday]
    
    # Determine time period
    if 5 <= hour < 12:
        time_period = "morning"
    elif 12 <= hour < 17:
        time_period = "afternoon"
    elif 17 <= hour < 21:
        time_period = "evening"
    else:
        time_period = "night"
    
    # Base weight of 1 for all moods
    mood_weights = {
        "happy": 1,
        "neutral": 1,
        "low_energy": 1,
        "stress": 1,
        "fun": 1,
        "weird": 1,
        "focus": 1,
        "adventure": 1,
        "love": 1,
        "sick": 1,
    }
    
    # Incrementally adjust weights based on time period (+1 or +2)
    if time_period == "morning":
        mood_weights["focus"] += 2
        mood_weights["happy"] += 1
        mood_weights["neutral"] += 1
    elif time_period == "afternoon":
        mood_weights["focus"] += 2
        mood_weights["neutral"] += 1
        mood_weights["stress"] += 1
    elif time_period == "evening":
        mood_weights["fun"] += 2
        mood_weights["love"] += 1
        mood_weights["low_energy"] += 1
    else:  # night
        mood_weights["low_energy"] += 2
        mood_weights["weird"] += 1
        mood_weights["neutral"] += 1
    
    # Incrementally adjust weights based on weekday (+1 or +2)
    # For late night (00:00-04:59), weekday is already adjusted to previous day above
    if weekday == 0:  # Monday
        mood_weights["focus"] += 2
        mood_weights["stress"] += 1
    elif weekday == 4:  # Friday
        mood_weights["happy"] += 2
        mood_weights["fun"] += 1
    elif weekday == 5:  # Saturday
        mood_weights["fun"] += 2
        mood_weights["adventure"] += 1
        mood_weights["love"] += 1
    elif weekday == 6:  # Sunday
        mood_weights["low_energy"] += 1
        mood_weights["love"] += 1
        mood_weights["neutral"] += 1
    
    # Small random boost for all moods to keep variety and avoid rigid patterns
    for mood in mood_weights:
        mood_weights[mood] += random.random() * 0.3
    
    # Select mood using weighted random choice
    moods = list(mood_weights.keys())
    weights = [mood_weights[mood] for mood in moods]
    selected_mood = random.choices(moods, weights=weights, k=1)[0]
    selected_weight = mood_weights[selected_mood]
    
    return {
        "mood": selected_mood,
        "time_period": time_period,
        "weekday_name": weekday_name,
        "selected_weight": round(selected_weight, 1),
    }

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

        # Determine behavior setting (default: random)
        behavior_value = "random"
        if isinstance(settings, dict):
            behavior_value = str(settings.get("behavior") or "random").lower()

        # Variable to store mood selection info for debug
        mood_info = None

        if mode_key == "random":
            # Mode is Random, so use Behavior to decide how to select a mood
            if behavior_value == "smart":
                mood_info = _get_smart_mood()
                mood_key = mood_info["mood"]
            else:
                # Random behavior: equal probability for all moods
                mood_key = random.choice(list(MOOD_DATA.keys()))
                # Create mood_info dict for consistency
                now = datetime.now()
                weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                weekday_name = weekday_names[now.weekday()]
                mood_info = {
                    "mood": mood_key,
                    "time_period": "N/A",
                    "weekday_name": weekday_name,
                    "selected_weight": "equal",
                }
        else:
            # Mode is set to a specific mood, ignore Behavior and use that mood
            mood_key = mode_key if mode_key in MOOD_DATA else random.choice(list(MOOD_DATA.keys()))
            # Create mood_info dict for consistency
            now = datetime.now()
            weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            weekday_name = weekday_names[now.weekday()]
            mood_info = {
                "mood": mood_key,
                "time_period": "N/A",
                "weekday_name": weekday_name,
                "selected_weight": "fixed",
            }

        mood = MOOD_DATA[mood_key]

        emoji = random.choice(mood["emojis"])
        caption = random.choice(mood["captions"])
        # Debug: append full debug info to caption
        caption = f"{caption} - {mood_info['mood']} - {mood_info['weekday_name']} - {mood_info['time_period']} - {mood_info['selected_weight']}"

        # Extract primary (text) and secondary (background) colors from settings
        primary_color = "#000000"  # default: black
        secondary_color = "#ffffff"  # default: white
        if isinstance(settings, dict):
            primary_color = settings.get("primaryColor") or "#000000"
            secondary_color = settings.get("secondaryColor") or "#ffffff"

        # Caption style: 'normal' (show caption) or 'minimal' (hide caption)
        caption_style = "normal"
        show_caption = True
        if isinstance(settings, dict):
            caption_style = str(settings.get("captionStyle") or "normal").lower()
            show_caption = (caption_style == "normal")

        template_params = {
            "emoji": emoji,
            "twemoji_url": _emoji_to_twemoji_url(emoji),
            "caption": caption,
            "primaryColor": primary_color,
            "secondaryColor": secondary_color,
            "plugin_settings": settings,
            "show_caption": show_caption,
        }

        image = self.render_image(
            dimensions, "emoji_mood.html", "emoji_mood.css", template_params
        )
        return image
