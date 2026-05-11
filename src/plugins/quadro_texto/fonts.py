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
    Handwritten   auto-detected handwritten candidate with safe fallback

size_label / size_value / size_sub are multipliers relative to canvas height.
"""

import os
from dataclasses import dataclass
from PIL import ImageFont
from utils.app_utils import resolve_path


_HANDWRITTEN_CANDIDATES = [
    # Prefer true handwritten families if present in future deployments.
    "PatrickHand-Regular.ttf",
    "Kalam-Regular.ttf",
    "Caveat-Regular.ttf",
    "GloriaHallelujah-Regular.ttf",
    "NanumPenScript-Regular.ttf",
    # Current repo fallback candidates.
    "Napoli.ttf",
    "Jost.ttf",
]


def _pick_handwritten_file() -> str:
    """Return best available handwritten-ish font file in static/fonts."""
    for candidate in _HANDWRITTEN_CANDIDATES:
        p = resolve_path(os.path.join("static", "fonts", candidate))
        if os.path.exists(p):
            return candidate
    return "Jost.ttf"

# ── Size multipliers (× display height) ────────────────────────────────────────
FONT_PACKS = {
    "bold_clean": {
        "label":  ("Jost",    0.086, "normal"),
        "value":  ("Jost",    0.200, "bold"),
        "sub":    ("Jost",    0.070, "normal"),
    },
    "geometric": {
        "label":  ("Jost",    0.078, "normal"),
        "value":  ("Jost",    0.215, "bold"),
        "sub":    ("Jost",    0.062, "bold"),
    },
    "rounded": {
        "label":  ("Jost",    0.084, "normal"),
        "value":  ("Jost",    0.195, "bold"),
        "sub":    ("Jost",    0.072, "normal"),
    },
    "condensed": {
        "label":  ("Jost",    0.070, "bold"),
        "value":  ("Jost",    0.230, "bold"),
        "sub":    ("Jost",    0.054, "normal"),
    },
    "editorial": {
        "label":  ("Napoli",  0.078, "normal"),
        "value":  ("Napoli",  0.195, "normal"),
        "sub":    ("Napoli",  0.060, "normal"),
    },
    "technical": {
        "label":  ("DS-Digital", 0.072, "normal"),
        "value":  ("DS-Digital", 0.200, "normal"),
        "sub":    ("DS-Digital", 0.058, "normal"),
    },
    "handwritten": {
        "label":  ("Handwritten", 0.089, "normal"),
        # Keep the main value highly legible on e-paper.
        "value":  ("Jost",        0.198, "bold"),
        "sub":    ("Handwritten", 0.072, "normal"),
    },
    "pixel": {
        "label":  ("Dogica",  0.062, "normal"),
        "value":  ("Dogica",  0.130, "bold"),
        "sub":    ("Dogica",  0.048, "normal"),
    },
}

FONT_PACK_NAMES = list(FONT_PACKS.keys())


_MISSING_GLYPH = "\u0378"


@dataclass(frozen=True)
class ResolvedFont:
    font: object
    missing_signature: tuple[tuple[int, int], bytes]


@dataclass(frozen=True)
class FontStack:
    primary: ResolvedFont
    fallbacks: tuple[ResolvedFont, ...] = ()


def _mask_signature(font, text: str) -> tuple[tuple[int, int], bytes]:
    mask = font.getmask(text)
    return (mask.size, bytes(mask))


def _build_resolved_font(file_name: str, size: int) -> ResolvedFont:
    path = resolve_path(os.path.join("static", "fonts", file_name))
    font = ImageFont.truetype(path, size)
    return ResolvedFont(font=font, missing_signature=_mask_signature(font, _MISSING_GLYPH))


def _build_default_font() -> ResolvedFont:
    font = ImageFont.load_default()
    return ResolvedFont(font=font, missing_signature=_mask_signature(font, _MISSING_GLYPH))


def _supports_char(font_entry: ResolvedFont, char: str) -> bool:
    if not char or char.isspace():
        return True
    return _mask_signature(font_entry.font, char) != font_entry.missing_signature


def resolve_text_font(font_obj, text: str):
    """Pick a concrete PIL font that can render the full text.

    Some decorative fonts bundled with the plugin do not include Portuguese
    accented glyphs. In those cases, fall back to a Jost variant for the whole
    string so labels remain readable on hardware.
    """
    if not isinstance(font_obj, FontStack):
        return font_obj

    text = str(text or "")
    for candidate in (font_obj.primary, *font_obj.fallbacks):
        if all(_supports_char(candidate, char) for char in text):
            return candidate.font
    return font_obj.primary.font


def load_font(pack_name: str, role: str, h: int):
    """Return a PIL ImageFont for the given pack + role at canvas height h.

    role: 'label' | 'value' | 'sub'
    Falls back to a Jost variant when the chosen decorative font does not cover
    the requested text (for example, Portuguese accents).
    """
    pack = FONT_PACKS.get(pack_name, FONT_PACKS["bold_clean"])
    font_name, mult, weight = pack[role]
    size = max(10, int(h * mult))

    font_map = {
        "Jost":       {"normal": "Jost.ttf", "bold": "Jost-SemiBold.ttf"},
        "Napoli":     {"normal": "Napoli.ttf", "bold": "Napoli.ttf"},
        "Dogica":     {"normal": "dogicapixel.ttf", "bold": "dogicapixelbold.ttf"},
        "Handwritten": {"normal": _pick_handwritten_file(), "bold": _pick_handwritten_file()},
        "DS-Digital": {"normal": os.path.join("DS-DIGI", "DS-DIGI.TTF"),
                       "bold":   os.path.join("DS-DIGI", "DS-DIGI.TTF")},
    }
    file_name = font_map.get(font_name, {}).get(weight, "Jost.ttf")

    fallback_files = []
    preferred_fallback = "Jost-SemiBold.ttf" if role == "value" or weight == "bold" else "Jost.ttf"
    for candidate in (preferred_fallback, "Jost.ttf", "Jost-SemiBold.ttf"):
        if candidate != file_name and candidate not in fallback_files:
            fallback_files.append(candidate)

    try:
        primary = _build_resolved_font(file_name, size)
    except Exception:
        primary = None

    fallbacks = []
    for candidate in fallback_files:
        try:
            fallbacks.append(_build_resolved_font(candidate, size))
        except Exception:
            continue

    if primary is None:
        if fallbacks:
            return FontStack(primary=fallbacks[0], fallbacks=tuple(fallbacks[1:]))
        return FontStack(primary=_build_default_font())

    return FontStack(primary=primary, fallbacks=tuple(fallbacks))
