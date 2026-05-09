"""
doodle.py — Hand-drawn rendering helpers for Quadro Texto.

This module focuses on a believable "drawn by hand" style while keeping
everything readable on e-paper:
  - controlled jitter (auto-scaled to canvas or explicit 2..5 strength)
  - multi-pass sketch lines
  - imperfect circles / rectangles / rounded boxes
  - marker strokes and scribble underlines
  - subtle paper texture helper

Optional runtime enhancements:
  - aggdraw  : smoother anti-aliased path rendering
  - cairosvg : local SVG icon loading into PIL
"""

import io
import logging
import math
import random as _rnd

from dependencies import HAS_AGGDRAW, HAS_CAIROSVG

logger = logging.getLogger(__name__)

_MIN_JITTER = 2.0
_MAX_JITTER = 5.0


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _canvas_size(draw):
    try:
        return draw._image.size  # type: ignore[attr-defined]
    except Exception:
        return (800, 480)


def _resolve_jitter(draw, jitter_strength=None):
    """Return jitter in pixels, clamped to [2..5] for legibility on e-paper."""
    if jitter_strength is not None:
        try:
            return _clamp(float(jitter_strength), _MIN_JITTER, _MAX_JITTER)
        except (TypeError, ValueError):
            pass
    w, h = _canvas_size(draw)
    auto = max(w, h) / 320.0
    return _clamp(auto, _MIN_JITTER, _MAX_JITTER)


def _j(value, amp):
    return value + _rnd.uniform(-amp, amp)


def _draw_polyline(draw, points, color, width):
    """Draw polyline using aggdraw when available, else Pillow line segments."""
    if len(points) < 2:
        return

    if HAS_AGGDRAW:
        try:
            import aggdraw

            canvas = draw._image  # type: ignore[attr-defined]
            ctx = aggdraw.Draw(canvas)
            pen = aggdraw.Pen(color, max(1, int(width)))
            path = aggdraw.Path()
            path.moveto(*points[0])
            for px, py in points[1:]:
                path.lineto(px, py)
            ctx.path(path, pen)
            ctx.flush()
            return
        except Exception:
            pass

    for p0, p1 in zip(points, points[1:]):
        draw.line([p0, p1], fill=color, width=max(1, int(width)))


def _jittered_segment_points(x0, y0, x1, y1, jitter, segments=10, phase=None):
    phase = _rnd.random() * math.tau if phase is None else phase
    dx = x1 - x0
    dy = y1 - y0
    ln = max(1.0, math.hypot(dx, dy))
    nx, ny = -dy / ln, dx / ln

    pts = []
    for i in range(segments + 1):
        t = i / segments
        bx = x0 + dx * t
        by = y0 + dy * t
        wobble = math.sin((t * math.tau) + phase) * jitter * 0.42
        wobble += _rnd.uniform(-jitter, jitter) * 0.30
        if i == 0 or i == segments:
            wobble *= 0.20
        pts.append((bx + nx * wobble, by + ny * wobble))
    return pts


def _rounded_rect_points(x0, y0, x1, y1, radius, arc_steps=8):
    """Generate clockwise perimeter points for a rounded rectangle."""
    r = max(1, min(radius, int((x1 - x0) / 2), int((y1 - y0) / 2)))

    def arc(cx, cy, rr, a0, a1, steps):
        pts = []
        for i in range(steps + 1):
            t = i / steps
            a = a0 + (a1 - a0) * t
            pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
        return pts

    pts = []
    pts += [(x0 + r, y0), (x1 - r, y0)]
    pts += arc(x1 - r, y0 + r, r, -math.pi / 2, 0.0, arc_steps)
    pts += [(x1, y0 + r), (x1, y1 - r)]
    pts += arc(x1 - r, y1 - r, r, 0.0, math.pi / 2, arc_steps)
    pts += [(x1 - r, y1), (x0 + r, y1)]
    pts += arc(x0 + r, y1 - r, r, math.pi / 2, math.pi, arc_steps)
    pts += [(x0, y1 - r), (x0, y0 + r)]
    pts += arc(x0 + r, y0 + r, r, math.pi, 3 * math.pi / 2, arc_steps)
    return pts


# ── Required hand-drawn helpers ───────────────────────────────────────────────

def draw_jittered_line(
    draw,
    x0,
    y0,
    x1,
    y1,
    color,
    width=3,
    jitter_strength=None,
    passes=2,
    segments=10,
):
    jitter = _resolve_jitter(draw, jitter_strength)
    for p in range(max(1, passes)):
        local = jitter * (0.88 + p * 0.16)
        pts = _jittered_segment_points(x0, y0, x1, y1, local, segments=segments + p)
        _draw_polyline(draw, pts, color, max(1, width - (p // 2)))


def draw_jittered_rectangle(
    draw,
    x0,
    y0,
    x1,
    y1,
    color,
    width=3,
    jitter_strength=None,
    passes=2,
):
    draw_jittered_line(
        draw, x0, y0, x1, y0, color, width=width,
        jitter_strength=jitter_strength, passes=passes, segments=8
    )
    draw_jittered_line(
        draw, x1, y0, x1, y1, color, width=width,
        jitter_strength=jitter_strength, passes=passes, segments=8
    )
    draw_jittered_line(
        draw, x1, y1, x0, y1, color, width=width,
        jitter_strength=jitter_strength, passes=passes, segments=8
    )
    draw_jittered_line(
        draw, x0, y1, x0, y0, color, width=width,
        jitter_strength=jitter_strength, passes=passes, segments=8
    )


def draw_jittered_rounded_rectangle(
    draw,
    x0,
    y0,
    x1,
    y1,
    radius,
    color,
    width=3,
    jitter_strength=None,
    passes=2,
):
    jitter = _resolve_jitter(draw, jitter_strength)
    base = _rounded_rect_points(x0, y0, x1, y1, radius, arc_steps=8)
    for p in range(max(1, passes)):
        local = jitter * (0.65 + 0.15 * p)
        noisy = [(_j(px, local * 0.55), _j(py, local * 0.55)) for px, py in base]
        noisy.append(noisy[0])
        _draw_polyline(draw, noisy, color, max(1, width - (p // 2)))


def draw_handdrawn_circle(
    draw,
    cx,
    cy,
    r,
    color,
    width=3,
    jitter_strength=None,
    passes=2,
):
    jitter = _resolve_jitter(draw, jitter_strength)
    steps = 44
    for p in range(max(1, passes)):
        local = jitter * (0.58 + p * 0.18)
        pts = []
        for i in range(steps + 1):
            t = i / steps
            a = t * math.tau
            rr = r + _rnd.uniform(-local, local)
            x = cx + rr * math.cos(a)
            y = cy + rr * math.sin(a)
            pts.append((x, y))
        _draw_polyline(draw, pts, color, max(1, width - (p // 2)))


def draw_handdrawn_arrow(
    draw,
    x0,
    y0,
    x1,
    y1,
    color,
    width=3,
    jitter_strength=None,
):
    jitter = _resolve_jitter(draw, jitter_strength)
    draw_jittered_line(
        draw, x0, y0, x1, y1, color, width=width,
        jitter_strength=jitter, passes=2, segments=8
    )

    ang = math.atan2(y1 - y0, x1 - x0)
    head = max(8, width * 3)
    for da in (math.pi - 0.62, math.pi + 0.62):
        hx = x1 + head * math.cos(ang + da)
        hy = y1 + head * math.sin(ang + da)
        draw_jittered_line(
            draw, x1, y1, hx, hy, color,
            width=max(1, width - 1), jitter_strength=jitter * 0.8,
            passes=1, segments=5,
        )


def draw_marker_stroke(
    draw,
    x0,
    y0,
    x1,
    y1,
    color,
    width=14,
    jitter_strength=None,
):
    jitter = _resolve_jitter(draw, jitter_strength)
    band = max(2, int(width * 0.22))
    for off in (-band, 0, band):
        draw_jittered_line(
            draw, x0, y0 + off, x1, y1 + off, color,
            width=max(2, int(width * 0.62)),
            jitter_strength=jitter * 0.45,
            passes=1,
            segments=7,
        )


def draw_scribble_underline(
    draw,
    x0,
    y,
    x1,
    color,
    width=3,
    jitter_strength=None,
):
    jitter = _resolve_jitter(draw, jitter_strength)
    draw_jittered_line(
        draw, x0, y, x1, y, color,
        width=width, jitter_strength=jitter * 0.55, passes=2, segments=10
    )
    draw_jittered_line(
        draw, x0 + 2, y + max(1, width), x1 - 2, y + max(1, width), color,
        width=max(1, width - 1), jitter_strength=jitter * 0.40, passes=1, segments=9
    )


def draw_double_sketch_border(
    draw,
    w,
    h,
    color,
    width=3,
    jitter_strength=None,
    gap=9,
):
    jitter = _resolve_jitter(draw, jitter_strength)
    outer_pad = width + 3
    draw_jittered_rectangle(
        draw,
        outer_pad,
        outer_pad,
        w - outer_pad,
        h - outer_pad,
        color,
        width=width,
        jitter_strength=jitter,
        passes=2,
    )
    inner = outer_pad + max(5, gap)
    draw_jittered_rectangle(
        draw,
        inner,
        inner,
        w - inner,
        h - inner,
        color,
        width=max(1, width - 1),
        jitter_strength=max(_MIN_JITTER, jitter * 0.75),
        passes=2,
    )


def draw_handdrawn_clock(draw, cx, cy, r, color, jitter_strength=None):
    lw = max(2, int(r / 8))
    jitter = _resolve_jitter(draw, jitter_strength)
    draw_handdrawn_circle(
        draw, cx, cy, r, color, width=lw, jitter_strength=jitter * 0.7, passes=2
    )

    for deg in (0, 90, 180, 270):
        a = math.radians(deg)
        x0 = cx + r * 0.76 * math.sin(a)
        y0 = cy - r * 0.76 * math.cos(a)
        x1 = cx + r * 0.93 * math.sin(a)
        y1 = cy - r * 0.93 * math.cos(a)
        draw_jittered_line(
            draw, x0, y0, x1, y1, color,
            width=max(1, lw - 1), jitter_strength=jitter * 0.55, passes=1, segments=4
        )

    ha = math.radians(-56)
    ma = math.radians(60)
    hl = r * 0.48
    ml = r * 0.68
    draw_jittered_line(
        draw, cx, cy, cx + hl * math.sin(ha), cy - hl * math.cos(ha), color,
        width=lw, jitter_strength=jitter * 0.6, passes=2, segments=5
    )
    draw_jittered_line(
        draw, cx, cy, cx + ml * math.sin(ma), cy - ml * math.cos(ma), color,
        width=max(1, lw - 1), jitter_strength=jitter * 0.55, passes=1, segments=6
    )

    c = max(2, r // 8)
    draw_handdrawn_circle(
        draw, cx, cy, c, color, width=max(1, lw - 1), jitter_strength=jitter * 0.35, passes=1
    )


def draw_handdrawn_door(draw, cx, cy, r, color, jitter_strength=None):
    lw = max(2, int(r / 8))
    jitter = _resolve_jitter(draw, jitter_strength)
    fw = int(r * 0.84)
    fh = int(r * 1.20)

    draw_jittered_rounded_rectangle(
        draw,
        cx - fw,
        cy - fh,
        cx + fw,
        cy + fh,
        radius=max(4, int(r * 0.24)),
        color=color,
        width=lw,
        jitter_strength=jitter * 0.7,
        passes=2,
    )

    draw_jittered_line(
        draw,
        cx - int(fw * 0.15),
        cy - int(fh * 0.78),
        cx - int(fw * 0.15),
        cy + int(fh * 0.80),
        color,
        width=max(1, lw - 1),
        jitter_strength=jitter * 0.45,
        passes=1,
        segments=8,
    )

    kr = max(2, int(r * 0.14))
    kx = cx + int(fw * 0.33)
    draw_handdrawn_circle(
        draw, kx, cy, kr, color,
        width=max(1, lw - 1), jitter_strength=jitter * 0.45, passes=1
    )

    ax0 = cx + fw + int(r * 0.16)
    ax1 = cx + fw + int(r * 0.70)
    draw_handdrawn_arrow(
        draw, ax0, cy, ax1, cy, color,
        width=max(2, lw), jitter_strength=jitter * 0.65,
    )


def draw_paper_texture(draw, w, h, base_color=(248, 246, 240), density=0.0016, strength=10):
    """Paint an off-white paper background with subtle grain points."""
    draw.rectangle([0, 0, w, h], fill=base_color)
    count = max(120, int(w * h * density))
    for _ in range(count):
        x = _rnd.randint(0, w - 1)
        y = _rnd.randint(0, h - 1)
        delta = _rnd.randint(-strength, strength)
        c = (
            _clamp(base_color[0] + delta, 0, 255),
            _clamp(base_color[1] + delta, 0, 255),
            _clamp(base_color[2] + delta, 0, 255),
        )
        draw.point((x, y), fill=c)


# ── Backward-compatible helper names ─────────────────────────────────────────

def draw_handdrawn_border(draw, w, h, color, lw=3, amp=None):
    draw_double_sketch_border(draw, w, h, color, width=lw, jitter_strength=amp)


def draw_wobbly_line(draw, x0, y0, x1, y1, color, lw=2, amp=2.5, segments=8):
    draw_jittered_line(
        draw, x0, y0, x1, y1, color,
        width=lw, jitter_strength=amp, passes=2, segments=segments
    )


def draw_marker_highlight(draw, x, y, text_w, text_h, color, alpha_color=None, tilt=2):
    fill = alpha_color or color
    draw_marker_stroke(
        draw,
        x - int(text_h * 0.12), y + text_h * 0.45,
        x + text_w + int(text_h * 0.12), y + text_h * 0.45,
        fill,
        width=max(8, int(text_h * 0.7)),
        jitter_strength=2.2,
    )


def draw_doodle_arrow(draw, x0, y, x1, color, lw=3, amp=2.0):
    draw_handdrawn_arrow(draw, x0, y, x1, y, color, width=lw, jitter_strength=amp)


def draw_sketch_clock(draw, cx, cy, r, color):
    draw_handdrawn_clock(draw, cx, cy, r, color, jitter_strength=3.0)


def draw_sketch_door(draw, cx, cy, r, color):
    draw_handdrawn_door(draw, cx, cy, r, color, jitter_strength=3.0)


def draw_speech_bubble(draw, x, y, w, h, color, tail="bottom-left", lw=2, fill=None):
    radius = int(min(w, h) * 0.20)
    if fill:
        draw.rectangle([x + 2, y + 2, x + w - 2, y + h - 2], fill=fill)
    draw_jittered_rounded_rectangle(
        draw,
        x,
        y,
        x + w,
        y + h,
        radius=radius,
        color=color,
        width=max(2, lw),
        jitter_strength=2.4,
        passes=2,
    )

    tail_size = int(min(w, h) * 0.20)
    if tail == "bottom-left":
        a = (x + int(tail_size * 0.2), y + h)
        b = (x + int(tail_size * 1.1), y + h)
        tip = (x + int(tail_size * 0.4), y + h + tail_size)
    elif tail == "bottom-right":
        a = (x + w - int(tail_size * 1.1), y + h)
        b = (x + w - int(tail_size * 0.2), y + h)
        tip = (x + w - int(tail_size * 0.4), y + h + tail_size)
    elif tail == "top-left":
        a = (x + int(tail_size * 0.2), y)
        b = (x + int(tail_size * 1.1), y)
        tip = (x + int(tail_size * 0.4), y - tail_size)
    else:
        a = (x + w - int(tail_size * 1.1), y)
        b = (x + w - int(tail_size * 0.2), y)
        tip = (x + w - int(tail_size * 0.4), y - tail_size)

    draw_handdrawn_arrow(draw, a[0], a[1], tip[0], tip[1], color, width=max(2, lw))
    draw_handdrawn_arrow(draw, b[0], b[1], tip[0], tip[1], color, width=max(2, lw))


def draw_sticker_badge(draw, cx, cy, rw, rh, bg_color, border_color, lw=3, amp=2.0):
    try:
        draw.ellipse([cx - rw, cy - rh, cx + rw, cy + rh], fill=bg_color)
    except Exception:
        pass
    draw_handdrawn_circle(
        draw, cx, cy, max(rw, rh), border_color,
        width=max(2, lw), jitter_strength=amp, passes=2,
    )


# ── SVG icon support (optional) ───────────────────────────────────────────────

def load_svg_icon(svg_path: str, size: tuple):
    """Convert local SVG file to PIL RGBA image, or return None if unavailable."""
    if not HAS_CAIROSVG:
        logger.warning(
            "Optional dependency cairosvg is not installed. "
            "SVG icons will use Pillow fallback."
        )
        return None
    try:
        import cairosvg
        from PIL import Image

        png_bytes = cairosvg.svg2png(
            url=svg_path,
            output_width=size[0],
            output_height=size[1],
        )
        return Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    except Exception as exc:
        logger.warning("load_svg_icon: failed to load '%s': %s", svg_path, exc)
        return None


# ── Illustration style dispatch ───────────────────────────────────────────────

_CONCRETE_STYLES = ["clean", "doodle", "sketch", "cartoon", "sticker"]

ILLUSTRATION_STYLES = [
    "clean", "doodle", "sketch", "cartoon", "sticker", "mixed", "random"
]


def get_illustration_clock_fn(style: str):
    from illustrations import draw_clock

    mapping = {
        "clean": draw_clock,
        "doodle": draw_handdrawn_clock,
        "sketch": draw_handdrawn_clock,
        "cartoon": draw_handdrawn_clock,
        "sticker": draw_handdrawn_clock,
    }
    return mapping.get(style, draw_clock)


def get_illustration_door_fn(style: str):
    from illustrations import draw_door

    mapping = {
        "clean": draw_door,
        "doodle": draw_handdrawn_door,
        "sketch": draw_handdrawn_door,
        "cartoon": draw_handdrawn_door,
        "sticker": draw_handdrawn_door,
    }
    return mapping.get(style, draw_door)


def get_illustration_border_fn(style: str):
    from illustrations import draw_border_rounded

    def _doodle_border(draw, w, h, color):
        draw_double_sketch_border(
            draw,
            w,
            h,
            color,
            width=max(2, h // 110),
            jitter_strength=_clamp(h / 260.0, _MIN_JITTER, _MAX_JITTER),
            gap=max(7, h // 56),
        )

    def _sketch_border(draw, w, h, color):
        draw_double_sketch_border(
            draw,
            w,
            h,
            color,
            width=max(2, h // 120),
            jitter_strength=_clamp(h / 230.0, _MIN_JITTER, _MAX_JITTER),
            gap=max(8, h // 50),
        )

    def _cartoon_border(draw, w, h, color):
        draw_jittered_rounded_rectangle(
            draw,
            6,
            6,
            w - 7,
            h - 7,
            radius=max(14, h // 18),
            color=color,
            width=max(3, h // 130),
            jitter_strength=2.6,
            passes=2,
        )

    mapping = {
        "clean": draw_border_rounded,
        "doodle": _doodle_border,
        "sketch": _sketch_border,
        "cartoon": _cartoon_border,
        "sticker": _cartoon_border,
    }
    return mapping.get(style, draw_border_rounded)


def resolve_illustration_style(raw_style: str, last_style: str = None) -> str:
    """Resolve random/mixed and apply dependency fallback chain."""
    from dependencies import resolve_illustration_style as _dep_resolve

    if raw_style in _CONCRETE_STYLES:
        return _dep_resolve(raw_style)

    candidates = [s for s in _CONCRETE_STYLES if s != last_style]
    picked = _rnd.choice(candidates or _CONCRETE_STYLES)
    return _dep_resolve(picked)