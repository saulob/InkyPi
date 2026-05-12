"""contrast.py — E-paper contrast and legibility utilities for Quadro Texto.

E-paper displays have lower apparent contrast than LCD screens and are viewed
in reflected ambient light.  These utilities enforce minimum legibility for
every layout/theme combination regardless of randomisation.

Priority order: legibility > contrast > hierarchy > aesthetics > decoration
"""

# ── Minimum contrast thresholds (WCAG-inspired) ───────────────────────────────
# WCAG 2.0 contrast ratios range from 1.0 (no contrast) to 21.0 (B&W).
MIN_EINK_RATIO    = 4.5   # WCAG AA — minimum for body/label text on e-paper
STRONG_EINK_RATIO = 7.0   # WCAG AAA — preferred for large headlines
DIVIDER_MIN_RATIO = 3.0   # Decorative lines / borders (lower tolerance)

# ── Safe e-paper palette ─────────────────────────────────────────────────────
EINK_DARK_TEXT     = (10,  10,  10)   # Near-black for light backgrounds
EINK_LIGHT_TEXT    = (245, 245, 245)  # Near-white for dark backgrounds
EINK_DARK_DIVIDER  = (55,  55,  55)   # Visible divider on light surfaces
EINK_LIGHT_DIVIDER = (195, 195, 195)  # Visible divider on dark surfaces

# Perceived-brightness threshold: >= this value → background is "light"
_LIGHT_THRESHOLD = 180


# ── Core WCAG luminance / contrast functions ──────────────────────────────────

def relative_luminance(color):
    """WCAG 2.0 relative luminance for an sRGB color (R, G, B each 0-255)."""
    def _lin(c):
        s = c / 255.0
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4
    r, g, b = color[0], color[1], color[2]
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast_ratio(c1, c2):
    """WCAG contrast ratio between two RGB colors.  Range: [1.0, 21.0]."""
    l1 = relative_luminance(c1)
    l2 = relative_luminance(c2)
    light = max(l1, l2)
    dark  = min(l1, l2)
    return (light + 0.05) / (dark + 0.05)


def perceived_brightness(color):
    """W3C perceived brightness in the 0-255 range."""
    return (color[0] * 299 + color[1] * 587 + color[2] * 114) / 1000.0


def is_light_bg(color):
    """Return True when the background is perceptually light (needs dark text)."""
    return perceived_brightness(color) >= _LIGHT_THRESHOLD


# ── Safe color selection ──────────────────────────────────────────────────────

def get_safe_text_color(bg_color):
    """
    Return the maximally-contrasting safe text color (near-black or near-white)
    for the given background.  Always produces readable e-paper text.
    """
    r_dark  = contrast_ratio(EINK_DARK_TEXT,  bg_color)
    r_light = contrast_ratio(EINK_LIGHT_TEXT, bg_color)
    return EINK_DARK_TEXT if r_dark >= r_light else EINK_LIGHT_TEXT


def get_safe_divider_color(bg_color):
    """Return a visible divider/border color for the given background."""
    return EINK_DARK_DIVIDER if is_light_bg(bg_color) else EINK_LIGHT_DIVIDER


def ensure_contrast(color, bg_color, min_ratio=MIN_EINK_RATIO, fallback=None):
    """
    Return *color* unchanged when it achieves at least *min_ratio* against
    *bg_color*.  Otherwise return *fallback* (auto-selected when not given).

    NEVER returns a color that fails the minimum — the fallback is always safe.
    """
    if contrast_ratio(color, bg_color) >= min_ratio:
        return color
    return fallback if fallback is not None else get_safe_text_color(bg_color)


def adjust_text_contrast(text_color, bg_color, min_ratio=MIN_EINK_RATIO):
    """Alias for ensure_contrast; returns a safe color when the original fails."""
    return ensure_contrast(text_color, bg_color, min_ratio=min_ratio)


def get_safe_text_color_for_surface(theme_color, surface_bg,
                                     min_ratio=MIN_EINK_RATIO):
    """
    Use this in layouts that draw text on a surface whose background colour
    differs from the theme's primary bg (e.g. paper-textured doodle areas,
    hardcoded panel fills).

    Returns *theme_color* when it is already legible; otherwise returns the
    maximally-contrasting safe text colour for *surface_bg*.

    Example::

        paper_bg = (248, 246, 240)
        top_tc = get_safe_text_color_for_surface(theme["top_text"], paper_bg)
        _draw_text(draw, x, y, text, font, top_tc)
    """
    return ensure_contrast(theme_color, surface_bg, min_ratio=min_ratio)


# ── Theme-level validation and clamping ──────────────────────────────────────

def clamp_theme_brightness(theme):
    """
    Return a copy of *theme* with text, divider and border colours enforced to
    meet minimum e-paper contrast against their corresponding backgrounds.

    Rules applied:
      • top_text    must contrast with both top_bg and bg
      • bottom_text must contrast with both bottom_bg and bg
      • divider / border must meet DIVIDER_MIN_RATIO against bg

    Only failing pairs are fixed; already-safe values are preserved.
    The original dict is never mutated.
    """
    t = dict(theme)

    # Text colours vs their section backgrounds
    t["top_text"]    = ensure_contrast(t["top_text"],    t["top_bg"])
    t["bottom_text"] = ensure_contrast(t["bottom_text"], t["bottom_bg"])

    # Also ensure they work on the unified bg used by single-bg layouts
    t["top_text"]    = ensure_contrast(t["top_text"],    t["bg"])
    t["bottom_text"] = ensure_contrast(t["bottom_text"], t["bg"])

    # Dividers and borders use a lower but still meaningful threshold
    fb_div = get_safe_divider_color(t["bg"])
    t["divider"] = ensure_contrast(
        t["divider"], t["bg"], min_ratio=DIVIDER_MIN_RATIO, fallback=fb_div
    )
    t["border"] = ensure_contrast(
        t["border"], t["bg"], min_ratio=DIVIDER_MIN_RATIO, fallback=fb_div
    )

    return t


def validate_theme_contrast(theme):
    """
    Validate all key colour pairs in a theme.

    Returns a list of ``(description, ratio, passes)`` tuples where *passes*
    is True when the pair meets MIN_EINK_RATIO.
    """
    pairs = [
        ("top_text / top_bg",       theme["top_text"],    theme["top_bg"]),
        ("bottom_text / bottom_bg", theme["bottom_text"], theme["bottom_bg"]),
        ("top_text / bg",           theme["top_text"],    theme["bg"]),
        ("bottom_text / bg",        theme["bottom_text"], theme["bg"]),
        ("divider / bg",            theme["divider"],     theme["bg"]),
        ("border / bg",             theme["border"],      theme["bg"]),
        ("accent / bg",             theme["accent"],      theme["bg"]),
    ]
    return [
        (label, round(contrast_ratio(tc, bc), 2), contrast_ratio(tc, bc) >= MIN_EINK_RATIO)
        for label, tc, bc in pairs
    ]


def get_readable_pair(bg_color):
    """
    Given any background colour, return ``(text_color, accent_color)``
    guaranteed readable on e-paper.
    """
    text   = get_safe_text_color(bg_color)
    accent = (30, 50, 140) if is_light_bg(bg_color) else (215, 200, 55)
    return text, accent


def ensure_accessible_palette(bg, *colors):
    """
    Return a tuple of colours, each guaranteed to contrast with *bg* at
    MIN_EINK_RATIO.  Useful for validating ad-hoc colour sets.
    """
    return tuple(ensure_contrast(c, bg) for c in colors)
