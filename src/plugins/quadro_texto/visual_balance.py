"""Geometry helpers for more intentional layout balance."""

from spacing import clamp


def fit_span(center_x, content_width, outer_x0, outer_x1, pad):
    target_w = min(outer_x1 - outer_x0, content_width + pad * 2)
    x0 = clamp(center_x - target_w // 2, outer_x0, outer_x1 - target_w)
    return int(x0), int(x0 + target_w)


def vertical_origin(y0, y1, total_height, bias=0.5):
    free = max(0, (y1 - y0) - total_height)
    return y0 + int(free * bias)


def split_columns(w, ratio=0.34):
    left_w = int(w * ratio)
    return left_w, w - left_w


def anchor_box(x0, y0, x1, y1, width, height, align="br", margin=0):
    if align == "tl":
        return x0 + margin, y0 + margin, x0 + margin + width, y0 + margin + height
    if align == "tr":
        return x1 - margin - width, y0 + margin, x1 - margin, y0 + margin + height
    if align == "bl":
        return x0 + margin, y1 - margin - height, x0 + margin + width, y1 - margin
    return x1 - margin - width, y1 - margin - height, x1 - margin, y1 - margin