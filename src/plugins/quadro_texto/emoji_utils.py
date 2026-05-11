"""
emoji_utils.py — Decorative emoji helpers for Quadro Texto.

Emoji rendering is intentionally resilient:
    - prefers Twemoji PNG assets loaded directly into PIL (no emoji font needed)
    - falls back to SVG rasterization when cairosvg is available
    - falls back to a monochrome token badge if download/rasterization is unavailable
    - never raises an error that breaks card rendering
"""

from __future__ import annotations

import logging
import os
import random
from io import BytesIO
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from dependencies import HAS_CAIROSVG
from utils.http_client import get_http_session
from utils.app_utils import resolve_path
import state as state_mod
from emoji_layout import choose_best_emoji_position, calculate_adaptive_emoji_size

logger = logging.getLogger(__name__)


def _unique_emojis(items):
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


TWEMOJI_RELEASE = "14.0.2"
TWEMOJI_BASE_URL = f"https://cdn.jsdelivr.net/gh/twitter/twemoji@{TWEMOJI_RELEASE}/assets/svg"
TWEMOJI_PNG_BASE_URL = f"https://cdn.jsdelivr.net/gh/twitter/twemoji@{TWEMOJI_RELEASE}/assets/72x72"


ALLOWED_EMOJIS = _unique_emojis([
    "😀", "😃", "😄", "😁", "😆", "😅", "🙂", "😊", "😇", "🥳",
    "🙂", "😐", "😶", "😑", "🤔", "🧐", "🤓", "😌", "🙄", "😏",
    "🎮", "🎲", "🎉", "🎈", "🍕", "🍔", "🌭", "🍟", "🎬", "🎥",
    "🤡", "👽", "👻", "💀", "👹", "👺", "🤖", "👾", "🥸", "💩",
    "🤓", "🧐", "💻", "📈", "🎯", "🚀", "🧠", "🕹️", "⏳", "📊",
    "✈️", "🌍", "🌞", "🚀", "🗺️", "🎒", "🏝️", "🌄", "🌌", "🧭",
])

_TOKEN_GROUPS = {
    ":)": {"😀", "😃", "😄", "😁", "😆", "😅", "🙂", "😊", "😇", "🥳"},
    "?": {"😐", "😶", "😑", "🤔", "🧐", "🤓", "😌", "🙄", "😏"},
    "FUN": {"🎮", "🎲", "🎉", "🎈", "🍕", "🍔", "🌭", "🍟", "🎬", "🎥"},
    "ODD": {"🤡", "👽", "👻", "💀", "👹", "👺", "🤖", "👾", "🥸", "💩"},
    "DEV": {"💻", "📈", "🎯", "🚀", "🧠", "🕹️", "⏳", "📊"},
    "TRIP": {"✈️", "🌍", "🌞", "🗺️", "🎒", "🏝️", "🌄", "🌌", "🧭"},
}


_WARNED_TWEMOJI = False


def choose_random_emoji(plugin_dir: str, emoji_mode: str, fixed_emoji: str | None,
                        prevent_repeat_emoji: bool = True) -> str | None:
    """Resolve emoji according to config, with optional non-repetition."""
    mode = str(emoji_mode or "random").strip().lower()
    fixed = str(fixed_emoji or "").strip()

    if mode == "none":
        return None

    if mode == "fixed":
        if fixed and fixed in ALLOWED_EMOJIS:
            if prevent_repeat_emoji:
                state_mod.record_emoji(plugin_dir, fixed)
            return fixed
        logger.warning(
            "quadro_texto: fixed_emoji '%s' is not in the allowed emoji list. Falling back to random.",
            fixed,
        )
        mode = "random"

    if mode == "random":
        if prevent_repeat_emoji:
            return state_mod.pick_emoji(plugin_dir, ALLOWED_EMOJIS)
        chosen = random.choice(ALLOWED_EMOJIS)
        state_mod.record_emoji(plugin_dir, chosen)
        return chosen

    logger.warning("quadro_texto: unknown emoji_mode '%s'. Emoji disabled.", mode)
    return None


def _fallback_token(emoji: str) -> str:
    for token, items in _TOKEN_GROUPS.items():
        if emoji in items:
            return token
    return "*"


def _emoji_to_twemoji_url(emoji: str) -> str:
    codepoints = "-".join(f"{ord(c):x}" for c in emoji if ord(c) != 0xFE0F)
    return f"{TWEMOJI_BASE_URL}/{codepoints}.svg"


def _emoji_to_twemoji_png_url(emoji: str) -> str:
    codepoints = "-".join(f"{ord(c):x}" for c in emoji if ord(c) != 0xFE0F)
    return f"{TWEMOJI_PNG_BASE_URL}/{codepoints}.png"


@lru_cache(maxsize=128)
def _fetch_twemoji_png(emoji: str) -> bytes | None:
    global _WARNED_TWEMOJI

    url = _emoji_to_twemoji_png_url(emoji)
    try:
        resp = get_http_session().get(url, timeout=10)
        resp.raise_for_status()
        return resp.content
    except Exception as exc:
        if not _WARNED_TWEMOJI:
            logger.warning(
                "quadro_texto: failed to fetch Twemoji PNG '%s': %s. %s",
                url,
                exc,
                "Trying SVG fallback." if HAS_CAIROSVG else "Using fallback badges.",
            )
            _WARNED_TWEMOJI = True
        return None


@lru_cache(maxsize=128)
def _fetch_twemoji_svg(emoji: str) -> bytes | None:
    global _WARNED_TWEMOJI
    if not HAS_CAIROSVG:
        if not _WARNED_TWEMOJI:
            logger.warning(
                "Optional dependency cairosvg is not installed. Emoji will use monochrome fallback badges."
            )
            _WARNED_TWEMOJI = True
        return None

    url = _emoji_to_twemoji_url(emoji)
    try:
        resp = get_http_session().get(url, timeout=10)
        resp.raise_for_status()
        return resp.content
    except Exception as exc:
        if not _WARNED_TWEMOJI:
            logger.warning(
                "quadro_texto: failed to fetch Twemoji asset '%s': %s. Using fallback badges.",
                url,
                exc,
            )
            _WARNED_TWEMOJI = True
        return None


@lru_cache(maxsize=256)
def _render_twemoji_rgba(emoji: str, size_px: int) -> Image.Image | None:
    png_bytes = _fetch_twemoji_png(emoji)
    if png_bytes:
        try:
            png = Image.open(BytesIO(png_bytes)).convert("RGBA")
            return png.resize((size_px, size_px), Image.LANCZOS)
        except Exception as exc:
            logger.warning(
                "quadro_texto: failed to decode Twemoji PNG '%s': %s. Trying SVG fallback.",
                emoji,
                exc,
            )

    svg_bytes = _fetch_twemoji_svg(emoji)
    if not svg_bytes:
        return None
    try:
        import cairosvg

        png_bytes = cairosvg.svg2png(
            bytestring=svg_bytes,
            output_width=size_px,
            output_height=size_px,
        )
        return Image.open(BytesIO(png_bytes)).convert("RGBA")
    except Exception as exc:
        logger.warning(
            "quadro_texto: failed to rasterize Twemoji '%s': %s. Using fallback badge.",
            emoji,
            exc,
        )
        return None


def get_available_emoji_font(size_px: int) -> ImageFont.FreeTypeFont | None:
    """Compatibility shim retained for callers; font rendering is no longer preferred."""
    return None


def _get_fallback_font(size_px: int):
    path = resolve_path(os.path.join("static", "fonts", "Jost-SemiBold.ttf"))
    try:
        return ImageFont.truetype(path, max(10, size_px))
    except Exception:
        return ImageFont.load_default()


def _emoji_size_px(size_name: str, w: int, h: int, illustration_style: str = "") -> int:
    """Resolve emoji pixel size from setting name.

    Sizes (at 800×480):
      small   ≈ 40 px  — subtle accent
      medium  ≈ 60 px  — balanced decoration
      large   ≈ 96 px  — featured visual element
      random  — picks medium or large each render
    """
    name = str(size_name or "medium").strip().lower()
    if name == "random":
        name = random.choice(["medium", "medium", "large"])

    short = min(w, h)
    base = {
        "small":  max(38, int(short * 0.100)),   # ~48 px at 480
        "medium": max(58, int(short * 0.150)),   # ~72 px at 480
        "large":  max(86, int(short * 0.240)),   # ~115 px at 480
    }.get(name, max(58, int(short * 0.150)))

    # Slight boost for artistic hand-drawn styles
    if illustration_style in ("doodle", "sketch", "cartoon", "sticker"):
        base = int(base * 1.10)
    return base



def draw_emoji(
    img,
    draw: ImageDraw.ImageDraw,
    emoji: str | None,
    layout_key: str,
    theme: dict,
    illustration_style: str,
    emoji_size: str = "medium",
    emoji_position: str = "random",
    show_icons: bool = True,
    show_border: bool = True,
) -> bool:
    """Render a decorative emoji centred within the layout's best free zone.

    Rendering chain:
      1. Twemoji SVG → rasterise with cairosvg → paste RGBA onto card
      2. Monochrome token badge (fallback when network / cairosvg unavailable)
    Returns True if anything was drawn.
    """
    if not emoji:
        return False

    w, h = img.size
    opts = {"show_border": show_border, "show_icons": show_icons}

    # ── Resolve size ──────────────────────────────────────────────────────────
    if str(emoji_size).strip().lower() == "adaptive":
        # First probe the best zone to get its dimensions, then derive size.
        _, _, zone_id = choose_best_emoji_position(
            layout_key, "adaptive", w, h, 0, opts
        )
        size_px = calculate_adaptive_emoji_size(layout_key, w, h, zone_id)
        effective_position = "adaptive"
    else:
        size_px = _emoji_size_px(emoji_size, w, h, illustration_style)
        effective_position = emoji_position

    # ── Resolve centre point ──────────────────────────────────────────────────
    cx, cy, zone_id = choose_best_emoji_position(
        layout_key, effective_position, w, h, size_px, opts
    )

    # ── Attempt Twemoji render ────────────────────────────────────────────────
    twemoji = _render_twemoji_rgba(emoji, size_px)
    if twemoji is not None:
        try:
            tw, th = twemoji.size
            bx = cx - tw // 2
            by = cy - th // 2
            if img.mode == "RGBA":
                img.alpha_composite(twemoji, (bx, by))
            else:
                img.paste(twemoji, (bx, by), twemoji)
            return True
        except Exception as exc:
            logger.warning("quadro_texto: Twemoji paste failed for '%s': %s", emoji, exc)

    # ── Monochrome fallback badge ─────────────────────────────────────────────
    token = _fallback_token(emoji)
    fallback_font = _get_fallback_font(max(12, int(size_px * 0.40)))
    try:
        bbox = draw.textbbox((0, 0), token, font=fallback_font)
        tw_b, th_b = bbox[2] - bbox[0], bbox[3] - bbox[1]
    except Exception:
        tw_b = max(20, int(size_px * 0.72))
        th_b = max(16, int(size_px * 0.48))

    pad_x = max(8, int(size_px * 0.20))
    pad_y = max(6, int(size_px * 0.14))
    bw = tw_b + pad_x * 2
    bh = th_b + pad_y * 2
    bx0 = cx - bw // 2
    by0 = cy - bh // 2
    bx1 = bx0 + bw
    by1 = by0 + bh

    fill = theme.get("mid_bg", theme.get("bg", (235, 235, 235)))
    outline = theme.get("accent", theme.get("border", (25, 25, 25)))
    text_color = theme.get("top_text", (15, 15, 15))
    radius = max(8, int(bh * 0.45))

    try:
        draw.rounded_rectangle([bx0, by0, bx1, by1], radius=radius,
                                fill=fill, outline=outline, width=2)
    except Exception:
        draw.rectangle([bx0, by0, bx1, by1], fill=fill, outline=outline, width=2)

    draw.text((cx, cy), token, font=fallback_font, fill=text_color, anchor="mm")
    return True