"""Decorative shape primitives for stronger visual composition."""


def draw_round_panel(draw, x0, y0, x1, y1, fill=None, outline=None, width=0, radius=24):
    try:
        draw.rounded_rectangle(
            [int(x0), int(y0), int(x1), int(y1)],
            radius=max(2, int(radius)),
            fill=fill,
            outline=outline,
            width=max(1, int(width)) if outline else 0,
        )
    except AttributeError:
        draw.rectangle(
            [int(x0), int(y0), int(x1), int(y1)],
            fill=fill,
            outline=outline,
            width=max(1, int(width)) if outline else 0,
        )


def draw_soft_disc(draw, cx, cy, r, fill, outline=None, width=0, inner=None):
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill, outline=outline, width=max(1, int(width)) if outline else 0)
    if inner:
        ir = int(r * 0.72)
        draw.ellipse([cx - ir, cy - ir, cx + ir, cy + ir], outline=inner, width=max(1, int(width)))


def draw_accent_band(draw, x0, y0, x1, y1, fill, radius=0):
    draw_round_panel(draw, x0, y0, x1, y1, fill=fill, radius=radius)


def draw_corner_accents(draw, x0, y0, x1, y1, size, color, lw=3, inset=0):
    s = int(size)
    x0 += inset
    y0 += inset
    x1 -= inset
    y1 -= inset

    draw.line([x0, y0 + s, x0, y0, x0 + s, y0], fill=color, width=lw)
    draw.line([x1 - s, y0, x1, y0, x1, y0 + s], fill=color, width=lw)
    draw.line([x0, y1 - s, x0, y1, x0 + s, y1], fill=color, width=lw)
    draw.line([x1 - s, y1, x1, y1, x1, y1 - s], fill=color, width=lw)


def draw_editorial_frame(draw, w, h, color, inset=10, lw=3, inner_gap=12, radius=0):
    draw_round_panel(draw, inset, inset, w - inset - 1, h - inset - 1, outline=color, width=lw, radius=radius)
    if inner_gap > 0:
        inner = inset + inner_gap
        draw_round_panel(
            draw,
            inner,
            inner,
            w - inner - 1,
            h - inner - 1,
            outline=color,
            width=max(1, lw - 1),
            radius=max(0, radius - 8),
        )