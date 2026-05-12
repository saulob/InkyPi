"""Composition utilities shared across premium Quadro Texto layouts."""

from fonts import resolve_text_font
from decorative_shapes import draw_round_panel


def text_size(draw, text, font):
    font = resolve_text_font(font, text)
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    except AttributeError:
        return draw.textsize(text, font=font)


def draw_text(draw, x, y, text, font, color, anchor="lt"):
    font = resolve_text_font(font, text)
    draw.text((x, y), text, font=font, fill=color, anchor=anchor)


def draw_label_chip(draw, x, y, text, font, text_color, fill, pad_x=18, pad_y=9, radius=18):
    tw, th = text_size(draw, text, font)
    draw_round_panel(
        draw,
        x,
        y,
        x + tw + pad_x * 2,
        y + th + pad_y * 2,
        fill=fill,
        radius=radius,
    )
    draw_text(draw, x + pad_x, y + pad_y, text, font, text_color)
    return x + tw + pad_x * 2, y + th + pad_y * 2


def draw_editorial_divider(draw, x0, y, x1, color, thickness, style="bar"):
    if style == "split":
        draw.rectangle([x0, y, x1, y + thickness], fill=color)
        inset = max(12, thickness * 3)
        draw.rectangle([x0, y - thickness * 2, min(x1, x0 + inset * 2), y - thickness], fill=color)
        return
    if style == "dashed":
        dash = max(16, thickness * 4)
        gap = max(10, thickness * 2)
        dx = x0
        while dx < x1:
            draw.rectangle([dx, y, min(x1, dx + dash), y + thickness], fill=color)
            dx += dash + gap
        return
    if style == "underline":
        draw.rectangle([x0, y, x1, y + thickness], fill=color)
        thin = max(1, thickness // 2)
        draw.rectangle([x0 + thin * 3, y + thickness + thin * 2, x1 - thin * 3, y + thickness + thin * 3], fill=color)
        return
    draw.rectangle([x0, y, x1, y + thickness], fill=color)