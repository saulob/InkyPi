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
from doodle import (
    get_illustration_clock_fn, get_illustration_door_fn,
    get_illustration_border_fn,
    resolve_illustration_style, ILLUSTRATION_STYLES,
)
import state as state_mod
import dependencies as deps_mod

# Log available optional features once at import time
deps_mod.log_startup_summary()

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


def _text_setting(settings, key, default):
    """Return a cleaned text setting, falling back when blank or None."""
    value = settings.get(key, default)
    if value is None:
        return default
    value = str(value).strip()
    return value or default


class QuadroTexto(BasePlugin):

    def generate_image(self, settings, device_config):
        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]
        w, h = dimensions

        texts = {
            "top_text":    _text_setting(settings, "top_text",    "Para contar"),
            "main_text":   _text_setting(settings, "main_text",   "2h extras"),
            "bottom_text": _text_setting(settings, "bottom_text", "Você sai às"),
            "time_text":   _text_setting(settings, "time_text",   "19h"),
        }

        layout_key    = settings.get("layout",     "random")
        theme_key     = settings.get("theme",      "random")
        font_pack_key = settings.get("font_pack",  "random")
        border_style  = settings.get("border_style", "random")
        icon_style    = settings.get("icon_style",  "random")
        illus_style   = settings.get("illustration_style", "random")
        jitter_raw    = settings.get("jitter_strength", "")

        show_border  = settings.get("show_border",   "true") != "false"
        show_icons   = settings.get("show_icons",    "true") != "false"
        show_divider = settings.get("show_divider",  "true") != "false"
        prevent_rpt  = settings.get("prevent_repeat_last", "true") != "false"

        jitter_strength = None
        if str(jitter_raw).strip().lower() not in ("", "auto", "none"):
            try:
                jitter_strength = float(jitter_raw)
                jitter_strength = max(2.0, min(5.0, jitter_strength))
            except (TypeError, ValueError):
                logger.warning(
                    "quadro_texto: invalid jitter_strength '%s', using auto.",
                    jitter_raw,
                )

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

        # ── Resolve illustration_style (new setting) ──────────────────────
        plugin_dir = self.get_plugin_dir()
        if illus_style == "random":
            illus_style = state_mod.pick_illustration_style(plugin_dir)
        elif illus_style == "mixed":
            illus_style = resolve_illustration_style("mixed")
        else:
            illus_style = resolve_illustration_style(illus_style)

        # Apply dependency-aware fallback (e.g. sketch→doodle without sketchify).
        illus_style = deps_mod.resolve_illustration_style(illus_style)

        # Pixel font does not pair well with hand-drawn styles.
        if illus_style in ("doodle", "sketch", "cartoon") and font_pack_key == "pixel":
            fallback_pack = "handwritten" if "handwritten" in FONT_PACKS else "rounded"
            logger.warning(
                "quadro_texto: font_pack 'pixel' is not recommended for illustration_style '%s'. "
                "Using '%s' instead.",
                illus_style,
                fallback_pack,
            )
            font_pack_key = fallback_pack

        # illustration_style overrides icon_style when set to a concrete value
        # (icon_style kept for backward compatibility)
        use_illus = illus_style in ("doodle", "sketch", "cartoon", "sticker")
        if use_illus:
            clock_fn = get_illustration_clock_fn(illus_style)
            door_fn  = get_illustration_door_fn(illus_style)
            border_fn = get_illustration_border_fn(illus_style) if show_border else get_border_fn("none")
        else:
            # fallback: use legacy icon_style (clean / doodle)
            effective_icon = illus_style if illus_style in ("clean", "doodle") else icon_style
            clock_fn = get_clock_fn(effective_icon)
            door_fn  = get_door_fn(effective_icon)
            border_fn = get_border_fn(border_style if show_border else "none")

        theme     = THEMES.get(theme_key, THEMES["black_white"])
        layout_fn = LAYOUTS.get(layout_key, LAYOUTS["split"])

        # font loader bound to chosen pack + canvas height
        def lf(role):
            return load_font(font_pack_key, role, h)

        illu = {
            "clock_fn":        clock_fn,
            "door_fn":         door_fn,
            "border_fn":       border_fn,
            "illustration_style": illus_style,
            "jitter_strength": jitter_strength,
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
