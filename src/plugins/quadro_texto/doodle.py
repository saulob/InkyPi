"""
doodle.py — Hand-drawn / sketch-style Pillow rendering helpers for Quadro Texto.

All functions draw directly on a PIL ImageDraw instance.
Each primitive adds controlled random jitter so it looks hand-drawn while
remaining clean and legible on e-paper displays at 800×480.

Optional libraries (detected via dependencies.py):
  aggdraw   — smoother anti-aliased curves and paths for doodle style
  cairosvg  — load_svg_icon() converts a local SVG to a PIL Image

Illustration styles dispatched in quadro_texto.py:
  clean    — standard Pillow geometric (from illustrations.py)
  doodle   — this module, wobbly lines + imperfect circles
  sketch   — heavier pencil feel; falls back to doodle without sketchify
  sticker  — speech bubbles, badges, thick marker strokes
  mixed    — randomly picks one of the above per element
  random   — like mixed but tracked in state.json for anti-repetition
"""

import logging
import math
import random as _rnd

from dependencies import HAS_AGGDRAW, HAS_CAIROSVG

logger = logging.getLogger(__name__)

# ── Jitter helpers ─────────────────────────────────────────────────────────────

def _j(n: float, amp: float = 2.5) -> float:
    """Add small Gaussian-ish jitter to a coordinate."""
    return n + _rnd.uniform(-amp, amp)


def _jpt(x: float, y: float, amp: float = 2.5):
    return (_j(x, amp), _j(y, amp))


def _jline(draw, pts, color, width=2, amp=2.5, segments=3):
    """Draw a wobbly polyline with jittered midpoints.

    If aggdraw is installed, uses anti-aliased paths for smoother curves.
    Falls back to Pillow line segments otherwise.
    """
    if len(pts) < 2:
        return

    expanded = [_jpt(*pts[0], amp)]
    for i in range(1, len(pts)):
        x0, y0 = pts[i - 1]
        x1, y1 = pts[i]
        for s in range(1, segments):
            t = s / segments
            expanded.append(_jpt(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, amp))
        expanded.append(_jpt(x1, y1, amp))

    if HAS_AGGDRAW:
        try:
            import aggdraw
            # aggdraw needs the underlying PIL image
            canvas = draw._image  # type: ignore[attr-defined]
            ctx = aggdraw.Draw(canvas)
            pen = aggdraw.Pen(color, width)
            flat = [coord for pt in expanded for coord in pt]
            ctx.path(flat, pen)  # type: ignore[attr-defined]
            ctx.flush()
            return
        except Exception:
            pass  # fall through to Pillow

    for a, b in zip(expanded, expanded[1:]):
        draw.line([a, b], fill=color, width=width)


# ── 1. Hand-drawn border ───────────────────────────────────────────────────────

def draw_handdrawn_border(draw, w, h, color, lw=3, amp=3.0):
    """Four wobbly lines forming a slightly imperfect rectangular border."""
    pad = lw + 4
    # top, bottom, left, right
    corners = [
        [(pad, pad), (w - pad, pad)],
        [(pad, h - pad), (w - pad, h - pad)],
        [(pad, pad), (pad, h - pad)],
        [(w - pad, pad), (w - pad, h - pad)],
    ]
    for seg in corners:
        _jline(draw, seg, color, width=lw, amp=amp, segments=6)


# ── 2. Wobbly horizontal / diagonal line ──────────────────────────────────────

def draw_wobbly_line(draw, x0, y0, x1, y1, color, lw=2, amp=2.5, segments=8):
    """A single wobbly line between two points."""
    _jline(draw, [(x0, y0), (x1, y1)], color, width=lw, amp=amp, segments=segments)


# ── 3. Marker highlight (filled band behind text) ─────────────────────────────

def draw_marker_highlight(draw, x, y, text_w, text_h, color, alpha_color=None, tilt=2):
    """Thick marker-style highlight band — slightly tilted parallelogram."""
    pad_x = int(text_h * 0.18)
    pad_y = int(text_h * 0.12)
    # Draw two overlapping thick rectangles with slight offset to simulate
    # a real marker stroke
    fill = alpha_color or color
    poly = [
        (_j(x - pad_x, 1.5),          _j(y - pad_y + tilt, 1.5)),
        (_j(x + text_w + pad_x, 1.5), _j(y - pad_y - tilt, 1.5)),
        (_j(x + text_w + pad_x, 1.5), _j(y + text_h + pad_y + tilt, 1.5)),
        (_j(x - pad_x, 1.5),          _j(y + text_h + pad_y - tilt, 1.5)),
    ]
    draw.polygon(poly, fill=fill)


# ── 4. Doodle arrow ───────────────────────────────────────────────────────────

def draw_doodle_arrow(draw, x0, y, x1, color, lw=3, amp=2.0):
    """Hand-drawn horizontal arrow with cartoon arrowhead."""
    # Shaft — wobbly line
    _jline(draw, [(x0, y), (x1, y)], color, width=lw, amp=amp, segments=5)
    # Arrowhead — two lines forming a V
    ah = lw + 4
    draw.line([(_j(x1, 1), _j(y, 1)), (_j(x1 - ah * 1.4, 1), _j(y - ah, 1))],
              fill=color, width=lw)
    draw.line([(_j(x1, 1), _j(y, 1)), (_j(x1 - ah * 1.4, 1), _j(y + ah, 1))],
              fill=color, width=lw)


# ── 5. Sketch clock ───────────────────────────────────────────────────────────

def draw_sketch_clock(draw, cx, cy, r, color):
    """Sketchy clock: imperfect outer circle, wobbly hands, hand-drawn ticks."""
    lw = max(2, r // 9)
    amp = max(1.5, r * 0.04)

    # Outer ring — two overlapping arcs for hand-drawn feel
    draw.arc([_j(cx - r, amp * 0.5), _j(cy - r, amp * 0.5),
              _j(cx + r, amp * 0.5), _j(cy + r, amp * 0.5)],
             start=5, end=185, fill=color, width=lw)
    draw.arc([_j(cx - r, amp * 0.5), _j(cy - r, amp * 0.5),
              _j(cx + r, amp * 0.5), _j(cy + r, amp * 0.5)],
             start=190, end=360, fill=color, width=max(1, lw - 1))

    # Tick marks
    for deg in (0, 90, 180, 270):
        a = math.radians(deg)
        x0 = cx + r * 0.78 * math.sin(a)
        y0 = cy - r * 0.78 * math.cos(a)
        x1 = cx + r * 0.93 * math.sin(a)
        y1 = cy - r * 0.93 * math.cos(a)
        _jline(draw, [(x0, y0), (x1, y1)], color, width=max(1, lw - 1), amp=amp, segments=2)

    # Hour hand ~ 10 o'clock
    ha = math.radians(-58)
    hl = r * 0.50
    _jline(draw, [(cx, cy), (cx + hl * math.sin(ha), cy - hl * math.cos(ha))],
           color, width=lw, amp=amp, segments=3)
    # Minute hand ~ 2 o'clock
    ma = math.radians(62)
    ml = r * 0.68
    _jline(draw, [(cx, cy), (cx + ml * math.sin(ma), cy - ml * math.cos(ma))],
           color, width=max(1, lw - 1), amp=amp * 0.8, segments=3)
    # Center dot
    cr = max(2, r // 8)
    draw.ellipse([_j(cx - cr, 1), _j(cy - cr, 1),
                  _j(cx + cr, 1), _j(cy + cr, 1)], fill=color)


# ── 6. Sketch door ────────────────────────────────────────────────────────────

def draw_sketch_door(draw, cx, cy, r, color):
    """Sketchy door: wobbly rectangle, hand-drawn knob, doodle arrow."""
    lw = max(2, r // 9)
    fw = int(r * 0.82)
    fh = int(r * 1.22)
    amp = max(1.5, r * 0.04)

    # Door frame — four wobbly lines
    tl = (cx - fw, cy - fh)
    tr = (cx + fw, cy - fh)
    bl = (cx - fw, cy + fh)
    br = (cx + fw, cy + fh)
    for seg in [(tl, tr), (tr, br), (br, bl), (bl, tl)]:
        _jline(draw, list(seg), color, width=lw, amp=amp, segments=4)

    # Knob — small wobbly circle
    hr = max(2, r // 8)
    hx = cx + int(fw * 0.40)
    draw.ellipse([_j(hx - hr, 1), _j(cy - hr, 1),
                  _j(hx + hr, 1), _j(cy + hr, 1)], fill=color)

    # Arrow
    ax0 = cx + fw + int(r * 0.20)
    ax1 = cx + fw + int(r * 0.65)
    draw_doodle_arrow(draw, ax0, cy, ax1, color, lw=lw, amp=amp * 0.7)


# ── 7. Speech bubble ──────────────────────────────────────────────────────────

def draw_speech_bubble(draw, x, y, w, h, color, tail="bottom-left", lw=2, fill=None):
    """Comic-style speech bubble with a tail.

    x, y  — top-left corner
    w, h  — bubble dimensions (rounded rectangle)
    tail  — one of: bottom-left, bottom-right, top-left, top-right
    """
    radius = int(min(w, h) * 0.18)
    amp = 1.5

    # Body
    if fill:
        try:
            draw.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=fill,
                                   outline=color, width=lw)
        except AttributeError:
            draw.rectangle([x, y, x + w, y + h], fill=fill, outline=color, width=lw)
    else:
        try:
            draw.rounded_rectangle([x, y, x + w, y + h], radius=radius,
                                   outline=color, width=lw)
        except AttributeError:
            draw.rectangle([x, y, x + w, y + h], outline=color, width=lw)

    # Tail
    tail_size = int(min(w, h) * 0.22)
    if tail == "bottom-left":
        tip = (_j(x + tail_size * 0.3, amp), _j(y + h + tail_size, amp))
        base_a = (_j(x + tail_size * 0.1, amp), _j(y + h - lw, amp))
        base_b = (_j(x + tail_size * 0.9, amp), _j(y + h - lw, amp))
    elif tail == "bottom-right":
        tip = (_j(x + w - tail_size * 0.3, amp), _j(y + h + tail_size, amp))
        base_a = (_j(x + w - tail_size * 0.9, amp), _j(y + h - lw, amp))
        base_b = (_j(x + w - tail_size * 0.1, amp), _j(y + h - lw, amp))
    elif tail == "top-left":
        tip = (_j(x + tail_size * 0.3, amp), _j(y - tail_size, amp))
        base_a = (_j(x + tail_size * 0.1, amp), _j(y + lw, amp))
        base_b = (_j(x + tail_size * 0.9, amp), _j(y + lw, amp))
    else:  # top-right
        tip = (_j(x + w - tail_size * 0.3, amp), _j(y - tail_size, amp))
        base_a = (_j(x + w - tail_size * 0.9, amp), _j(y + lw, amp))
        base_b = (_j(x + w - tail_size * 0.1, amp), _j(y + lw, amp))

    draw.polygon([base_a, base_b, tip], fill=fill or color, outline=color if fill else None)


# ── 8. Sticker badge ──────────────────────────────────────────────────────────

def draw_sticker_badge(draw, cx, cy, rw, rh, bg_color, border_color, lw=3, amp=2.0):
    """Irregular sticker-like oval badge with wobbly outline."""
    # Solid fill
    try:
        draw.rounded_rectangle([cx - rw, cy - rh, cx + rw, cy + rh],
                                radius=rh, fill=bg_color)
    except AttributeError:
        draw.ellipse([cx - rw, cy - rh, cx + rw, cy + rh], fill=bg_color)

    # Wobbly outline — approximate with many short arc segments
    steps = 32
    pts = []
    for i in range(steps + 1):
        angle = 2 * math.pi * i / steps
        # Ellipse point with jitter
        px = cx + (rw + _rnd.uniform(-amp, amp)) * math.cos(angle)
        py = cy + (rh + _rnd.uniform(-amp, amp)) * math.sin(angle)
        pts.append((px, py))
    for a, b in zip(pts, pts[1:]):
        draw.line([a, b], fill=border_color, width=lw)


# ── SVG icon support (optional) ───────────────────────────────────────────────

def load_svg_icon(svg_path: str, size: tuple):
    """Convert a local SVG file to a PIL RGBA Image.

    Requires cairosvg (detected via HAS_CAIROSVG). Returns None if unavailable
    or if the file cannot be read.

    Usage::

        icon = load_svg_icon("/path/to/clock.svg", (80, 80))
        if icon:
            img.paste(icon, (x, y), icon)
    """
    if not HAS_CAIROSVG:
        logger.debug("load_svg_icon: cairosvg not available, returning None.")
        return None
    try:
        import cairosvg
        from PIL import Image
        import io
        png_bytes = cairosvg.svg2png(
            url=svg_path,
            output_width=size[0],
            output_height=size[1],
        )
        return Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    except Exception as exc:
        logger.warning("load_svg_icon: failed to load '%s': %s", svg_path, exc)
        return None


# ── Style dispatch ─────────────────────────────────────────────────────────────

CLOCK_STYLES = {
    "clean":   None,   # use illustrations.draw_clock
    "doodle":  None,   # use illustrations.draw_clock_doodle
    "sketch":  draw_sketch_clock,
    "sticker": draw_sketch_clock,   # same fn, styling handled at call site
}

DOOR_STYLES = {
    "clean":   None,   # use illustrations.draw_door
    "doodle":  None,   # use illustrations.draw_door_doodle
    "sketch":  draw_sketch_door,
    "sticker": draw_sketch_door,
}

_CONCRETE_STYLES = ["clean", "doodle", "sketch", "sticker"]

ILLUSTRATION_STYLES = ["clean", "doodle", "sketch", "sticker", "mixed", "random"]


def get_illustration_clock_fn(style: str):
    """Return the clock draw function for the given illustration_style.

    For mixed/random the caller must resolve the style first.
    """
    from illustrations import draw_clock, draw_clock_doodle
    mapping = {
        "clean":   draw_clock,
        "doodle":  draw_clock_doodle,
        "sketch":  draw_sketch_clock,
        "sticker": draw_sketch_clock,
    }
    return mapping.get(style, draw_clock)


def get_illustration_door_fn(style: str):
    """Return the door draw function for the given illustration_style."""
    from illustrations import draw_door, draw_door_doodle
    mapping = {
        "clean":   draw_door,
        "doodle":  draw_door_doodle,
        "sketch":  draw_sketch_door,
        "sticker": draw_sketch_door,
    }
    return mapping.get(style, draw_door)


def resolve_illustration_style(raw_style: str, last_style: str = None) -> str:
    """Resolve 'mixed' or 'random' to a concrete style, applying dep fallbacks.

    Delegates to ``dependencies.resolve_illustration_style`` for fallback logic
    (sketch → doodle without sketchify, doodle → clean without aggdraw).
    For 'mixed' / 'random', picks a concrete style randomly.
    """
    from dependencies import resolve_illustration_style as _dep_resolve

    if raw_style in _CONCRETE_STYLES:
        return _dep_resolve(raw_style)

    # mixed / random / unknown → pick concrete, then apply dep fallback
    candidates = [s for s in _CONCRETE_STYLES if s != last_style]
    picked = _rnd.choice(candidates or _CONCRETE_STYLES)
    return _dep_resolve(picked)
