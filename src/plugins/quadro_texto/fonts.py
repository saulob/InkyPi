"""
fonts.py — Font packs for Quadro Texto plugin.

Each pack defines size multipliers and font names for:
  label_font   : small label text (top_text / bottom_text)
  value_font   : large bold text  (main_text / time_text)
  sub_font     : medium secondary / decorator text

Available local fonts (InkyPi static/fonts/):
  Jost          regular + SemiBold (clean geometric sans)
  Napoli        normal              (serif / editorial)
  Dogica        pixel + bold        (retro pixel)
  DS-DIGI       normal              (digital / LCD)

size_label / size_value / size_sub are multipliers relative to canvas height.
"""

import os
from PIL import ImageFont
from utils.app_utils import resolve_path

# ── Size multipliers (× display height) ────────────────────────────────────────
FONT_PACKS = {
    "bold_clean": {
        "label":  ("Jost",    0.072, "normal"),
        "value":  ("Jost",    0.200, "bold"),
        "sub":    ("Jost",    0.058, "normal"),
    },
    "geometric": {
        "label":  ("Jost",    0.065, "normal"),
        "value":  ("Jost",    0.215, "bold"),
        "sub":    ("Jost",    0.052, "bold"),
    },
    "rounded": {
        "label":  ("Jost",    0.070, "normal"),
        "value":  ("Jost",    0.195, "bold"),
        "sub":    ("Jost",    0.060, "normal"),
    },
    "condensed": {
        "label":  ("Jost",    0.058, "bold"),
        "value":  ("Jost",    0.230, "bold"),
        "sub":    ("Jost",    0.045, "normal"),
    },
    "editorial": {
        "label":  ("Napoli",  0.065, "normal"),
        "value":  ("Napoli",  0.195, "normal"),
        "sub":    ("Napoli",  0.050, "normal"),
    },
    "technical": {
        "label":  ("DS-Digital", 0.060, "normal"),
        "value":  ("DS-Digital", 0.200, "normal"),
        "sub":    ("DS-Digital", 0.048, "normal"),
    },
    "pixel": {
        "label":  ("Dogica",  0.052, "normal"),
        "value":  ("Dogica",  0.130, "bold"),
        "sub":    ("Dogica",  0.040, "normal"),
    },
}

FONT_PACK_NAMES = list(FONT_PACKS.keys())


def load_font(pack_name: str, role: str, h: int):
    """Return a PIL ImageFont for the given pack + role at canvas height h.

    role: 'label' | 'value' | 'sub'
    Falls back to default if font not available.
    """
    pack = FONT_PACKS.get(pack_name, FONT_PACKS["bold_clean"])
    font_name, mult, weight = pack[role]
    size = max(10, int(h * mult))

    font_map = {
        "Jost":       {"normal": "Jost.ttf", "bold": "Jost-SemiBold.ttf"},
        "Napoli":     {"normal": "Napoli.ttf", "bold": "Napoli.ttf"},
        "Dogica":     {"normal": "dogicapixel.ttf", "bold": "dogicapixelbold.ttf"},
        "DS-Digital": {"normal": os.path.join("DS-DIGI", "DS-DIGI.TTF"),
                       "bold":   os.path.join("DS-DIGI", "DS-DIGI.TTF")},
    }
    file_name = font_map.get(font_name, {}).get(weight, "Jost.ttf")
    path = resolve_path(os.path.join("static", "fonts", file_name))
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()
