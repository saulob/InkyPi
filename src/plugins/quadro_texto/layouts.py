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


# ── Internal helpers ───────────────────────────────────────────────────────────

def _text_w(draw, text, font):
    try:
        return draw.textlength(text, font=font)
    except AttributeError:
        return draw.textsize(text, font=font)[0]


def _draw_text(draw, x, y, text, font, color, anchor="lt"):
    draw.text((x, y), text, font=font, fill=color, anchor=anchor)


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


# ── 1. SPLIT ──────────────────────────────────────────────────────────────────

def render_split(img, draw, w, h, texts, theme, lf, illu, opts):
    pad     = int(w * 0.045)
    icon_r  = int(h * 0.115)
    gap     = int(h * 0.022)
    lbl_f   = lf("label")
    val_f   = lf("value")

    div_y  = h // 2
    div_th = max(2, h // 120)

    _section_bg(img, draw, 0, 0, w, div_y, theme["top_bg"])
    _section_bg(img, draw, 0, div_y, w, h,  theme["bottom_bg"])

    if opts.get("show_divider", True):
        draw.rectangle([0, div_y - div_th, w, div_y + div_th], fill=theme["divider"])

    icon_cx = pad + icon_r
    text_x  = (icon_cx + icon_r + pad) if opts.get("show_icons", True) else pad

    lbl_h = int(h * 0.072)
    val_h = int(h * 0.200)
    total_h = lbl_h + gap + val_h

    # Top section
    top_cy = div_y // 2
    if opts.get("show_icons", True):
        illu["clock_fn"](draw, icon_cx, top_cy, icon_r, theme["top_text"])
    ty = top_cy - total_h // 2
    _draw_text(draw, text_x, ty, texts["top_text"], lbl_f, theme["top_text"])
    _draw_text(draw, text_x, ty + lbl_h + gap, texts["main_text"], val_f, theme["top_text"])

    # Bottom section
    bot_cy = div_y + (h - div_y) // 2
    if opts.get("show_icons", True):
        illu["door_fn"](draw, icon_cx, bot_cy, icon_r, theme["bottom_text"])
    ty2 = bot_cy - total_h // 2
    _draw_text(draw, text_x, ty2, texts["bottom_text"], lbl_f, theme["bottom_text"])
    _draw_text(draw, text_x, ty2 + lbl_h + gap, texts["time_text"], val_f, theme["bottom_text"])

    if opts.get("show_border", True):
        illu["border_fn"](draw, w, h, theme["border"])


# ── 2. POSTER ─────────────────────────────────────────────────────────────────

def render_poster(img, draw, w, h, texts, theme, lf, illu, opts):
    _section_bg(img, draw, 0, 0, w, h, theme["bg"])
    icon_r = int(h * 0.09)
    lbl_f  = lf("label")
    val_f  = lf("value")
    val_f2 = lf("sub")
    gap    = int(h * 0.025)

    y = int(h * 0.06)
    if opts.get("show_icons", True):
        illu["clock_fn"](draw, w // 2, y + icon_r, icon_r, theme["top_text"])
        y += icon_r * 2 + gap

    _draw_text(draw, w // 2, y, texts["top_text"], lbl_f, theme["top_text"], anchor="mt")
    y += int(h * 0.072) + gap
    _draw_text(draw, w // 2, y, texts["main_text"], val_f, theme["top_text"], anchor="mt")
    y += int(h * 0.200) + gap * 2

    if opts.get("show_divider", True):
        dw = int(w * 0.45)
        _divider(draw, (w - dw) // 2, y, (w + dw) // 2, theme["divider"], h)
        y += int(h * 0.030)

    _draw_text(draw, w // 2, y, texts["bottom_text"], lbl_f, theme["bottom_text"], anchor="mt")
    y += int(h * 0.072) + gap
    _draw_text(draw, w // 2, y, texts["time_text"], val_f, theme["bottom_text"], anchor="mt")

    if opts.get("show_icons", True):
        dr = int(icon_r * 0.65)
        illu["door_fn"](draw, w - int(w * 0.09), h - int(h * 0.11), dr, theme["bottom_text"])

    if opts.get("show_border", True):
        illu["border_fn"](draw, w, h, theme["border"])


# ── 3. MINIMAL ────────────────────────────────────────────────────────────────

def render_minimal(img, draw, w, h, texts, theme, lf, illu, opts):
    _section_bg(img, draw, 0, 0, w, h, theme["bg"])
    lbl_f  = lf("label")
    val_f  = lf("value")
    val_f2 = lf("sub")
    gap    = int(h * 0.025)
    gap2   = int(h * 0.048)
    lbl_h  = int(h * 0.088)
    val_h  = int(h * 0.225)
    val_sm = int(h * 0.130)
    dh     = max(2, h // 120)

    total_h = lbl_h + gap + val_h + gap2 + dh + gap2 + lbl_h + gap + val_sm
    y = (h - total_h) // 2

    _draw_text(draw, w // 2, y, texts["top_text"], lbl_f, theme["top_text"], "mt")
    y += lbl_h + gap
    _draw_text(draw, w // 2, y, texts["main_text"], val_f, theme["top_text"], "mt")
    y += val_h + gap2

    if opts.get("show_divider", True):
        dw = int(w * 0.32)
        _divider(draw, (w - dw) // 2, y, (w + dw) // 2, theme["divider"], h)
    y += dh + gap2

    _draw_text(draw, w // 2, y, texts["bottom_text"], lbl_f, theme["bottom_text"], "mt")
    y += lbl_h + gap
    _draw_text(draw, w // 2, y, texts["time_text"], val_f2, theme["bottom_text"], "mt")

    if opts.get("show_border", True):
        illu["border_fn"](draw, w, h, theme["border"])


# ── 4. BADGE ──────────────────────────────────────────────────────────────────

def render_badge(img, draw, w, h, texts, theme, lf, illu, opts):
    _section_bg(img, draw, 0, 0, w, h, theme["bg"])
    lbl_f  = lf("label")
    val_f  = lf("value")
    sub_f  = lf("sub")
    gap    = int(h * 0.028)
    pad    = int(w * 0.06)

    # Top area: label + large pill with main_text
    y = int(h * 0.09)
    if opts.get("show_icons", True):
        icon_r = int(h * 0.07)
        illu["clock_fn"](draw, pad + icon_r, y + icon_r, icon_r, theme["top_text"])
        tx = pad + icon_r * 2 + int(pad * 0.6)
    else:
        tx = pad
    _draw_text(draw, tx, y, texts["top_text"], lbl_f, theme["top_text"])

    # Badge pill for main_text
    bh = int(h * 0.190)
    by = y + int(h * 0.085)
    bx0 = pad
    bx1 = w - pad
    try:
        draw.rounded_rectangle([bx0, by, bx1, by + bh], radius=bh // 2,
                                fill=theme["accent"])
    except AttributeError:
        draw.rectangle([bx0, by, bx1, by + bh], fill=theme["accent"])
    # text on badge
    bg_lum = sum(theme["accent"]) / 3
    badge_tc = (255, 255, 255) if bg_lum < 128 else (10, 10, 10)
    _draw_text(draw, w // 2, by + bh // 2, texts["main_text"], val_f, badge_tc, "mm")

    # Bottom: divider + bottom_text + time pill
    y2 = by + bh + int(h * 0.065)
    if opts.get("show_divider", True):
        dw = int(w * 0.55)
        _divider(draw, (w - dw) // 2, y2, (w + dw) // 2, theme["divider"], h)
        y2 += int(h * 0.030)

    if opts.get("show_icons", True):
        icon_r2 = int(h * 0.065)
        illu["door_fn"](draw, pad + icon_r2, y2 + icon_r2, icon_r2, theme["bottom_text"])
        bx2 = pad + icon_r2 * 2 + int(pad * 0.5)
    else:
        bx2 = pad
    _draw_text(draw, bx2, y2, texts["bottom_text"], sub_f, theme["bottom_text"])
    y2 += int(h * 0.065)
    _draw_text(draw, bx2, y2, texts["time_text"], val_f, theme["bottom_text"])

    if opts.get("show_border", True):
        illu["border_fn"](draw, w, h, theme["border"])


# ── 5. DASHBOARD ──────────────────────────────────────────────────────────────

def render_dashboard(img, draw, w, h, texts, theme, lf, illu, opts):
    panel_w = int(w * 0.30)
    _section_bg(img, draw, 0, 0, panel_w, h, theme["mid_bg"])
    _section_bg(img, draw, panel_w, 0, w, h, theme["bg"])

    lbl_f  = lf("label")
    val_f  = lf("value")
    sub_f  = lf("sub")
    icon_r = int(h * 0.12)
    pad    = int(h * 0.04)
    gap    = int(h * 0.028)

    # Left panel: stacked icons
    cy1 = h // 3
    cy2 = h * 2 // 3
    if opts.get("show_icons", True):
        illu["clock_fn"](draw, panel_w // 2, cy1, icon_r, theme["top_text"])
        illu["door_fn"](draw, panel_w // 2, cy2, int(icon_r * 0.85), theme["bottom_text"])

    # Right panel: text blocks
    tx = panel_w + int(w * 0.05)
    lbl_h = int(h * 0.080)
    val_h = int(h * 0.200)
    total = lbl_h + gap + val_h + int(h * 0.06) + lbl_h + gap + int(h * 0.150)
    ty = (h - total) // 2

    _draw_text(draw, tx, ty, texts["top_text"], lbl_f, theme["top_text"])
    ty += lbl_h + gap
    _draw_text(draw, tx, ty, texts["main_text"], val_f, theme["top_text"])
    ty += val_h + int(h * 0.06)

    if opts.get("show_divider", True):
        _divider(draw, tx, ty, w - int(w * 0.05), theme["divider"], h, "dashed")
        ty += int(h * 0.030)

    _draw_text(draw, tx, ty, texts["bottom_text"], lbl_f, theme["bottom_text"])
    ty += lbl_h + gap
    _draw_text(draw, tx, ty, texts["time_text"], val_f, theme["bottom_text"])

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

    lbl_f  = lf("label")
    val_f  = lf("value")
    sub_f  = lf("sub")
    gap    = int(h * 0.030)
    pad    = int(w * 0.06)
    lbl_h  = int(h * 0.072)
    val_h  = int(h * 0.200)

    total_h = (lbl_h + gap + val_h) * 2 + int(h * 0.08)
    y = (h - total_h) // 2

    # Corner brackets decoration
    bpad = int(h * 0.04)
    bsize = int(h * 0.08)
    draw_all_corner_brackets(draw, bpad, bpad, w - bpad, h - bpad, bsize, theme["border"], lw=2)

    _draw_text(draw, pad, y, texts["top_text"], lbl_f, theme["top_text"])
    y += lbl_h + gap
    _draw_text(draw, pad, y, texts["main_text"], val_f, theme["top_text"])
    y += val_h + int(h * 0.05)

    dw = int(w * 0.50)
    _divider(draw, pad, y, pad + dw, theme["divider"], h, "dashed")
    y += int(h * 0.03)

    _draw_text(draw, pad, y, texts["bottom_text"], lbl_f, theme["bottom_text"])
    y += lbl_h + gap
    _draw_text(draw, pad, y, texts["time_text"], val_f, theme["bottom_text"])

    # Blueprint label tag bottom-right
    tag_text = "WORK REMINDER"
    sub_f2 = lf("sub")
    tag_w = int(_text_w(draw, tag_text, sub_f2))
    tag_x = w - pad - tag_w
    tag_y = h - int(h * 0.07)
    _draw_text(draw, tag_x, tag_y, tag_text, sub_f2, theme["accent"])


# ── 7. DOODLE ─────────────────────────────────────────────────────────────────

def render_doodle(img, draw, w, h, texts, theme, lf, illu, opts):
    _section_bg(img, draw, 0, 0, w, h, theme["bg"])
    lbl_f  = lf("label")
    val_f  = lf("value")
    sub_f  = lf("sub")
    gap    = int(h * 0.025)
    pad    = int(w * 0.06)

    # Doodle background circles
    doodle_col = tuple(max(0, c - 20) if theme["bg"][0] > 128 else min(255, c + 20)
                       for c in theme["bg"])
    draw_doodle_circle(draw, int(w * 0.82), int(h * 0.15), int(h * 0.18), doodle_col, lw=3)
    draw_doodle_circle(draw, int(w * 0.12), int(h * 0.78), int(h * 0.12), doodle_col, lw=2)

    # Underline accent behind main_text
    lbl_h = int(h * 0.082)
    val_h = int(h * 0.215)
    y = int(h * 0.10)

    if opts.get("show_icons", True):
        icon_r = int(h * 0.09)
        from illustrations import draw_clock_doodle
        draw_clock_doodle(draw, pad + icon_r, y + icon_r, icon_r, theme["top_text"])
        tx = pad + icon_r * 2 + int(pad * 0.5)
    else:
        tx = pad

    _draw_text(draw, tx, y, texts["top_text"], lbl_f, theme["top_text"])
    y += lbl_h + gap

    tw = int(_text_w(draw, texts["main_text"], val_f))
    _draw_text(draw, tx, y, texts["main_text"], val_f, theme["top_text"])
    ul_y = y + val_h + int(gap * 0.4)
    draw_underline(draw, tx, ul_y, min(tw + 10, w - tx - pad),
                   max(3, h // 80), theme["accent"])
    y = ul_y + int(h * 0.06)

    if opts.get("show_divider", True):
        dw = int(w * 0.35)
        _divider(draw, tx, y, tx + dw, theme["divider"], h, "dashed")
        y += int(h * 0.035)

    if opts.get("show_icons", True):
        icon_r2 = int(h * 0.08)
        from illustrations import draw_door_doodle
        draw_door_doodle(draw, pad + icon_r2, y + icon_r2, icon_r2, theme["bottom_text"])
        bx = pad + icon_r2 * 2 + int(pad * 0.5)
    else:
        bx = pad
    _draw_text(draw, bx, y, texts["bottom_text"], lbl_f, theme["bottom_text"])
    y += lbl_h + gap
    _draw_text(draw, bx, y, texts["time_text"], val_f, theme["bottom_text"])


# ── 8. FRAMED ─────────────────────────────────────────────────────────────────

def render_framed(img, draw, w, h, texts, theme, lf, illu, opts):
    _section_bg(img, draw, 0, 0, w, h, theme["mid_bg"])

    # Inner mat
    mat = int(min(w, h) * 0.055)
    inner_x0, inner_y0 = mat, mat
    inner_x1, inner_y1 = w - mat, h - mat
    _section_bg(img, draw, inner_x0, inner_y0, inner_x1, inner_y1, theme["bg"])
    # Mat border
    lw = max(2, mat // 5)
    draw.rectangle([inner_x0, inner_y0, inner_x1, inner_y1], outline=theme["border"], width=lw)

    iw = inner_x1 - inner_x0
    ih = inner_y1 - inner_y0
    pad = int(iw * 0.06)
    icon_r = int(ih * 0.11)
    gap = int(ih * 0.025)
    lbl_h = int(ih * 0.082)
    val_h = int(ih * 0.200)

    div_y = inner_y0 + ih // 2
    if opts.get("show_divider", True):
        dw2 = int(iw * 0.88)
        _divider(draw, inner_x0 + (iw - dw2) // 2, div_y,
                 inner_x0 + (iw + dw2) // 2, theme["divider"], ih)

    icon_cx = inner_x0 + pad + icon_r
    tx = icon_cx + icon_r + pad

    # Top
    top_cy = inner_y0 + ih // 4
    if opts.get("show_icons", True):
        illu["clock_fn"](draw, icon_cx, top_cy, icon_r, theme["top_text"])
    ty = top_cy - (lbl_h + gap + val_h) // 2
    _draw_text(draw, tx, ty, texts["top_text"], lf("label"), theme["top_text"])
    _draw_text(draw, tx, ty + lbl_h + gap, texts["main_text"], lf("value"), theme["top_text"])

    # Bottom
    bot_cy = inner_y0 + ih * 3 // 4
    if opts.get("show_icons", True):
        illu["door_fn"](draw, icon_cx, bot_cy, icon_r, theme["bottom_text"])
    ty2 = bot_cy - (lbl_h + gap + val_h) // 2
    _draw_text(draw, tx, ty2, texts["bottom_text"], lf("label"), theme["bottom_text"])
    _draw_text(draw, tx, ty2 + lbl_h + gap, texts["time_text"], lf("value"), theme["bottom_text"])

    # Outer border
    if opts.get("show_border", True):
        draw.rectangle([0, 0, w - 1, h - 1], outline=theme["border"],
                       width=max(3, mat // 4))


# ── 9. STICKER ────────────────────────────────────────────────────────────────

def render_sticker(img, draw, w, h, texts, theme, lf, illu, opts):
    _section_bg(img, draw, 0, 0, w, h, theme["bg"])

    stripe_h = int(h * 0.115)
    _section_bg(img, draw, 0, 0, w, stripe_h, theme["accent"])
    _section_bg(img, draw, 0, h - stripe_h, w, h, theme["accent"])

    lbl_f = lf("label")
    val_f = lf("value")
    sub_f = lf("sub")
    pad   = int(w * 0.055)
    gap   = int(h * 0.022)

    lbl_h = int(h * 0.082)
    val_h = int(h * 0.200)
    tot1  = lbl_h + gap + val_h
    tot2  = lbl_h + gap + int(h * 0.150)
    inner = h - stripe_h * 2
    y = stripe_h + (inner - tot1 - int(h * 0.07) - tot2) // 2

    if opts.get("show_icons", True):
        icon_r = int(h * 0.08)
        illu["clock_fn"](draw, pad + icon_r, y + icon_r, icon_r, theme["top_text"])
        tx = pad + icon_r * 2 + int(pad * 0.4)
    else:
        tx = pad

    _draw_text(draw, tx, y, texts["top_text"], lbl_f, theme["top_text"])
    _draw_text(draw, tx, y + lbl_h + gap, texts["main_text"], val_f, theme["top_text"])
    y += tot1 + int(h * 0.04)

    if opts.get("show_divider", True):
        dw = int(w * 0.45)
        _divider(draw, pad, y, pad + dw, theme["divider"], h)
        y += int(h * 0.030)

    if opts.get("show_icons", True):
        icon_r2 = int(h * 0.07)
        illu["door_fn"](draw, pad + icon_r2, y + icon_r2, icon_r2, theme["bottom_text"])
        bx = pad + icon_r2 * 2 + int(pad * 0.4)
    else:
        bx = pad
    _draw_text(draw, bx, y, texts["bottom_text"], sub_f, theme["bottom_text"])
    _draw_text(draw, bx, y + lbl_h + gap, texts["time_text"], val_f, theme["bottom_text"])

    if opts.get("show_border", True):
        illu["border_fn"](draw, w, h, theme["border"])


# ── 10. LATERAL ───────────────────────────────────────────────────────────────

def render_lateral(img, draw, w, h, texts, theme, lf, illu, opts):
    stripe_w = int(w * 0.14)
    _section_bg(img, draw, 0, 0, stripe_w, h, theme["accent"])
    _section_bg(img, draw, stripe_w, 0, w, h, theme["bg"])

    lbl_f = lf("label")
    val_f = lf("value")
    sub_f = lf("sub")
    pad   = int(w * 0.045)
    gap   = int(h * 0.025)

    # Rotated text in stripe — we simulate with dots
    dot_r = max(3, int(stripe_w * 0.10))
    for dy in range(int(h * 0.12), h - int(h * 0.12), int(h * 0.09)):
        draw.ellipse([stripe_w // 2 - dot_r, dy - dot_r,
                      stripe_w // 2 + dot_r, dy + dot_r], fill=theme["bg"])

    tx = stripe_w + pad
    lbl_h = int(h * 0.082)
    val_h = int(h * 0.200)
    total_h = lbl_h + gap + val_h + int(h * 0.07) + lbl_h + gap + int(h * 0.150)
    y = (h - total_h) // 2

    icon_r = int(h * 0.100)
    if opts.get("show_icons", True):
        illu["clock_fn"](draw, tx + icon_r, y + icon_r, icon_r, theme["top_text"])
        ftx = tx + icon_r * 2 + gap
    else:
        ftx = tx

    _draw_text(draw, ftx, y, texts["top_text"], lbl_f, theme["top_text"])
    _draw_text(draw, ftx, y + lbl_h + gap, texts["main_text"], val_f, theme["top_text"])
    y += val_h + lbl_h + int(h * 0.05)

    if opts.get("show_divider", True):
        _divider(draw, tx, y, w - pad, theme["divider"], h)
        y += int(h * 0.035)

    if opts.get("show_icons", True):
        icon_r2 = int(h * 0.085)
        illu["door_fn"](draw, tx + icon_r2, y + icon_r2, icon_r2, theme["bottom_text"])
        fbx = tx + icon_r2 * 2 + gap
    else:
        fbx = tx

    _draw_text(draw, fbx, y, texts["bottom_text"], lbl_f, theme["bottom_text"])
    _draw_text(draw, fbx, y + lbl_h + gap, texts["time_text"], val_f, theme["bottom_text"])

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
}

LAYOUT_NAMES = list(LAYOUTS.keys())
