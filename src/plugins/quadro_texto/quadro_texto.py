"""
quadro_texto.py — Main entry point for the Quadro Texto InkyPi plugin.

Generates a visual reminder card using Pillow only (no HTML, no APIs).
Supports 10 layouts × 9 themes × 7 font packs with anti-repetition state.
"""

import logging
import random
import sys
import os

# Allow imports from plugin directory
_plugin_dir = os.path.dirname(os.path.abspath(__file__))
if _plugin_dir not in sys.path:
    sys.path.insert(0, _plugin_dir)

from plugins.base_plugin.base_plugin import BasePlugin
from PIL import Image, ImageDraw

from themes       import THEMES, THEME_NAMES
from fonts        import FONT_PACKS, FONT_PACK_NAMES, load_font
from layouts      import LAYOUTS, LAYOUT_NAMES
from illustrations import get_clock_fn, get_door_fn, get_border_fn
import state as state_mod

logger = logging.getLogger(__name__)

# ── All possible random combination keys ──────────────────────────────────────
_BORDER_STYLES = ["rounded", "double", "blueprint", "none"]
_DIV_STYLES    = ["solid", "dashed", "double"]
_ICON_STYLES   = ["clean", "doodle"]

def _all_combinations():
    combos = []
    for lay in LAYOUT_NAMES:
        for th in THEME_NAMES:
            for fp in FONT_PACK_NAMES:
                for bs in _BORDER_STYLES:
                    for ic in _ICON_STYLES:
                        combos.append(f"{lay}|{th}|{fp}|{bs}|{ic}")
    return combos

_ALL_COMBOS = _all_combinations()


class QuadroTexto(BasePlugin):

    def generate_image(self, settings, device_config):
        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]
        w, h = dimensions

        texts = {
            "top_text":    settings.get("top_text",    "Para contar"),
            "main_text":   settings.get("main_text",   "2h extras"),
            "bottom_text": settings.get("bottom_text", "Você sai às"),
            "time_text":   settings.get("time_text",   "19h"),
        }

        layout_key    = settings.get("layout",     "random")
        theme_key     = settings.get("theme",      "random")
        font_pack_key = settings.get("font_pack",  "random")
        border_style  = settings.get("border_style", "random")
        icon_style    = settings.get("icon_style",  "random")

        show_border  = settings.get("show_border",   "true") != "false"
        show_icons   = settings.get("show_icons",    "true") != "false"
        show_divider = settings.get("show_divider",  "true") != "false"
        prevent_rpt  = settings.get("prevent_repeat_last", "true") != "false"

        # ── Resolve random values (with anti-repeat when all are random) ──────
        all_random = (layout_key == "random" and theme_key == "random"
                      and font_pack_key == "random")

        if all_random and prevent_rpt:
            plugin_dir = self.get_plugin_dir()
            sig = state_mod.pick_combination(plugin_dir, _ALL_COMBOS)
            parts = sig.split("|")
            layout_key, theme_key, font_pack_key, border_style, icon_style = parts
        else:
            if layout_key    == "random": layout_key    = random.choice(LAYOUT_NAMES)
            if theme_key     == "random": theme_key     = random.choice(THEME_NAMES)
            if font_pack_key == "random": font_pack_key = random.choice(FONT_PACK_NAMES)
            if border_style  == "random": border_style  = random.choice(_BORDER_STYLES)
            if icon_style    == "random": icon_style    = random.choice(_ICON_STYLES)

            if prevent_rpt:
                sig = f"{layout_key}|{theme_key}|{font_pack_key}|{border_style}|{icon_style}"
                state_mod.record_fixed(self.get_plugin_dir(), sig)

        theme  = THEMES.get(theme_key, THEMES["black_white"])
        layout_fn = LAYOUTS.get(layout_key, LAYOUTS["split"])

        # font loader bound to chosen pack + canvas height
        def lf(role):
            return load_font(font_pack_key, role, h)

        illu = {
            "clock_fn":  get_clock_fn(icon_style),
            "door_fn":   get_door_fn(icon_style),
            "border_fn": get_border_fn(border_style if show_border else "none"),
        }

        opts = {
            "show_border":  show_border,
            "show_icons":   show_icons,
            "show_divider": show_divider,
        }

        img  = Image.new("RGB", (w, h), theme.get("bg", theme.get("top_bg", (255, 255, 255))))
        draw = ImageDraw.Draw(img)

        try:
            layout_fn(img, draw, w, h, texts, theme, lf, illu, opts)
        except Exception as e:
            logger.error(f"quadro_texto: layout '{layout_key}' failed: {e}", exc_info=True)
            raise RuntimeError(f"Erro ao renderizar layout '{layout_key}': {e}")

        return img
