"""
layouts.py — All render functions for Quadro Texto plugin.

Each render_* function signature:
    render_*(img, draw, w, h, texts, theme, fonts, illu, opts) -> None

    texts : dict with keys top_text, main_text, bottom_text, time_text
    theme : dict from themes.THEMES
    fonts : callable load_font(role) already bound to pack+h
    illu  : dict with keys clock_fn, door_fn, border_fn, icon_style
    opts  : dict with keys show_border, show_icons, show_divider, align

Available layouts:
  split          — canvas cut in 2 horizontal halves
  poster         — centred vertically, clock top, door bottom-right
  minimal        — text only, centred, thin divider
  badge          — large bold label inside a pill/badge shape
  dashboard      — left icon panel + right text panel
  blueprint      — technical style with grid lines and brackets
  doodle         — sketchy hand-drawn feel
  framed         — inner frame / mat border
  sticker        — bold label on solid-color block with accent stripe
  lateral        — coloured left stripe with text on right
    sketch_note    — looks like a handwritten paper note
    marker_board   — marker-highlight style board
    doodle_card    — two stacked doodle cards with hand arrows
        hero_banner    — bold hero card with lower metric block
        editorial      — poster/editorial composition with strong time card
        modern_widget  — nested rounded widget panels
        focus_mode     — centered premium poster with framed time block
        split_hero     — asymmetrical hero block plus lower info banner
"""

import math
from PIL import Image, ImageDraw
from illustrations import (
    draw_clock, draw_door, draw_check, draw_calendar,
    draw_corner_bracket, draw_all_corner_brackets, draw_underline,
    draw_arrow_right, draw_doodle_circle, draw_star_burst,
    draw_border_rounded, draw_border_double, draw_border_blueprint,
    get_clock_fn, get_door_fn, get_border_fn,
    draw_building, draw_sun,
)
from doodle import (
    draw_paper_texture,
    draw_jittered_line,
    draw_jittered_rounded_rectangle,
    draw_double_sketch_border,
    draw_marker_stroke,
    draw_scribble_underline,
    draw_handdrawn_arrow,
)
from fonts import resolve_text_font
from spacing import layout_scale, split_y
from contrast import (
    get_safe_text_color_for_surface as _surf_tc,
    get_safe_divider_color as _surf_div,
    DIVIDER_MIN_RATIO,
)
from emoji_layout import add_occupied_box as _add_occupied_box, should_show_icon as _should_show_icon
from visual_balance import fit_span, vertical_origin, split_columns
from decorative_shapes import (
    draw_round_panel,
    draw_soft_disc,
    draw_corner_accents,
    draw_editorial_frame,
    draw_accent_band,
)
from hero_elements import draw_icon_tile, draw_icon_disc, draw_value_panel
from composition_helpers import text_size as _measure_text, draw_label_chip, draw_editorial_divider


# ── Internal helpers ───────────────────────────────────────────────────────────

def _text_w(draw, text, font):
    return _measure_text(draw, text, font)[0]


def _text_h(draw, text, font):
    return _measure_text(draw, text, font)[1]


def _box_from_anchor(x, y, width, height, anchor="lt"):
    if anchor == "mm":
        return (
            int(x - width / 2),
            int(y - height / 2),
            int(x + width / 2),
            int(y + height / 2),
        )
    if anchor == "mt":
        return (
            int(x - width / 2),
            int(y),
            int(x + width / 2),
            int(y + height),
        )
    return int(x), int(y), int(x + width), int(y + height)


def _inflate_box(box, pad):
    x0, y0, x1, y1 = box
    pad = max(0, int(pad))
    return x0 - pad, y0 - pad, x1 + pad, y1 + pad


def _track_box(opts, name, box, pad=0):
    occupied_boxes = (opts or {}).get("occupied_boxes")
    if not occupied_boxes or not name or box is None:
        return
    _add_occupied_box(occupied_boxes, name, _inflate_box(box, pad))


def _draw_text(draw, x, y, text, font, color, anchor="lt", opts=None, box_name=None, box_pad=0):
    font = resolve_text_font(font, text)
    draw.text((x, y), text, font=font, fill=color, anchor=anchor)
    if box_name:
        tw, th = _measure_text(draw, text, font)
        _track_box(
            opts,
            box_name,
            _box_from_anchor(x, y, tw, th, anchor),
            pad=box_pad,
        )


def _section_bg(img, draw, x0, y0, x1, y1, color):
    draw.rectangle([x0, y0, x1, y1], fill=color)


def _divider(draw, x0, y, x1, color, h_ref, style="solid"):
    lw = max(2, h_ref // 120)
    if style == "dashed":
        dash = 12
        gap  = 8
        x = x0
        while x < x1:
            draw.line([x, y, min(x + dash, x1), y], fill=color, width=lw)
            x += dash + gap
    elif style == "double":
        draw.line([x0, y - lw, x1, y - lw], fill=color, width=lw)
        draw.line([x0, y + lw + 1, x1, y + lw + 1], fill=color, width=lw)
    else:
        draw.line([x0, y, x1, y], fill=color, width=lw)


def _draw_editorial_divider_tracked(
    draw,
    x0,
    y,
    x1,
    color,
    thickness,
    style="bar",
    opts=None,
    box_name="divider_box",
    box_pad=8,
):
    draw_editorial_divider(draw, x0, y, x1, color, thickness, style=style)
    y0 = y
    y1 = y + thickness
    if style == "split":
        y0 = y - thickness * 2
    if style == "underline":
        thin = max(1, thickness // 2)
        y1 = y + thickness + thin * 3
    _track_box(opts, box_name, (x0, y0, x1, y1), pad=box_pad)


def _draw_accent_band_tracked(draw, x0, y0, x1, y1, color, opts=None, box_name="divider_box", box_pad=6, radius=0):
    draw_accent_band(draw, x0, y0, x1, y1, color, radius=radius)
    _track_box(opts, box_name, (x0, y0, x1, y1), pad=box_pad)


def _draw_icon_disc_tracked(
    draw,
    cx,
    cy,
    radius,
    fill,
    outline,
    icon_fn,
    icon_color,
    opts=None,
    icon_name="clock",
    ring_width=0,
    box_pad=10,
):
    layout_key = (opts or {}).get("layout_key", "")
    if not _should_show_icon(layout_key, icon_name, radius * 2):
        return False
    draw_icon_disc(draw, cx, cy, radius, fill, outline, icon_fn, icon_color, ring_width=ring_width)
    _track_box(opts, f"{icon_name}_box", (cx - radius, cy - radius, cx + radius, cy + radius), pad=box_pad)
    return True


def _draw_icon_tile_tracked(
    draw,
    cx,
    cy,
    size,
    fill,
    outline,
    icon_fn,
    icon_color,
    opts=None,
    icon_name="door",
    radius=None,
    outline_width=0,
    box_pad=10,
):
    layout_key = (opts or {}).get("layout_key", "")
    if not _should_show_icon(layout_key, icon_name, size):
        return False
    draw_icon_tile(
        draw,
        cx,
        cy,
        size,
        fill,
        outline,
        icon_fn,
        icon_color,
        radius=radius,
        outline_width=outline_width,
    )
    half = size // 2
    _track_box(opts, f"{icon_name}_box", (cx - half, cy - half, cx + half, cy + half), pad=box_pad)
    return True


def _direct_icon_box(icon_name, cx, cy, radius):
    if icon_name == "door":
        return (
            cx - int(radius * 1.05),
            cy - int(radius * 1.35),
            cx + int(radius * 2.05),
            cy + int(radius * 1.35),
        )
    return cx - radius, cy - radius, cx + radius, cy + radius


def _draw_free_icon_tracked(draw, cx, cy, radius, icon_fn, icon_color, opts=None, icon_name="clock", box_pad=8):
    layout_key = (opts or {}).get("layout_key", "")
    if not _should_show_icon(layout_key, icon_name, radius * 2):
        return False
    icon_fn(draw, cx, cy, radius, icon_color)
    _track_box(opts, f"{icon_name}_box", _direct_icon_box(icon_name, cx, cy, radius), pad=box_pad)
    return True


# ── 1. SPLIT ──────────────────────────────────────────────────────────────────

def render_split(img, draw, w, h, texts, theme, lf, illu, opts):
    sc = layout_scale(w, h)
    pad = sc["pad_x"]
    lbl_f = lf("label")
    val_f = lf("value")
    hero_y = split_y(h, 0.58)

    _section_bg(img, draw, 0, 0, w, hero_y, theme["top_bg"])
    _section_bg(img, draw, 0, hero_y, w, h, theme["bottom_bg"])

    if opts.get("show_divider", True):
        _draw_accent_band_tracked(
            draw,
            0,
            hero_y - sc["divider_mid"],
            w,
            hero_y + sc["divider_mid"],
            theme["divider"],
            opts=opts,
            box_name="divider_box",
        )

    label_y = int(h * 0.09)
    draw_label_chip(
        draw,
        pad,
        label_y,
        texts["top_text"],
        lbl_f,
        theme["top_text"],
        theme["mid_bg"],
        pad_x=18,
        pad_y=10,
        radius=sc["radius_sm"],
    )
    value_y = label_y + int(h * 0.13)
    _draw_text(draw, pad, value_y, texts["main_text"], val_f, theme["top_text"], opts=opts, box_name="main_text_box", box_pad=14)

    main_w = int(_text_w(draw, texts["main_text"], val_f))
    _draw_editorial_divider_tracked(
        draw,
        pad,
        value_y + int(h * 0.185),
        min(w - pad, pad + main_w + int(w * 0.10)),
        theme["divider"],
        sc["divider_mid"],
        style="split",
        opts=opts,
    )

    if opts.get("show_icons", True):
        disc_r = sc["icon_xl"]
        _draw_icon_disc_tracked(
            draw,
            w - pad - disc_r,
            int(hero_y * 0.42),
            disc_r,
            theme["mid_bg"],
            theme["border"],
            illu["clock_fn"],
            theme["top_text"],
            opts=opts,
            icon_name="clock",
            ring_width=max(2, h // 130),
        )

    bottom_y = hero_y + int(h * 0.08)
    door_shown = False
    if opts.get("show_icons", True):
        tile = int(h * 0.20)
        door_shown = _draw_icon_tile_tracked(
            draw,
            pad + tile // 2,
            bottom_y + tile // 2,
            tile,
            theme["mid_bg"],
            theme["border"],
            illu["door_fn"],
            theme["bottom_text"],
            opts=opts,
            icon_name="door",
            outline_width=max(2, h // 140),
        )
    if door_shown:
        text_x = pad + tile + int(w * 0.04)
    else:
        text_x = pad

    _draw_text(draw, text_x, bottom_y, texts["bottom_text"], lbl_f, theme["bottom_text"])
    time_y = bottom_y + int(h * 0.11)
    _draw_text(draw, text_x, time_y, texts["time_text"], val_f, theme["bottom_text"], opts=opts, box_name="time_text_box", box_pad=12)

    time_w = int(_text_w(draw, texts["time_text"], val_f))
    _draw_editorial_divider_tracked(
        draw,
        text_x,
        time_y + int(h * 0.19),
        min(w - pad, text_x + time_w + int(w * 0.08)),
        theme["accent"],
        sc["divider_thick"],
        style="underline",
        opts=opts,
    )

    if opts.get("show_border", True):
        illu["border_fn"](draw, w, h, theme["border"])


# ── 2. POSTER ─────────────────────────────────────────────────────────────────

def render_poster(img, draw, w, h, texts, theme, lf, illu, opts):
    _section_bg(img, draw, 0, 0, w, h, theme["bg"])
    sc = layout_scale(w, h)
    pad = sc["pad_x"]
    lbl_f = lf("label")
    val_f = lf("value")

    if opts.get("show_icons", True):
        _draw_icon_disc_tracked(
            draw,
            w // 2,
            int(h * 0.17),
            int(h * 0.105),
            theme["mid_bg"],
            theme["border"],
            illu["clock_fn"],
            theme["top_text"],
            opts=opts,
            icon_name="clock",
            ring_width=max(2, h // 140),
        )

    label_w = int(_text_w(draw, texts["top_text"], lbl_f)) + 40
    draw_label_chip(
        draw,
        (w - label_w) // 2,
        int(h * 0.26),
        texts["top_text"],
        lbl_f,
        theme["top_text"],
        theme["mid_bg"],
        pad_x=20,
        pad_y=10,
        radius=sc["radius_sm"],
    )

    panel_y0 = int(h * 0.37)
    panel_h = int(h * 0.22)
    text_w = int(_text_w(draw, texts["main_text"], val_f))
    panel_x0, panel_x1 = fit_span(w // 2, text_w, pad, w - pad, int(w * 0.10))
    hero_fill = theme["accent"]
    hero_lum = sum(hero_fill) / 3
    hero_tc = (255, 255, 255) if hero_lum < 128 else (10, 10, 10)
    draw_value_panel(
        draw,
        panel_x0,
        panel_y0,
        panel_x1,
        panel_y0 + panel_h,
        hero_fill,
        radius=sc["radius_lg"],
    )
    _draw_text(draw, w // 2, panel_y0 + panel_h // 2, texts["main_text"], val_f, hero_tc, anchor="mm", opts=opts, box_name="main_text_box", box_pad=14)

    divider_y = panel_y0 + panel_h + int(h * 0.07)
    if opts.get("show_divider", True):
        _draw_editorial_divider_tracked(
            draw,
            int(w * 0.26),
            divider_y,
            int(w * 0.74),
            theme["divider"],
            sc["divider_mid"],
            style="split",
            opts=opts,
        )

    bottom_label_y = divider_y + int(h * 0.06)
    _draw_text(draw, w // 2, bottom_label_y, texts["bottom_text"], lbl_f, theme["bottom_text"], anchor="mt")
    time_y = bottom_label_y + int(h * 0.11)
    _draw_text(draw, w // 2, time_y, texts["time_text"], val_f, theme["bottom_text"], anchor="mt", opts=opts, box_name="time_text_box", box_pad=12)

    if opts.get("show_icons", True):
        tile = int(h * 0.14)
        _draw_icon_tile_tracked(
            draw,
            w - pad - tile // 2,
            h - int(h * 0.13),
            tile,
            theme["mid_bg"],
            theme["border"],
            illu["door_fn"],
            theme["bottom_text"],
            opts=opts,
            icon_name="door",
            outline_width=max(2, h // 150),
        )

    if opts.get("show_border", True):
        illu["border_fn"](draw, w, h, theme["border"])


# ── 3. MINIMAL ────────────────────────────────────────────────────────────────

def render_minimal(img, draw, w, h, texts, theme, lf, illu, opts):
    _section_bg(img, draw, 0, 0, w, h, theme["bg"])
    sc = layout_scale(w, h)
    lbl_f = lf("label")
    val_f = lf("value")

    total_h = int(h * 0.54)
    y = vertical_origin(int(h * 0.04), h - int(h * 0.08), total_h, bias=0.40)

    if opts.get("show_icons", True):
        _draw_icon_disc_tracked(
            draw,
            w // 2,
            y + int(h * 0.03),
            sc["icon_md"],
            theme["mid_bg"],
            theme["border"],
            illu["clock_fn"],
            theme["top_text"],
            opts=opts,
            icon_name="clock",
            ring_width=max(2, h // 150),
        )
        y += int(h * 0.10)

    chip_w = int(_text_w(draw, texts["top_text"], lbl_f)) + 36
    draw_label_chip(
        draw,
        (w - chip_w) // 2,
        y,
        texts["top_text"],
        lbl_f,
        theme["top_text"],
        theme["mid_bg"],
        pad_x=18,
        pad_y=9,
        radius=sc["radius_sm"],
    )
    y += int(h * 0.11)
    _draw_text(draw, w // 2, y, texts["main_text"], val_f, theme["top_text"], "mt", opts=opts, box_name="main_text_box", box_pad=12)
    y += int(h * 0.19)

    if opts.get("show_divider", True):
        _draw_editorial_divider_tracked(
            draw,
            int(w * 0.32),
            y,
            int(w * 0.68),
            theme["divider"],
            sc["divider_mid"],
            style="underline",
            opts=opts,
        )
        y += int(h * 0.06)

    _draw_text(draw, w // 2, y, texts["bottom_text"], lbl_f, theme["bottom_text"], "mt")
    y += int(h * 0.11)
    _draw_text(draw, w // 2, y, texts["time_text"], val_f, theme["bottom_text"], "mt", opts=opts, box_name="time_text_box", box_pad=12)

    if opts.get("show_border", True):
        illu["border_fn"](draw, w, h, theme["border"])


# ── 4. BADGE ──────────────────────────────────────────────────────────────────

def render_badge(img, draw, w, h, texts, theme, lf, illu, opts):
    _section_bg(img, draw, 0, 0, w, h, theme["bg"])
    sc = layout_scale(w, h)
    pad = sc["pad_x"]
    lbl_f = lf("label")
    val_f = lf("value")

    y = int(h * 0.10)
    draw_label_chip(
        draw,
        pad,
        y,
        texts["top_text"],
        lbl_f,
        theme["top_text"],
        theme["mid_bg"],
        pad_x=18,
        pad_y=10,
        radius=sc["radius_sm"],
    )

    pill_y = y + int(h * 0.12)
    pill_h = int(h * 0.22)
    text_w = int(_text_w(draw, texts["main_text"], val_f))
    pill_x0 = pad
    pill_x1 = min(w - pad - int(w * 0.10), pad + text_w + int(w * 0.18))
    fill = theme["accent"]
    fill_lum = sum(fill) / 3
    text_c = (255, 255, 255) if fill_lum < 128 else (10, 10, 10)
    draw_value_panel(draw, pill_x0, pill_y, pill_x1, pill_y + pill_h, fill, radius=pill_h // 2)
    _draw_text(draw, (pill_x0 + pill_x1) // 2, pill_y + pill_h // 2, texts["main_text"], val_f, text_c, "mm", opts=opts, box_name="main_text_box", box_pad=12)

    if opts.get("show_icons", True):
        _draw_icon_disc_tracked(
            draw,
            w - pad - int(h * 0.12),
            int(h * 0.24),
            int(h * 0.12),
            theme["mid_bg"],
            theme["border"],
            illu["clock_fn"],
            theme["top_text"],
            opts=opts,
            icon_name="clock",
            ring_width=max(2, h // 140),
        )

    divider_y = pill_y + pill_h + int(h * 0.06)
    if opts.get("show_divider", True):
        _draw_editorial_divider_tracked(
            draw,
            pad,
            divider_y,
            pill_x1,
            theme["divider"],
            sc["divider_mid"],
            style="split",
            opts=opts,
        )

    bottom_y = divider_y + int(h * 0.06)
    door_shown = False
    if opts.get("show_icons", True):
        tile = int(h * 0.15)
        door_shown = _draw_icon_tile_tracked(
            draw,
            pad + tile // 2,
            bottom_y + tile // 2,
            tile,
            theme["mid_bg"],
            theme["border"],
            illu["door_fn"],
            theme["bottom_text"],
            opts=opts,
            icon_name="door",
            outline_width=max(2, h // 150),
        )
    if door_shown:
        text_x = pad + tile + int(w * 0.035)
    else:
        text_x = pad

    _draw_text(draw, text_x, bottom_y, texts["bottom_text"], lbl_f, theme["bottom_text"])
    time_y = bottom_y + int(h * 0.11)
    _draw_text(draw, text_x, time_y, texts["time_text"], val_f, theme["bottom_text"], opts=opts, box_name="time_text_box", box_pad=12)

    time_w = int(_text_w(draw, texts["time_text"], val_f))
    _draw_editorial_divider_tracked(
        draw,
        text_x,
        time_y + int(h * 0.19),
        min(w - pad, text_x + time_w + int(w * 0.08)),
        theme["accent"],
        sc["divider_thick"],
        style="underline",
        opts=opts,
    )

    if opts.get("show_border", True):
        illu["border_fn"](draw, w, h, theme["border"])


# ── 5. DASHBOARD ──────────────────────────────────────────────────────────────

def render_dashboard(img, draw, w, h, texts, theme, lf, illu, opts):
    sc = layout_scale(w, h)
    panel_w, _ = split_columns(w, 0.34)
    outer_pad = int(w * 0.025)

    _section_bg(img, draw, 0, 0, w, h, theme["bg"])
    draw_value_panel(
        draw,
        outer_pad,
        int(h * 0.04),
        panel_w,
        h - int(h * 0.04),
        theme["mid_bg"],
        outline=theme["border"],
        radius=sc["radius_lg"],
        outline_width=max(2, h // 140),
    )
    _track_box(opts, "icon_panel_box", (outer_pad, int(h * 0.04), panel_w, h - int(h * 0.04)), pad=8)

    lbl_f = lf("label")
    val_f = lf("value")

    if opts.get("show_icons", True):
        icon_size = int(h * 0.19)
        cx = (outer_pad + panel_w) // 2
        _draw_icon_tile_tracked(
            draw,
            cx,
            int(h * 0.25),
            icon_size,
            theme["bg"],
            theme["border"],
            illu["clock_fn"],
            theme["top_text"],
            opts=opts,
            icon_name="clock",
            outline_width=max(2, h // 150),
        )
        draw_accent_band(
            draw,
            outer_pad + int(w * 0.04),
            int(h * 0.46),
            panel_w - int(w * 0.04),
            int(h * 0.48),
            theme["accent"],
            radius=sc["radius_sm"],
        )
        _draw_icon_tile_tracked(
            draw,
            cx,
            int(h * 0.69),
            int(h * 0.17),
            theme["bg"],
            theme["border"],
            illu["door_fn"],
            theme["bottom_text"],
            opts=opts,
            icon_name="door",
            outline_width=max(2, h // 150),
        )

    tx = panel_w + int(w * 0.05)
    draw_label_chip(
        draw,
        tx,
        int(h * 0.08),
        texts["top_text"],
        lbl_f,
        theme["top_text"],
        theme["mid_bg"],
        pad_x=18,
        pad_y=10,
        radius=sc["radius_sm"],
    )
    main_y = int(h * 0.24)
    _draw_text(draw, tx, main_y, texts["main_text"], val_f, theme["top_text"], opts=opts, box_name="main_text_box", box_pad=14)

    if opts.get("show_divider", True):
        _draw_editorial_divider_tracked(
            draw,
            tx,
            main_y + int(h * 0.20),
            min(w - int(w * 0.08), tx + int(w * 0.42)),
            theme["divider"],
            sc["divider_mid"],
            style="split",
            opts=opts,
        )

    card_y0 = int(h * 0.60)
    time_w = int(_text_w(draw, texts["time_text"], val_f))
    card_x0 = tx
    card_x1 = min(w - int(w * 0.14), tx + time_w + int(w * 0.20))
    draw_value_panel(
        draw,
        card_x0,
        card_y0,
        card_x1,
        card_y0 + int(h * 0.24),
        theme["top_bg"],
        outline=theme["border"],
        radius=sc["radius_md"],
        outline_width=max(2, h // 150),
    )
    _draw_text(draw, card_x0 + int(w * 0.03), card_y0 + int(h * 0.035), texts["bottom_text"], lbl_f, theme["bottom_text"])
    _draw_text(draw, card_x0 + int(w * 0.03), card_y0 + int(h * 0.11), texts["time_text"], val_f, theme["bottom_text"], opts=opts, box_name="time_text_box", box_pad=12)

    if opts.get("show_border", True):
        illu["border_fn"](draw, w, h, theme["border"])


# ── 6. BLUEPRINT ──────────────────────────────────────────────────────────────

def render_blueprint(img, draw, w, h, texts, theme, lf, illu, opts):
    # Blueprint uses ink_high_contrast styling overrides; work with what's given
    _section_bg(img, draw, 0, 0, w, h, theme["bg"])

    # Grid background
    grid_c = tuple(max(0, c - 15) if theme["bg"][0] > 128 else min(255, c + 15)
                   for c in theme["bg"])
    grid_sp = int(h * 0.065)
    for gy in range(0, h, grid_sp):
        draw.line([0, gy, w, gy], fill=grid_c, width=1)
    for gx in range(0, w, grid_sp):
        draw.line([gx, 0, gx, h], fill=grid_c, width=1)

    sc = layout_scale(w, h)
    lbl_f = lf("label")
    val_f = lf("value")
    pad = sc["pad_x"]

    draw_corner_accents(
        draw,
        int(w * 0.03),
        int(h * 0.04),
        w - int(w * 0.03),
        h - int(h * 0.04),
        int(h * 0.08),
        theme["border"],
        lw=2,
    )

    if opts.get("show_icons", True):
        _draw_icon_disc_tracked(
            draw,
            w - int(w * 0.14),
            int(h * 0.23),
            int(h * 0.105),
            theme["mid_bg"],
            theme["border"],
            illu["clock_fn"],
            theme["top_text"],
            opts=opts,
            icon_name="clock",
            ring_width=max(2, h // 150),
        )

    draw_label_chip(
        draw,
        pad,
        int(h * 0.12),
        texts["top_text"],
        lbl_f,
        theme["top_text"],
        theme["mid_bg"],
        pad_x=16,
        pad_y=9,
        radius=sc["radius_sm"],
    )
    main_y = int(h * 0.27)
    _draw_text(draw, pad, main_y, texts["main_text"], val_f, theme["top_text"], opts=opts, box_name="main_text_box", box_pad=14)

    if opts.get("show_divider", True):
        _draw_editorial_divider_tracked(
            draw,
            pad,
            main_y + int(h * 0.19),
            pad + int(w * 0.48),
            theme["divider"],
            sc["divider_mid"],
            style="dashed",
            opts=opts,
        )

    bottom_y = int(h * 0.63)
    _draw_text(draw, pad, bottom_y, texts["bottom_text"], lbl_f, theme["bottom_text"])
    _draw_text(draw, pad, bottom_y + int(h * 0.11), texts["time_text"], val_f, theme["bottom_text"], opts=opts, box_name="time_text_box", box_pad=12)




# ── 7. DOODLE ─────────────────────────────────────────────────────────────────

def render_doodle(img, draw, w, h, texts, theme, lf, illu, opts):
    jitter = illu.get("jitter_strength")
    _PAPER = (248, 246, 240)
    draw_paper_texture(draw, w, h, base_color=_PAPER, density=0.0016, strength=9)

    # Contrast-safe colours for the paper surface
    top_tc = _surf_tc(theme["top_text"],    _PAPER)
    bot_tc = _surf_tc(theme["bottom_text"], _PAPER)
    acc_c  = _surf_tc(theme["accent"],  _PAPER, min_ratio=DIVIDER_MIN_RATIO)
    div_c  = _surf_tc(theme["divider"], _PAPER, min_ratio=DIVIDER_MIN_RATIO)
    brd_c  = _surf_tc(theme["border"],  _PAPER, min_ratio=DIVIDER_MIN_RATIO)

    sc = layout_scale(w, h)
    lbl_f = lf("label")
    val_f = lf("value")
    gap = int(h * 0.026)
    pad = sc["pad_x"]

    if opts.get("show_border", True):
        draw_double_sketch_border(
            draw,
            w,
            h,
            brd_c,
            width=max(2, h // 120),
            jitter_strength=jitter,
            gap=max(8, h // 52),
        )

    lbl_h = int(h * 0.088)
    y = int(h * 0.10)

    if opts.get("show_icons", True):
        icon_r = int(h * 0.105)
        clock_shown = _draw_free_icon_tracked(
            draw,
            pad + icon_r,
            y + icon_r,
            icon_r,
            illu["clock_fn"],
            top_tc,
            opts=opts,
            icon_name="clock",
        )
        tx = pad + icon_r * 2 + int(pad * 0.55) if clock_shown else pad
    else:
        tx = pad

    _draw_text(draw, tx, y, texts["top_text"], lbl_f, top_tc)
    y += int(h * 0.10)
    _draw_text(draw, tx, y, texts["main_text"], val_f, top_tc, opts=opts, box_name="main_text_box", box_pad=14)

    tw = int(_text_w(draw, texts["main_text"], val_f))
    ul_y = y + int(h * 0.19)
    ul_x1 = min(w - pad, tx + tw + int(w * 0.10))
    draw_scribble_underline(
        draw,
        tx,
        ul_y,
        ul_x1,
        acc_c,
        width=max(4, h // 85),
        jitter_strength=jitter,
    )
    _track_box(opts, "divider_box", (tx, ul_y - int(h * 0.03), ul_x1, ul_y + int(h * 0.03)), pad=8)

    # Decorative hand-drawn arrow near divider region.
    arrow_y = ul_y + int(h * 0.06)
    arrow_x1 = min(w - pad, tx + int(w * 0.28))
    draw_handdrawn_arrow(
        draw,
        tx,
        arrow_y,
        arrow_x1,
        arrow_y,
        div_c,
        width=max(2, h // 120),
        jitter_strength=jitter,
    )
    _track_box(opts, "divider_box", (tx, arrow_y - int(h * 0.03), arrow_x1, arrow_y + int(h * 0.03)), pad=8)

    y = arrow_y + int(h * 0.05)
    if opts.get("show_divider", True):
        div_x1 = min(w - pad, tx + int(w * 0.52))
        draw_jittered_line(
            draw,
            tx,
            y,
            div_x1,
            y,
            div_c,
            width=max(3, h // 105),
            jitter_strength=jitter,
            passes=2,
            segments=10,
        )
        _track_box(opts, "divider_box", (tx, y - int(h * 0.03), div_x1, y + int(h * 0.03)), pad=8)
        y += int(h * 0.045)

    door_shown = False
    if opts.get("show_icons", True):
        box = int(h * 0.16)
        door_radius = int(box * 0.26)
        if _should_show_icon(opts.get("layout_key", ""), "door", door_radius * 2):
            draw_jittered_rounded_rectangle(
                draw,
                pad,
                y,
                pad + box,
                y + box,
                radius=max(12, h // 18),
                color=brd_c,
                width=max(2, h // 125),
                jitter_strength=jitter,
                passes=2,
            )
            door_shown = _draw_free_icon_tracked(
                draw,
                pad + box // 2,
                y + box // 2,
                door_radius,
                illu["door_fn"],
                bot_tc,
                opts=opts,
                icon_name="door",
            )
    if door_shown:
        bx = pad + box + int(w * 0.04)
    else:
        bx = pad

    _draw_text(draw, bx, y, texts["bottom_text"], lbl_f, bot_tc)
    y += int(h * 0.10)

    # Marker-like accent under time text (underline style).
    txw = int(_text_w(draw, texts["time_text"], val_f))
    _draw_text(draw, bx, y, texts["time_text"], val_f, bot_tc, opts=opts, box_name="time_text_box", box_pad=12)
    marker_x1 = min(w - pad, bx + txw + int(w * 0.06))
    draw_marker_stroke(
        draw,
        bx,
        y + int(h * 0.185),
        marker_x1,
        y + int(h * 0.185),
        acc_c,
        width=max(9, h // 21),
        jitter_strength=jitter,
    )
    _track_box(opts, "divider_box", (bx, y + int(h * 0.145), marker_x1, y + int(h * 0.225)), pad=6)


# ── 8. FRAMED ─────────────────────────────────────────────────────────────────

def render_framed(img, draw, w, h, texts, theme, lf, illu, opts):
    sc = layout_scale(w, h)
    _section_bg(img, draw, 0, 0, w, h, theme["mid_bg"])

    mat = int(min(w, h) * 0.050)
    inner_x0, inner_y0 = mat, mat
    inner_x1, inner_y1 = w - mat, h - mat
    draw_value_panel(
        draw,
        inner_x0,
        inner_y0,
        inner_x1,
        inner_y1,
        theme["bg"],
        outline=theme["border"],
        radius=sc["radius_md"],
        outline_width=max(3, mat // 5),
    )

    iw = inner_x1 - inner_x0
    ih = inner_y1 - inner_y0
    pad = int(iw * 0.06)
    div_y = inner_y0 + ih // 2
    if opts.get("show_divider", True):
        _draw_editorial_divider_tracked(
            draw,
            inner_x0 + int(iw * 0.08),
            div_y,
            inner_x1 - int(iw * 0.08),
            theme["divider"],
            sc["divider_mid"],
            style="bar",
            opts=opts,
        )

    tx = inner_x0 + pad
    if opts.get("show_icons", True):
        _draw_icon_tile_tracked(
            draw,
            inner_x1 - int(iw * 0.11),
            inner_y0 + int(ih * 0.22),
            int(h * 0.15),
            theme["mid_bg"],
            theme["border"],
            illu["clock_fn"],
            theme["top_text"],
            opts=opts,
            icon_name="clock",
            outline_width=max(2, h // 150),
        )
        _draw_icon_tile_tracked(
            draw,
            inner_x1 - int(iw * 0.11),
            inner_y0 + int(ih * 0.72),
            int(h * 0.14),
            theme["mid_bg"],
            theme["border"],
            illu["door_fn"],
            theme["bottom_text"],
            opts=opts,
            icon_name="door",
            outline_width=max(2, h // 150),
        )

    draw_label_chip(draw, tx, inner_y0 + int(ih * 0.09), texts["top_text"], lf("label"), theme["top_text"], theme["mid_bg"], pad_x=16, pad_y=8, radius=sc["radius_sm"])
    _draw_text(draw, tx, inner_y0 + int(ih * 0.23), texts["main_text"], lf("value"), theme["top_text"], opts=opts, box_name="main_text_box", box_pad=14)
    _draw_text(draw, tx, inner_y0 + int(ih * 0.61), texts["bottom_text"], lf("label"), theme["bottom_text"])
    _draw_text(draw, tx, inner_y0 + int(ih * 0.73), texts["time_text"], lf("value"), theme["bottom_text"], opts=opts, box_name="time_text_box", box_pad=12)

    if opts.get("show_border", True):
        draw_editorial_frame(draw, w, h, theme["border"], inset=max(4, mat // 3), lw=max(2, mat // 5), inner_gap=0, radius=sc["radius_md"])


# ── 9. STICKER ────────────────────────────────────────────────────────────────

def render_sticker(img, draw, w, h, texts, theme, lf, illu, opts):
    _section_bg(img, draw, 0, 0, w, h, theme["bg"])
    sc = layout_scale(w, h)
    lbl_f = lf("label")
    val_f = lf("value")
    pad = sc["pad_x"]
    stripe_h = int(h * 0.11)

    draw_accent_band(draw, 0, 0, w, stripe_h, theme["accent"])

    if opts.get("show_icons", True):
        _draw_icon_tile_tracked(
            draw,
            w - pad - int(h * 0.06),
            stripe_h // 2,
            int(h * 0.12),
            theme["bg"],
            None,
            illu["clock_fn"],
            theme["accent"],
            opts=opts,
            icon_name="clock",
        )

    label_y = int(h * 0.16)
    draw_label_chip(
        draw,
        pad,
        label_y,
        texts["top_text"],
        lbl_f,
        theme["top_text"],
        theme["mid_bg"],
        pad_x=18,
        pad_y=10,
        radius=sc["radius_sm"],
    )

    pill_y = label_y + int(h * 0.11)
    pill_h = int(h * 0.20)
    text_w = int(_text_w(draw, texts["main_text"], val_f))
    pill_x0 = pad
    pill_x1 = min(w - pad - int(w * 0.12), pad + text_w + int(w * 0.18))
    fill_lum = sum(theme["accent"]) / 3
    hero_tc = (255, 255, 255) if fill_lum < 128 else (10, 10, 10)
    draw_value_panel(draw, pill_x0, pill_y, pill_x1, pill_y + pill_h, theme["accent"], radius=pill_h // 2)
    _draw_text(draw, (pill_x0 + pill_x1) // 2, pill_y + pill_h // 2, texts["main_text"], val_f, hero_tc, "mm", opts=opts, box_name="main_text_box", box_pad=12)

    divider_y = pill_y + pill_h + int(h * 0.06)
    if opts.get("show_divider", True):
        _draw_editorial_divider_tracked(
            draw,
            pad,
            divider_y,
            pill_x1,
            theme["divider"],
            sc["divider_mid"],
            style="split",
            opts=opts,
        )

    bottom_y = divider_y + int(h * 0.06)
    door_shown = False
    if opts.get("show_icons", True):
        tile = int(h * 0.15)
        door_shown = _draw_icon_tile_tracked(
            draw,
            pad + tile // 2,
            bottom_y + tile // 2,
            tile,
            theme["mid_bg"],
            theme["border"],
            illu["door_fn"],
            theme["bottom_text"],
            opts=opts,
            icon_name="door",
            outline_width=max(2, h // 150),
        )
    if door_shown:
        bx = pad + tile + int(w * 0.035)
    else:
        bx = pad
    _draw_text(draw, bx, bottom_y, texts["bottom_text"], lbl_f, theme["bottom_text"])
    time_y = bottom_y + int(h * 0.11)
    _draw_text(draw, bx, time_y, texts["time_text"], val_f, theme["bottom_text"], opts=opts, box_name="time_text_box", box_pad=12)

    time_w = int(_text_w(draw, texts["time_text"], val_f))
    _draw_editorial_divider_tracked(
        draw,
        bx,
        time_y + int(h * 0.19),
        min(w - pad, bx + time_w + int(w * 0.08)),
        theme["accent"],
        sc["divider_thick"],
        style="underline",
        opts=opts,
    )

    if opts.get("show_border", True):
        illu["border_fn"](draw, w, h, theme["border"])


# ── 10. LATERAL ───────────────────────────────────────────────────────────────

def render_lateral(img, draw, w, h, texts, theme, lf, illu, opts):
    sc = layout_scale(w, h)
    _section_bg(img, draw, 0, 0, w, h, theme["bg"])

    side_x0 = int(w * 0.02)
    side_x1 = int(w * 0.27)
    draw_value_panel(
        draw,
        side_x0,
        int(h * 0.04),
        side_x1,
        h - int(h * 0.04),
        theme["accent"],
        outline=theme["border"],
        radius=sc["radius_lg"],
        outline_width=max(2, h // 145),
    )
    _track_box(opts, "icon_panel_box", (side_x0, int(h * 0.04), side_x1, h - int(h * 0.04)), pad=8)

    if opts.get("show_icons", True):
        cx = (side_x0 + side_x1) // 2
        _draw_icon_disc_tracked(
            draw,
            cx,
            int(h * 0.24),
            int(h * 0.105),
            theme["bg"],
            theme["bg"],
            illu["clock_fn"],
            theme["accent"],
            opts=opts,
            icon_name="clock",
            ring_width=max(2, h // 160),
        )
        draw_accent_band(
            draw,
            side_x0 + int(w * 0.03),
            int(h * 0.46),
            side_x1 - int(w * 0.03),
            int(h * 0.48),
            theme["bg"],
            radius=sc["radius_sm"],
        )
        _draw_icon_tile_tracked(
            draw,
            cx,
            int(h * 0.70),
            int(h * 0.17),
            theme["bg"],
            theme["bg"],
            illu["door_fn"],
            theme["accent"],
            opts=opts,
            icon_name="door",
        )

    lbl_f = lf("label")
    val_f = lf("value")
    tx = side_x1 + int(w * 0.05)
    pad = sc["pad_x"]
    draw_label_chip(
        draw,
        tx,
        int(h * 0.10),
        texts["top_text"],
        lbl_f,
        theme["top_text"],
        theme["mid_bg"],
        pad_x=18,
        pad_y=10,
        radius=sc["radius_sm"],
    )
    main_y = int(h * 0.24)
    _draw_text(draw, tx, main_y, texts["main_text"], val_f, theme["top_text"], opts=opts, box_name="main_text_box", box_pad=14)

    if opts.get("show_divider", True):
        _draw_editorial_divider_tracked(
            draw,
            tx,
            main_y + int(h * 0.20),
            min(w - pad, tx + int(w * 0.46)),
            theme["divider"],
            sc["divider_mid"],
            style="bar",
            opts=opts,
        )

    bottom_y = int(h * 0.63)
    _draw_text(draw, tx, bottom_y, texts["bottom_text"], lbl_f, theme["bottom_text"])
    _draw_text(draw, tx, bottom_y + int(h * 0.11), texts["time_text"], val_f, theme["bottom_text"], opts=opts, box_name="time_text_box", box_pad=12)

    if opts.get("show_border", True):
        illu["border_fn"](draw, w, h, theme["border"])


# ── 11. SKETCH NOTE ──────────────────────────────────────────────────────────

def render_sketch_note(img, draw, w, h, texts, theme, lf, illu, opts):
    jitter = illu.get("jitter_strength")
    _PAPER = (252, 250, 245)  # inner note surface (lighter than outer texture)
    draw_paper_texture(draw, w, h, base_color=(249, 247, 242), density=0.0018, strength=8)

    # Contrast-safe colours for the paper note surface
    top_tc = _surf_tc(theme["top_text"],    _PAPER)
    bot_tc = _surf_tc(theme["bottom_text"], _PAPER)
    acc_c  = _surf_tc(theme["accent"],  _PAPER, min_ratio=DIVIDER_MIN_RATIO)
    div_c  = _surf_tc(theme["divider"], _PAPER, min_ratio=DIVIDER_MIN_RATIO)
    brd_c  = _surf_tc(theme["border"],  _PAPER, min_ratio=DIVIDER_MIN_RATIO)

    sc = layout_scale(w, h)
    lbl_f = lf("label")
    val_f = lf("value")
    sub_f = lf("sub")
    pad = sc["pad_x"]
    gap = int(h * 0.024)

    # Inner note area
    nx0, ny0 = pad, int(h * 0.07)
    nx1, ny1 = w - pad, h - int(h * 0.07)
    draw.rectangle([nx0 + 4, ny0 + 4, nx1 - 4, ny1 - 4], fill=_PAPER)
    draw_jittered_rounded_rectangle(
        draw,
        nx0,
        ny0,
        nx1,
        ny1,
        radius=max(12, h // 18),
        color=brd_c,
        width=max(2, h // 130),
        jitter_strength=jitter,
        passes=2,
    )

    # Small "paper tape" strips.
    tape_c = (227, 222, 205)
    tape_w = int(w * 0.20)
    tape_h = int(h * 0.040)
    draw.rectangle([w // 2 - tape_w - 8, ny0 - tape_h // 2, w // 2 - 8, ny0 + tape_h // 2], fill=tape_c)
    draw.rectangle([w // 2 + 8, ny0 - tape_h // 2, w // 2 + tape_w + 8, ny0 + tape_h // 2], fill=tape_c)

    y = ny0 + int(h * 0.07)
    if opts.get("show_icons", True):
        ir = int(h * 0.082)
        _draw_free_icon_tracked(draw, nx1 - int(w * 0.12), y + ir, ir, illu["clock_fn"], top_tc, opts=opts, icon_name="clock")

    _draw_text(draw, nx0 + int(w * 0.03), y, texts["top_text"], lbl_f, top_tc)
    y += int(h * 0.094)
    _draw_text(draw, nx0 + int(w * 0.03), y, texts["main_text"], val_f, top_tc, opts=opts, box_name="main_text_box", box_pad=14)
    y += int(h * 0.212)

    sketch_x1 = nx1 - int(w * 0.10)
    draw_scribble_underline(
        draw,
        nx0 + int(w * 0.03),
        y,
        sketch_x1,
        acc_c,
        width=max(4, h // 92),
        jitter_strength=jitter,
    )
    _track_box(opts, "divider_box", (nx0 + int(w * 0.03), y - int(h * 0.03), sketch_x1, y + int(h * 0.03)), pad=8)
    y += int(h * 0.06)

    if opts.get("show_divider", True):
        line_x0 = nx0 + int(w * 0.03)
        line_x1 = nx1 - int(w * 0.03)
        draw_jittered_line(
            draw,
            line_x0,
            y,
            line_x1,
            y,
            div_c,
            width=max(2, h // 125),
            jitter_strength=jitter,
            passes=2,
            segments=10,
        )
        _track_box(opts, "divider_box", (line_x0, y - int(h * 0.03), line_x1, y + int(h * 0.03)), pad=8)
        y += int(h * 0.032)

    if opts.get("show_icons", True):
        ir2 = int(h * 0.078)
        _draw_free_icon_tracked(draw, nx1 - int(w * 0.12), y + ir2, ir2, illu["door_fn"], bot_tc, opts=opts, icon_name="door")

    _draw_text(draw, nx0 + int(w * 0.03), y, texts["bottom_text"], sub_f, bot_tc)
    y += int(h * 0.074) + gap
    _draw_text(draw, nx0 + int(w * 0.03), y, texts["time_text"], val_f, bot_tc, opts=opts, box_name="time_text_box", box_pad=12)

    txw = int(_text_w(draw, texts["time_text"], val_f))
    marker_x1 = min(nx1 - int(w * 0.16), nx0 + int(w * 0.03) + txw + int(w * 0.05))
    draw_marker_stroke(
        draw,
        nx0 + int(w * 0.03),
        y + int(h * 0.165),
        marker_x1,
        y + int(h * 0.165),
        acc_c,
        width=max(8, h // 24),
        jitter_strength=jitter,
    )
    _track_box(opts, "divider_box", (nx0 + int(w * 0.03), y + int(h * 0.125), marker_x1, y + int(h * 0.205)), pad=6)

    if opts.get("show_border", True):
        draw_double_sketch_border(
            draw,
            w,
            h,
            brd_c,
            width=max(2, h // 120),
            jitter_strength=jitter,
            gap=max(8, h // 54),
        )


# ── 12. MARKER BOARD ─────────────────────────────────────────────────────────

def render_marker_board(img, draw, w, h, texts, theme, lf, illu, opts):
    jitter = illu.get("jitter_strength")
    _PAPER = (252, 252, 246)  # inner board surface
    draw_paper_texture(draw, w, h, base_color=(245, 246, 239), density=0.0014, strength=8)

    # Contrast-safe colours for the whiteboard surface
    top_tc = _surf_tc(theme["top_text"],    _PAPER)
    bot_tc = _surf_tc(theme["bottom_text"], _PAPER)
    acc_c  = _surf_tc(theme["accent"],  _PAPER, min_ratio=DIVIDER_MIN_RATIO)
    div_c  = _surf_tc(theme["divider"], _PAPER, min_ratio=DIVIDER_MIN_RATIO)
    brd_c  = _surf_tc(theme["border"],  _PAPER, min_ratio=DIVIDER_MIN_RATIO)

    sc = layout_scale(w, h)
    lbl_f = lf("label")
    val_f = lf("value")
    sub_f = lf("sub")
    pad = int(w * 0.05)

    bx0, by0 = pad, int(h * 0.09)
    bx1, by1 = w - pad, h - int(h * 0.09)

    # Board surface
    draw.rectangle([bx0 + 4, by0 + 4, bx1 - 4, by1 - 4], fill=_PAPER)
    draw_jittered_rounded_rectangle(
        draw,
        bx0,
        by0,
        bx1,
        by1,
        radius=max(14, h // 16),
        color=brd_c,
        width=max(2, h // 125),
        jitter_strength=jitter,
        passes=2,
    )

    tx = bx0 + int(w * 0.05)
    y = by0 + int(h * 0.065)

    draw_marker_stroke(
        draw,
        tx,
        y + int(h * 0.034),
        min(bx1 - int(w * 0.05), tx + int(w * 0.50)),
        y + int(h * 0.034),
        acc_c,
        width=max(11, h // 15),
        jitter_strength=jitter,
    )
    _draw_text(draw, tx, y, texts["top_text"], lbl_f, top_tc)
    y += int(h * 0.095)

    _draw_text(draw, tx, y, texts["main_text"], val_f, top_tc, opts=opts, box_name="main_text_box", box_pad=14)
    y += int(h * 0.215)

    if opts.get("show_icons", True):
        ir = int(h * 0.085)
        _draw_free_icon_tracked(draw, bx1 - int(w * 0.12), by0 + int(h * 0.16), ir, illu["clock_fn"], top_tc, opts=opts, icon_name="clock")

    if opts.get("show_divider", True):
        arrow_x1 = min(bx1 - int(w * 0.12), tx + int(w * 0.34))
        draw_handdrawn_arrow(
            draw,
            tx,
            y,
            arrow_x1,
            y,
            div_c,
            width=max(3, h // 104),
            jitter_strength=jitter,
        )
        _track_box(opts, "divider_box", (tx, y - int(h * 0.03), arrow_x1, y + int(h * 0.03)), pad=8)
        y += int(h * 0.058)

    _draw_text(draw, tx, y, texts["bottom_text"], sub_f, bot_tc)
    y += int(h * 0.084)

    _draw_text(draw, tx, y, texts["time_text"], val_f, bot_tc, opts=opts, box_name="time_text_box", box_pad=12)
    marker_x1 = min(bx1 - int(w * 0.05), tx + int(w * 0.38))
    draw_marker_stroke(
        draw,
        tx,
        y + int(h * 0.182),
        marker_x1,
        y + int(h * 0.182),
        acc_c,
        width=max(9, h // 21),
        jitter_strength=jitter,
    )
    _track_box(opts, "divider_box", (tx, y + int(h * 0.145), marker_x1, y + int(h * 0.225)), pad=6)

    if opts.get("show_icons", True):
        ir2 = int(h * 0.080)
        _draw_free_icon_tracked(draw, bx1 - int(w * 0.12), y + int(h * 0.06), ir2, illu["door_fn"], bot_tc, opts=opts, icon_name="door")

    if opts.get("show_border", True):
        draw_double_sketch_border(
            draw,
            w,
            h,
            brd_c,
            width=max(2, h // 124),
            jitter_strength=jitter,
            gap=max(7, h // 56),
        )


# ── 13. DOODLE CARD ──────────────────────────────────────────────────────────

def render_doodle_card(img, draw, w, h, texts, theme, lf, illu, opts):
    jitter = illu.get("jitter_strength")
    draw_paper_texture(draw, w, h, base_color=(247, 245, 239), density=0.0016, strength=10)

    sc = layout_scale(w, h)
    lbl_f = lf("label")
    val_f = lf("value")
    sub_f = lf("sub")

    pad = sc["pad_x"]
    card_gap = int(h * 0.040)
    card_h = int((h - pad * 2 - card_gap) / 2)

    c1 = (pad, pad, w - pad - int(w * 0.04), pad + card_h)
    c2 = (pad + int(w * 0.04), pad + card_h + card_gap, w - pad, h - pad)

    draw.rectangle([c1[0] + 4, c1[1] + 4, c1[2] - 4, c1[3] - 4], fill=theme["top_bg"])
    draw.rectangle([c2[0] + 4, c2[1] + 4, c2[2] - 4, c2[3] - 4], fill=theme["bottom_bg"])

    draw_jittered_rounded_rectangle(
        draw,
        c1[0], c1[1], c1[2], c1[3],
        radius=max(14, h // 20),
        color=theme["border"],
        width=max(2, h // 125),
        jitter_strength=jitter,
        passes=2,
    )
    draw_jittered_rounded_rectangle(
        draw,
        c2[0], c2[1], c2[2], c2[3],
        radius=max(14, h // 20),
        color=theme["border"],
        width=max(2, h // 125),
        jitter_strength=jitter,
        passes=2,
    )

    # Connector arrow between cards.
    mid_y = c1[3] + card_gap // 2
    draw_handdrawn_arrow(
        draw,
        int(w * 0.31),
        mid_y,
        int(w * 0.69),
        mid_y,
        theme["accent"],
        width=max(3, h // 104),
        jitter_strength=jitter,
    )
    _track_box(opts, "divider_box", (int(w * 0.31), mid_y - int(h * 0.03), int(w * 0.69), mid_y + int(h * 0.03)), pad=8)

    # Card 1 (top)
    t1x = c1[0] + int(w * 0.04)
    t1y = c1[1] + int(h * 0.045)
    if opts.get("show_icons", True):
        ir = int(h * 0.078)
        _draw_free_icon_tracked(draw, c1[2] - int(w * 0.09), t1y + ir, ir, illu["clock_fn"], theme["top_text"], opts=opts, icon_name="clock")
    _draw_text(draw, t1x, t1y, texts["top_text"], lbl_f, theme["top_text"])
    _draw_text(draw, t1x, t1y + int(h * 0.092), texts["main_text"], val_f, theme["top_text"], opts=opts, box_name="main_text_box", box_pad=14)

    # Card 2 (bottom)
    t2x = c2[0] + int(w * 0.04)
    t2y = c2[1] + int(h * 0.045)
    if opts.get("show_icons", True):
        ir2 = int(h * 0.074)
        _draw_free_icon_tracked(draw, c2[2] - int(w * 0.09), t2y + ir2, ir2, illu["door_fn"], theme["bottom_text"], opts=opts, icon_name="door")
    _draw_text(draw, t2x, t2y, texts["bottom_text"], sub_f, theme["bottom_text"])
    _draw_text(draw, t2x, t2y + int(h * 0.092), texts["time_text"], val_f, theme["bottom_text"], opts=opts, box_name="time_text_box", box_pad=12)

    if opts.get("show_divider", True):
        underline_x1 = min(c2[2] - int(w * 0.12), t2x + int(w * 0.42))
        draw_scribble_underline(
            draw,
            t2x,
            t2y + int(h * 0.18),
            underline_x1,
            theme["accent"],
            width=max(4, h // 94),
            jitter_strength=jitter,
        )
        _track_box(opts, "divider_box", (t2x, t2y + int(h * 0.15), underline_x1, t2y + int(h * 0.21)), pad=8)

    if opts.get("show_border", True):
        draw_double_sketch_border(
            draw,
            w,
            h,
            theme["border"],
            width=max(2, h // 124),
            jitter_strength=jitter,
            gap=max(7, h // 58),
        )


# ── 14. HERO BANNER ──────────────────────────────────────────────────────────

def render_hero_banner(img, draw, w, h, texts, theme, lf, illu, opts):
    sc = layout_scale(w, h)
    pad = sc["pad_x"]
    lbl_f = lf("label")
    val_f = lf("value")
    _section_bg(img, draw, 0, 0, w, h, theme["bg"])

    hero_x0 = pad
    hero_y0 = int(h * 0.10)
    hero_x1 = int(w * 0.74)
    hero_y1 = int(h * 0.46)
    fill_lum = sum(theme["accent"]) / 3
    hero_tc = (255, 255, 255) if fill_lum < 128 else (10, 10, 10)
    draw_value_panel(draw, hero_x0, hero_y0, hero_x1, hero_y1, theme["accent"], radius=sc["radius_lg"])
    draw_label_chip(draw, hero_x0 + int(w * 0.03), hero_y0 + int(h * 0.03), texts["top_text"], lbl_f, theme["accent"], theme["bg"], pad_x=18, pad_y=10, radius=sc["radius_sm"])
    _draw_text(draw, hero_x0 + int(w * 0.03), hero_y0 + int(h * 0.17), texts["main_text"], val_f, hero_tc, opts=opts, box_name="main_text_box", box_pad=14)

    if opts.get("show_icons", True):
        _draw_icon_disc_tracked(
            draw,
            w - pad - int(h * 0.14),
            int(h * 0.24),
            int(h * 0.13),
            theme["mid_bg"],
            theme["border"],
            illu["clock_fn"],
            theme["top_text"],
            opts=opts,
            icon_name="clock",
            ring_width=max(2, h // 150),
        )

    lower_x0 = pad
    lower_y0 = int(h * 0.58)
    lower_x1 = int(w * 0.56)
    lower_y1 = int(h * 0.86)
    draw_value_panel(draw, lower_x0, lower_y0, lower_x1, lower_y1, theme["mid_bg"], outline=theme["border"], radius=sc["radius_md"], outline_width=max(2, h // 150))
    door_shown = False
    if opts.get("show_icons", True):
        door_shown = _draw_icon_tile_tracked(draw, lower_x0 + int(h * 0.09), lower_y0 + int(h * 0.11), int(h * 0.15), theme["bg"], theme["border"], illu["door_fn"], theme["bottom_text"], opts=opts, icon_name="door", outline_width=max(2, h // 150))
    if door_shown:
        tx = lower_x0 + int(h * 0.18)
    else:
        tx = lower_x0 + int(w * 0.03)
    _draw_text(draw, tx, lower_y0 + int(h * 0.04), texts["bottom_text"], lbl_f, theme["bottom_text"])
    _draw_text(draw, tx, lower_y0 + int(h * 0.14), texts["time_text"], val_f, theme["bottom_text"], opts=opts, box_name="time_text_box", box_pad=12)

    if opts.get("show_border", True):
        illu["border_fn"](draw, w, h, theme["border"])


# ── 15. EDITORIAL ────────────────────────────────────────────────────────────

def render_editorial(img, draw, w, h, texts, theme, lf, illu, opts):
    sc = layout_scale(w, h)
    pad = sc["pad_x"]
    lbl_f = lf("label")
    val_f = lf("value")
    _section_bg(img, draw, 0, 0, w, h, theme["bg"])
    draw_corner_accents(draw, int(w * 0.03), int(h * 0.04), w - int(w * 0.03), h - int(h * 0.04), int(h * 0.08), theme["border"], lw=3)

    draw_label_chip(draw, pad, int(h * 0.10), texts["top_text"], lbl_f, theme["top_text"], theme["mid_bg"], pad_x=18, pad_y=10, radius=sc["radius_sm"])
    _draw_text(draw, pad, int(h * 0.26), texts["main_text"], val_f, theme["top_text"], opts=opts, box_name="main_text_box", box_pad=14)
    if opts.get("show_divider", True):
        _draw_editorial_divider_tracked(draw, pad, int(h * 0.57), int(w * 0.78), theme["divider"], sc["divider_mid"], style="split", opts=opts)

    if opts.get("show_icons", True):
        _draw_icon_disc_tracked(draw, w - pad - int(h * 0.11), int(h * 0.20), int(h * 0.11), theme["mid_bg"], theme["border"], illu["clock_fn"], theme["top_text"], opts=opts, icon_name="clock", ring_width=max(2, h // 150))

    bottom_y = int(h * 0.66)
    _draw_text(draw, pad, bottom_y, texts["bottom_text"], lbl_f, theme["bottom_text"])
    time_w = int(_text_w(draw, texts["time_text"], val_f))
    card_x1 = w - pad
    card_x0 = max(int(w * 0.42), card_x1 - time_w - int(w * 0.16))
    draw_value_panel(draw, card_x0, int(h * 0.62), card_x1, int(h * 0.88), theme["mid_bg"], outline=theme["border"], radius=sc["radius_md"], outline_width=max(2, h // 150))
    _draw_text(draw, card_x0 + int(w * 0.03), int(h * 0.71), texts["time_text"], val_f, theme["bottom_text"], opts=opts, box_name="time_text_box", box_pad=12)

    if opts.get("show_border", True):
        illu["border_fn"](draw, w, h, theme["border"])


# ── 16. MODERN WIDGET ────────────────────────────────────────────────────────

def render_modern_widget(img, draw, w, h, texts, theme, lf, illu, opts):
    sc = layout_scale(w, h)
    fx0 = int(w * 0.04)
    fy0 = int(h * 0.06)
    fx1 = w - int(w * 0.04)
    fy1 = h - int(h * 0.06)
    lbl_f = lf("label")
    val_f = lf("value")
    _section_bg(img, draw, 0, 0, w, h, theme["bg"])
    draw_value_panel(draw, fx0, fy0, fx1, fy1, theme["top_bg"], outline=theme["border"], radius=sc["radius_lg"], outline_width=max(2, h // 150))
    _track_box(opts, "icon_panel_box", (fx1 - int(w * 0.18), fy0 + int(h * 0.10), fx1 - int(w * 0.02), fy0 + int(h * 0.58)), pad=8)

    draw_label_chip(draw, fx0 + int(w * 0.03), fy0 + int(h * 0.03), texts["top_text"], lbl_f, theme["top_text"], theme["mid_bg"], pad_x=18, pad_y=10, radius=sc["radius_sm"])
    hero_x0 = fx0 + int(w * 0.03)
    hero_y0 = fy0 + int(h * 0.16)
    hero_x1 = fx1 - int(w * 0.18)
    hero_y1 = fy0 + int(h * 0.40)
    draw_value_panel(draw, hero_x0, hero_y0, hero_x1, hero_y1, theme["mid_bg"], radius=sc["radius_md"])
    _draw_text(draw, hero_x0 + int(w * 0.03), hero_y0 + int(h * 0.08), texts["main_text"], val_f, theme["top_text"], opts=opts, box_name="main_text_box", box_pad=14)

    if opts.get("show_icons", True):
        ix = fx1 - int(w * 0.10)
        _draw_icon_tile_tracked(draw, ix, fy0 + int(h * 0.20), int(h * 0.15), theme["bg"], theme["border"], illu["clock_fn"], theme["top_text"], opts=opts, icon_name="clock", outline_width=max(2, h // 150))
        _draw_icon_tile_tracked(draw, ix, fy0 + int(h * 0.46), int(h * 0.14), theme["bg"], theme["border"], illu["door_fn"], theme["bottom_text"], opts=opts, icon_name="door", outline_width=max(2, h // 150))

    lower_x0 = fx0 + int(w * 0.03)
    lower_y0 = fy0 + int(h * 0.54)
    lower_x1 = int(w * 0.56)
    lower_y1 = fy1 - int(h * 0.03)
    draw_value_panel(draw, lower_x0, lower_y0, lower_x1, lower_y1, theme["bg"], outline=theme["border"], radius=sc["radius_md"], outline_width=max(2, h // 150))
    _draw_text(draw, lower_x0 + int(w * 0.03), lower_y0 + int(h * 0.03), texts["bottom_text"], lbl_f, theme["bottom_text"])
    _draw_text(draw, lower_x0 + int(w * 0.03), lower_y0 + int(h * 0.13), texts["time_text"], val_f, theme["bottom_text"], opts=opts, box_name="time_text_box", box_pad=12)

    if opts.get("show_border", True):
        illu["border_fn"](draw, w, h, theme["border"])


# ── 17. FOCUS MODE ───────────────────────────────────────────────────────────

def render_focus_mode(img, draw, w, h, texts, theme, lf, illu, opts):
    sc = layout_scale(w, h)
    lbl_f = lf("label")
    val_f = lf("value")
    _section_bg(img, draw, 0, 0, w, h, theme["bg"])

    if opts.get("show_border", True):
        draw_editorial_frame(draw, w, h, theme["border"], inset=int(h * 0.03), lw=max(2, h // 130), inner_gap=12, radius=sc["radius_md"])

    top_y = int(h * 0.12)
    if opts.get("show_icons", True):
        clock_shown = _draw_icon_disc_tracked(draw, w // 2, top_y + int(h * 0.05), int(h * 0.10), theme["mid_bg"], theme["border"], illu["clock_fn"], theme["top_text"], opts=opts, icon_name="clock", ring_width=max(2, h // 150))
        if clock_shown:
            top_y += int(h * 0.14)

    chip_w = int(_text_w(draw, texts["top_text"], lbl_f)) + 40
    draw_label_chip(draw, (w - chip_w) // 2, top_y, texts["top_text"], lbl_f, theme["top_text"], theme["mid_bg"], pad_x=20, pad_y=10, radius=sc["radius_sm"])
    _draw_text(draw, w // 2, int(h * 0.42), texts["main_text"], val_f, theme["top_text"], anchor="mm", opts=opts, box_name="main_text_box", box_pad=14)

    if opts.get("show_divider", True):
        _draw_editorial_divider_tracked(draw, int(w * 0.26), int(h * 0.58), int(w * 0.74), theme["divider"], sc["divider_thick"], style="split", opts=opts)

    card_x0 = int(w * 0.24)
    card_x1 = int(w * 0.76)
    card_y0 = int(h * 0.66)
    card_y1 = int(h * 0.88)
    draw_value_panel(draw, card_x0, card_y0, card_x1, card_y1, theme["mid_bg"], outline=theme["border"], radius=sc["radius_md"], outline_width=max(2, h // 150))
    _draw_text(draw, w // 2, card_y0 + int(h * 0.045), texts["bottom_text"], lbl_f, theme["bottom_text"], anchor="mt")
    _draw_text(draw, w // 2, card_y0 + int(h * 0.13), texts["time_text"], val_f, theme["bottom_text"], anchor="mt", opts=opts, box_name="time_text_box", box_pad=12)


# ── 18. SPLIT HERO ───────────────────────────────────────────────────────────

def render_split_hero(img, draw, w, h, texts, theme, lf, illu, opts):
    sc = layout_scale(w, h)
    pad = sc["pad_x"]
    lbl_f = lf("label")
    val_f = lf("value")
    _section_bg(img, draw, 0, 0, w, h, theme["bg"])

    hero_x0 = pad
    hero_y0 = int(h * 0.08)
    hero_x1 = int(w * 0.60)
    hero_y1 = int(h * 0.58)
    fill_lum = sum(theme["accent"]) / 3
    hero_tc = (255, 255, 255) if fill_lum < 128 else (10, 10, 10)
    draw_value_panel(draw, hero_x0, hero_y0, hero_x1, hero_y1, theme["accent"], radius=sc["radius_lg"])
    draw_label_chip(draw, hero_x0 + int(w * 0.03), hero_y0 + int(h * 0.03), texts["top_text"], lbl_f, theme["accent"], theme["bg"], pad_x=18, pad_y=10, radius=sc["radius_sm"])
    _draw_text(draw, hero_x0 + int(w * 0.03), hero_y0 + int(h * 0.18), texts["main_text"], val_f, hero_tc, opts=opts, box_name="main_text_box", box_pad=14)

    if opts.get("show_icons", True):
        _draw_icon_disc_tracked(draw, w - pad - int(h * 0.13), int(h * 0.28), int(h * 0.13), theme["mid_bg"], theme["border"], illu["clock_fn"], theme["top_text"], opts=opts, icon_name="clock", ring_width=max(2, h // 150))

    lower_y0 = int(h * 0.66)
    lower_y1 = int(h * 0.90)
    draw_value_panel(draw, pad, lower_y0, w - pad, lower_y1, theme["bottom_bg"], outline=theme["border"], radius=sc["radius_md"], outline_width=max(2, h // 150))
    door_shown = False
    if opts.get("show_icons", True):
        door_shown = _draw_icon_tile_tracked(draw, pad + int(h * 0.09), lower_y0 + int(h * 0.11), int(h * 0.15), theme["mid_bg"], theme["border"], illu["door_fn"], theme["bottom_text"], opts=opts, icon_name="door", outline_width=max(2, h // 150))
    if door_shown:
        tx = pad + int(h * 0.18)
    else:
        tx = pad + int(w * 0.03)
    _draw_text(draw, tx, lower_y0 + int(h * 0.04), texts["bottom_text"], lbl_f, theme["bottom_text"])
    _draw_text(draw, tx, lower_y0 + int(h * 0.14), texts["time_text"], val_f, theme["bottom_text"], opts=opts, box_name="time_text_box", box_pad=12)

    if opts.get("show_border", True):
        illu["border_fn"](draw, w, h, theme["border"])


# ── Registry ───────────────────────────────────────────────────────────────────

LAYOUTS = {
    "split":     render_split,
    "poster":    render_poster,
    "minimal":   render_minimal,
    "badge":     render_badge,
    "dashboard": render_dashboard,
    "blueprint": render_blueprint,
    "doodle":    render_doodle,
    "framed":    render_framed,
    "sticker":   render_sticker,
    "lateral":   render_lateral,
    "sketch_note":  render_sketch_note,
    "marker_board": render_marker_board,
    "doodle_card":  render_doodle_card,
    "hero_banner":  render_hero_banner,
    "editorial":    render_editorial,
    "modern_widget": render_modern_widget,
    "focus_mode":   render_focus_mode,
    "split_hero":   render_split_hero,
}

LAYOUT_NAMES = list(LAYOUTS.keys())
