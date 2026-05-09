"""
dependencies.py — Optional dependency detection for the Quadro Texto plugin.

Import this module to know which rendering backends are available at runtime.
The plugin always works with Pillow alone; all other libraries enhance quality.

Flags
-----
HAS_AGGDRAW   : smoother curves, anti-aliased paths, better doodle rendering
HAS_CAIROSVG  : convert local SVG files to PIL images (SVG icon support)
HAS_DRAWSVG   : programmatic SVG generation via Python code
HAS_SKETCHIFY : advanced sketch / pencil image-processing effects

Usage
-----
    from dependencies import HAS_AGGDRAW, resolve_illustration_style
    if HAS_AGGDRAW:
        # use aggdraw paths
    else:
        # Pillow fallback
"""

import logging

logger = logging.getLogger(__name__)

# ── Try importing each optional library ───────────────────────────────────────

try:
    import aggdraw as _aggdraw       # noqa: F401
    HAS_AGGDRAW = True
except ImportError:
    HAS_AGGDRAW = False
    logger.warning(
        "Optional dependency 'aggdraw' is not installed. "
        "Doodle curves will use Pillow fallback (slightly less smooth)."
    )

try:
    import cairosvg as _cairosvg     # noqa: F401
    HAS_CAIROSVG = True
except ImportError:
    HAS_CAIROSVG = False
    logger.warning(
        "Optional dependency 'cairosvg' is not installed. "
        "SVG icons will use Pillow-drawn fallback."
    )

try:
    import drawsvg as _drawsvg       # noqa: F401
    HAS_DRAWSVG = True
except ImportError:
    HAS_DRAWSVG = False
    logger.warning(
        "Optional dependency 'drawsvg' is not installed. "
        "Vector SVG generation is disabled; Pillow drawing will be used."
    )

try:
    import sketchify as _sketchify   # noqa: F401
    HAS_SKETCHIFY = True
except ImportError:
    HAS_SKETCHIFY = False
    logger.warning(
        "Optional dependency 'sketchify' is not installed. "
        "Advanced sketch effects are disabled; doodle style will be used instead."
    )

# ── Public helpers ─────────────────────────────────────────────────────────────

def get_dependency_status() -> dict:
    """Return a dict mapping each dependency name to its availability.

    Example::

        {
            "Pillow":    True,
            "aggdraw":   False,
            "cairosvg":  True,
            "drawsvg":   False,
            "sketchify": False,
        }
    """
    try:
        from PIL import Image as _pil  # noqa: F401
        has_pillow = True
    except ImportError:
        has_pillow = False

    return {
        "Pillow":    has_pillow,
        "aggdraw":   HAS_AGGDRAW,
        "cairosvg":  HAS_CAIROSVG,
        "drawsvg":   HAS_DRAWSVG,
        "sketchify": HAS_SKETCHIFY,
    }


def get_missing_optional_dependencies() -> list:
    """Return a list of optional dependency names that are NOT installed.

    Example::

        ["aggdraw", "cairosvg", "sketchify"]
    """
    missing = []
    if not HAS_AGGDRAW:
        missing.append("aggdraw")
    if not HAS_CAIROSVG:
        missing.append("cairosvg")
    if not HAS_DRAWSVG:
        missing.append("drawsvg")
    if not HAS_SKETCHIFY:
        missing.append("sketchify")
    return missing


# ── Illustration-style fallback resolution ────────────────────────────────────

# Maps requested style → required dependency (None = always available)
_STYLE_DEPS = {
    "clean":   None,
    "doodle":  "aggdraw",   # nicer with aggdraw, falls back to clean without it
    "sketch":  "sketchify", # requires sketchify; falls back to doodle
    "sticker": None,        # uses only Pillow
    "mixed":   None,        # picks at runtime from available styles
    "random":  None,        # anti-repeat; resolved by state.pick_illustration_style
}

# Fallback chain: if a style's dependency is missing, use this instead
_FALLBACKS = {
    "sketch": "doodle",
    "doodle": "clean",
}


def resolve_illustration_style(requested: str) -> str:
    """Return the best available style for *requested*, applying fallbacks.

    - ``sketch`` without sketchify  → ``doodle``
    - ``doodle`` without aggdraw    → ``clean``
    - ``mixed`` / ``random``        → left for caller to resolve
    - ``clean`` / ``sticker``       → always available

    Logs a warning each time a fallback is applied.
    """
    # mixed / random are handled upstream (state.py or quadro_texto.py)
    if requested in ("mixed", "random"):
        return requested

    dep = _STYLE_DEPS.get(requested)
    flags = {
        "aggdraw":   HAS_AGGDRAW,
        "cairosvg":  HAS_CAIROSVG,
        "drawsvg":   HAS_DRAWSVG,
        "sketchify": HAS_SKETCHIFY,
    }

    style = requested
    visited = set()
    while dep and not flags.get(dep, True):
        if style in visited:
            # Break cycle
            style = "clean"
            break
        visited.add(style)
        fallback = _FALLBACKS.get(style, "clean")
        logger.warning(
            f"illustration_style '{style}' requires '{dep}' which is not installed. "
            f"Falling back to '{fallback}'."
        )
        style = fallback
        dep = _STYLE_DEPS.get(style)

    return style


def svg_icons_available() -> bool:
    """Return True if SVG→PIL conversion is available (cairosvg installed)."""
    return HAS_CAIROSVG


def log_startup_summary():
    """Log a one-time summary of available optional features at plugin load."""
    status = get_dependency_status()
    available   = [k for k, v in status.items() if v]
    unavailable = [k for k, v in status.items() if not v]

    if unavailable:
        logger.info(
            "quadro_texto: optional dependencies not installed: %s. "
            "Features requiring them will use Pillow fallbacks.",
            ", ".join(unavailable),
        )
    else:
        logger.info("quadro_texto: all optional dependencies available.")
