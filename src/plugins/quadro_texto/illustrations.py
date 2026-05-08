"""
illustrations.py — Reusable Pillow drawing primitives for Quadro Texto.

All functions draw directly on an ImageDraw object.
Coordinates use floats; Pillow handles rounding.
Colors are RGB tuples.
"""

import math


# ── Primitive helpers ──────────────────────────────────────────────────────────

def _lw(r, divisor=9):
    return max(2, int(r / divisor))


# ── Clock icon ─────────────────────────────────────────────────────────────────

def draw_clock(draw, cx, cy, r, color):
    """Analog clock face — circle, tick marks, hour≈10, minute≈2."""
    lw = _lw(r)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=lw)
    for deg in (0, 90, 180, 270):
        a = math.radians(deg)
        x0 = cx + r * 0.78 * math.sin(a)
        y0 = cy - r * 0.78 * math.cos(a)
        x1 = cx + r * 0.92 * math.sin(a)
        y1 = cy - r * 0.92 * math.cos(a)
        draw.line([x0, y0, x1, y1], fill=color, width=max(1, lw - 1))
    # hour hand ~ 10:10 left
    ha = math.radians(-60)
    hl = r * 0.52
    draw.line([cx, cy, cx + hl * math.sin(ha), cy - hl * math.cos(ha)],
              fill=color, width=lw)
    # minute hand ~ 2 o'clock
    ma = math.radians(60)
    ml = r * 0.70
    draw.line([cx, cy, cx + ml * math.sin(ma), cy - ml * math.cos(ma)],
              fill=color, width=max(1, lw - 1))
    cd = max(2, r // 7)
    draw.ellipse([cx - cd, cy - cd, cx + cd, cy + cd], fill=color)


def draw_clock_doodle(draw, cx, cy, r, color):
    """Sketchy clock with slightly irregular circle arcs and wobbly hands."""
    lw = _lw(r)
    # Outer circle in two arcs to look hand-drawn
    draw.arc([cx - r, cy - r, cx + r, cy + r], start=5, end=180, fill=color, width=lw)
    draw.arc([cx - r, cy - r, cx + r, cy + r], start=185, end=358, fill=color, width=lw)
    # Hands
    ha = math.radians(-55)
    hl = r * 0.50
    draw.line([cx, cy, cx + hl * math.sin(ha), cy - hl * math.cos(ha)],
              fill=color, width=lw)
    ma = math.radians(65)
    ml = r * 0.68
    draw.line([cx, cy, cx + ml * math.sin(ma), cy - ml * math.cos(ma)],
              fill=color, width=max(1, lw - 1))
    draw.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=color)
    # Small doodle ticks
    for deg in (0, 90, 180, 270):
        a = math.radians(deg)
        x0 = cx + r * 0.80 * math.sin(a)
        y0 = cy - r * 0.80 * math.cos(a)
        x1 = cx + r * 0.93 * math.sin(a)
        y1 = cy - r * 0.93 * math.cos(a)
        draw.line([x0, y0, x1, y1], fill=color, width=max(1, lw - 1))


# ── Door / exit icon ──────────────────────────────────────────────────────────

def draw_door(draw, cx, cy, r, color):
    """Rectangle door + knob + rightward arrow."""
    lw = _lw(r)
    fw = int(r * 0.82)
    fh = int(r * 1.22)
    draw.rectangle([cx - fw, cy - fh, cx + fw, cy + fh], outline=color, width=lw)
    hr = max(2, r // 8)
    hx = cx + int(fw * 0.40)
    draw.ellipse([hx - hr, cy - hr, hx + hr, cy + hr], fill=color)
    ax0 = cx + fw + int(r * 0.20)
    ax1 = cx + fw + int(r * 0.65)
    aw  = max(2, r // 7)
    draw.line([ax0, cy, ax1, cy], fill=color, width=aw)
    ah = aw + 2
    draw.polygon([(ax1, cy - ah), (ax1 + int(ah * 1.4), cy), (ax1, cy + ah)], fill=color)


def draw_door_doodle(draw, cx, cy, r, color):
    """Sketchy door with rounded frame corners and cartoon arrow."""
    lw = _lw(r)
    fw = int(r * 0.82)
    fh = int(r * 1.22)
    try:
        draw.rounded_rectangle([cx - fw, cy - fh, cx + fw, cy + fh],
                                radius=max(3, r // 6), outline=color, width=lw)
    except AttributeError:
        draw.rectangle([cx - fw, cy - fh, cx + fw, cy + fh], outline=color, width=lw)
    hr = max(3, r // 7)
    hx = cx + int(fw * 0.38)
    draw.ellipse([hx - hr, cy - hr, hx + hr, cy + hr], outline=color, width=lw)
    # Cartoon chunky arrow
    ax0 = cx + fw + int(r * 0.18)
    ax1 = cx + fw + int(r * 0.60)
    aw  = max(3, r // 6)
    draw.line([ax0, cy, ax1, cy], fill=color, width=aw)
    ah = aw + 4
    draw.polygon([(ax1, cy - ah), (ax1 + int(ah * 1.5), cy), (ax1, cy + ah)], fill=color)


# ── Calendar icon ─────────────────────────────────────────────────────────────

def draw_calendar(draw, cx, cy, r, color):
    lw = _lw(r)
    fw = int(r * 0.90)
    fh = int(r * 0.85)
    top = cy - fh
    bot = cy + fh
    left = cx - fw
    right = cx + fw
    draw.rectangle([left, top, right, bot], outline=color, width=lw)
    bar = top + int(fh * 0.42)
    draw.line([left, bar, right, bar], fill=color, width=lw)
    # Bindings
    bx = [left + fw // 3, cx, right - fw // 3]
    for bxi in bx:
        draw.line([bxi, top - int(r * 0.18), bxi, top + int(r * 0.12)],
                  fill=color, width=max(2, lw - 1))
    # Grid dots
    gw = (right - left) // 4
    gh = (bot - bar) // 3
    for row in range(2):
        for col in range(3):
            gx = left + gw + col * gw
            gy = bar + gh + row * gh
            cr = max(2, r // 12)
            draw.ellipse([gx - cr, gy - cr, gx + cr, gy + cr], fill=color)


# ── Check / confirm icon ──────────────────────────────────────────────────────

def draw_check(draw, cx, cy, r, color):
    lw = max(3, r // 5)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=_lw(r))
    x1 = cx - int(r * 0.38)
    y1 = cy + int(r * 0.05)
    x2 = cx - int(r * 0.05)
    y2 = cy + int(r * 0.40)
    x3 = cx + int(r * 0.42)
    y3 = cy - int(r * 0.30)
    draw.line([x1, y1, x2, y2, x3, y3], fill=color, width=lw)


# ── Arrow decorations ──────────────────────────────────────────────────────────

def draw_arrow_right(draw, x, y, length, thickness, color):
    ah = thickness + 3
    draw.line([x, y, x + length, y], fill=color, width=thickness)
    draw.polygon([(x + length, y - ah),
                  (x + length + int(ah * 1.4), y),
                  (x + length, y + ah)], fill=color)


def draw_arrow_down(draw, x, y, length, thickness, color):
    ah = thickness + 3
    draw.line([x, y, x, y + length], fill=color, width=thickness)
    draw.polygon([(x - ah, y + length),
                  (x, y + length + int(ah * 1.4)),
                  (x + ah, y + length)], fill=color)


# ── Decorative shapes ──────────────────────────────────────────────────────────

def draw_underline(draw, x, y, width, thickness, color):
    draw.line([x, y, x + width, y], fill=color, width=thickness)


def draw_pill_badge(draw, cx, cy, rw, rh, bg_color, text_color, draw_fn):
    """Rounded badge background."""
    try:
        draw.rounded_rectangle([cx - rw, cy - rh, cx + rw, cy + rh],
                                radius=rh, fill=bg_color)
    except AttributeError:
        draw.ellipse([cx - rw, cy - rh, cx + rw, cy + rh], fill=bg_color)


def draw_star_burst(draw, cx, cy, r, points, color, lw=2):
    """Simple starburst / explosion shape."""
    inner = r * 0.45
    for i in range(points * 2):
        a = math.radians(i * 180 / points - 90)
        rr = r if i % 2 == 0 else inner
        x = cx + rr * math.cos(a)
        y = cy + rr * math.sin(a)
        if i == 0:
            prev = (x, y)
            continue
        draw.line([prev[0], prev[1], x, y], fill=color, width=lw)
        prev = (x, y)


def draw_doodle_circle(draw, cx, cy, r, color, lw=2):
    """Slightly imperfect hand-drawn looking circle."""
    draw.arc([cx - r, cy - r, cx + r, cy + r], 0, 195, fill=color, width=lw)
    draw.arc([cx - r - 2, cy - r + 2, cx + r - 2, cy + r - 2],
             200, 360, fill=color, width=lw)


def draw_corner_bracket(draw, x, y, size, color, lw=2, corner="tl"):
    """Single corner bracket decoration."""
    s = size
    if corner == "tl":
        draw.line([x, y + s, x, y, x + s, y], fill=color, width=lw)
    elif corner == "tr":
        draw.line([x - s, y, x, y, x, y + s], fill=color, width=lw)
    elif corner == "bl":
        draw.line([x, y - s, x, y, x + s, y], fill=color, width=lw)
    elif corner == "br":
        draw.line([x - s, y, x, y, x, y - s], fill=color, width=lw)


def draw_all_corner_brackets(draw, x0, y0, x1, y1, size, color, lw=2):
    draw_corner_bracket(draw, x0, y0, size, color, lw, "tl")
    draw_corner_bracket(draw, x1, y0, size, color, lw, "tr")
    draw_corner_bracket(draw, x0, y1, size, color, lw, "bl")
    draw_corner_bracket(draw, x1, y1, size, color, lw, "br")


def draw_building(draw, cx, cy, r, color):
    """Simple office building silhouette."""
    lw = _lw(r)
    bw = int(r * 1.0)
    bh = int(r * 1.4)
    draw.rectangle([cx - bw, cy - bh, cx + bw, cy + int(bh * 0.1)],
                   outline=color, width=lw)
    ws = int(r * 0.22)
    wg = int(r * 0.18)
    for row in range(3):
        for col in range(2):
            wx = cx - bw // 2 + col * (ws + wg * 2) - ws // 2
            wy = cy - bh + wg + row * (ws + wg)
            draw.rectangle([wx, wy, wx + ws, wy + ws], outline=color, width=max(1, lw - 1))


def draw_sun(draw, cx, cy, r, color):
    lw = _lw(r, 8)
    ir = int(r * 0.55)
    draw.ellipse([cx - ir, cy - ir, cx + ir, cy + ir], outline=color, width=lw)
    for deg in range(0, 360, 45):
        a = math.radians(deg)
        x0 = cx + (ir + 3) * math.cos(a)
        y0 = cy + (ir + 3) * math.sin(a)
        x1 = cx + r * math.cos(a)
        y1 = cy + r * math.sin(a)
        draw.line([x0, y0, x1, y1], fill=color, width=lw)


# ── Border styles ──────────────────────────────────────────────────────────────

def draw_border_rounded(draw, w, h, color, lw=None):
    lw = lw or max(3, h // 80)
    try:
        draw.rounded_rectangle([lw, lw, w - lw - 1, h - lw - 1],
                                radius=int(h * 0.04), outline=color, width=lw)
    except AttributeError:
        draw.rectangle([lw, lw, w - lw - 1, h - lw - 1], outline=color, width=lw)


def draw_border_double(draw, w, h, color):
    outer = max(3, h // 80)
    inner = max(2, outer - 1)
    gap   = outer + 6
    draw.rectangle([outer, outer, w - outer - 1, h - outer - 1],
                   outline=color, width=outer)
    draw.rectangle([gap, gap, w - gap - 1, h - gap - 1],
                   outline=color, width=inner)


def draw_border_blueprint(draw, w, h, color):
    lw = max(2, h // 100)
    draw.rectangle([lw, lw, w - lw - 1, h - lw - 1], outline=color, width=lw)
    dash = 8
    # top dashes
    for x in range(20, w - 20, dash * 2):
        draw.line([x, 0, min(x + dash, w), 0], fill=color, width=lw)


# ── Icon dispatch ──────────────────────────────────────────────────────────────

CLOCK_VARIANTS  = {"clean": draw_clock,  "doodle": draw_clock_doodle}
DOOR_VARIANTS   = {"clean": draw_door,   "doodle": draw_door_doodle}
BORDER_VARIANTS = {
    "rounded":   draw_border_rounded,
    "double":    draw_border_double,
    "blueprint": draw_border_blueprint,
    "none":      lambda *a, **k: None,
}


def get_clock_fn(style="clean"):
    return CLOCK_VARIANTS.get(style, draw_clock)


def get_door_fn(style="clean"):
    return DOOR_VARIANTS.get(style, draw_door)


def get_border_fn(style="rounded"):
    return BORDER_VARIANTS.get(style, draw_border_rounded)
