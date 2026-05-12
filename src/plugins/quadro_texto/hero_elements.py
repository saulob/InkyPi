"""Hero elements used by premium layouts."""

from decorative_shapes import draw_round_panel, draw_soft_disc


def draw_icon_tile(draw, cx, cy, size, fill, outline, icon_fn, icon_color, radius=None, outline_width=0):
    half = size // 2
    draw_round_panel(
        draw,
        cx - half,
        cy - half,
        cx + half,
        cy + half,
        fill=fill,
        outline=outline,
        width=max(1, outline_width) if outline else 0,
        radius=radius or max(12, size // 4),
    )
    icon_fn(draw, cx, cy, max(18, int(size * 0.28)), icon_color)


def draw_icon_disc(draw, cx, cy, radius, fill, outline, icon_fn, icon_color, ring_width=0):
    draw_soft_disc(
        draw,
        cx,
        cy,
        radius,
        fill,
        outline=outline,
        width=max(1, ring_width) if outline else 0,
        inner=outline,
    )
    icon_fn(draw, cx, cy, max(18, int(radius * 0.58)), icon_color)


def draw_value_panel(draw, x0, y0, x1, y1, fill, outline=None, radius=24, outline_width=0):
    draw_round_panel(
        draw,
        x0,
        y0,
        x1,
        y1,
        fill=fill,
        outline=outline,
        width=max(1, outline_width) if outline else 0,
        radius=radius,
    )