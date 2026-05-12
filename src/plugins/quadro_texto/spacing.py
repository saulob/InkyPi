"""Responsive spacing helpers for Quadro Texto layouts."""


def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def layout_scale(w, h):
    short = min(w, h)
    return {
        "pad_x": int(w * 0.06),
        "pad_y": int(h * 0.08),
        "gap_xs": max(4, int(h * 0.014)),
        "gap_sm": max(6, int(h * 0.020)),
        "gap_md": max(10, int(h * 0.030)),
        "gap_lg": max(14, int(h * 0.048)),
        "icon_sm": int(h * 0.075),
        "icon_md": int(h * 0.100),
        "icon_lg": int(h * 0.130),
        "icon_xl": int(h * 0.170),
        "radius_sm": max(12, int(short * 0.030)),
        "radius_md": max(18, int(short * 0.052)),
        "radius_lg": max(24, int(short * 0.085)),
        "divider_thin": max(2, h // 110),
        "divider_mid": max(4, h // 72),
        "divider_thick": max(6, h // 42),
        "stripe": int(h * 0.12),
    }


def inset_rect(w, h, x_frac=0.06, y_frac=0.08):
    px = int(w * x_frac)
    py = int(h * y_frac)
    return px, py, w - px, h - py


def centered_span(center_x, content_width, extra_pad, min_x, max_x):
    x0 = max(min_x, center_x - content_width // 2 - extra_pad)
    x1 = min(max_x, center_x + content_width // 2 + extra_pad)
    if x1 <= x0:
        x1 = x0 + max(1, content_width + extra_pad * 2)
    return int(x0), int(x1)


def split_y(h, ratio=0.58):
    return int(h * ratio)