"""
themes.py — Color palettes for Quadro Texto plugin.

Each theme defines:
  top_bg / bottom_bg      : background color for each section
  bg                      : single bg (used by single-bg layouts)
  top_text / bottom_text  : text color for each section
  accent                  : accent / highlight color
  divider                 : divider line color
  border                  : outer border color
  mid_bg                  : optional stripe / mid-section color
"""

THEMES = {
    # ── Neutrals ──────────────────────────────────────────────────────────────
    "black_white": {
        "top_bg":      (255, 255, 255),
        "bottom_bg":   (255, 255, 255),
        "bg":          (255, 255, 255),
        "top_text":    ( 12,  12,  12),
        "bottom_text": ( 12,  12,  12),
        "accent":      ( 12,  12,  12),
        "divider":     ( 30,  30,  30),
        "border":      ( 20,  20,  20),
        "mid_bg":      (220, 220, 220),
    },
    "ink_high_contrast": {
        "top_bg":      (  0,   0,   0),
        "bottom_bg":   (  0,   0,   0),
        "bg":          (  0,   0,   0),
        "top_text":    (255, 255, 255),
        "bottom_text": (255, 255, 255),
        "accent":      (255, 255, 255),
        "divider":     (200, 200, 200),
        "border":      (180, 180, 180),
        "mid_bg":      ( 40,  40,  40),
    },
    "grayscale": {
        "top_bg":      (245, 245, 245),
        "bottom_bg":   (210, 210, 210),
        "bg":          (240, 240, 240),
        "top_text":    ( 30,  30,  30),
        "bottom_text": ( 30,  30,  30),
        "accent":      ( 60,  60,  60),
        "divider":     ( 80,  80,  80),
        "border":      ( 50,  50,  50),
        "mid_bg":      (175, 175, 175),
    },
    # ── Cool ──────────────────────────────────────────────────────────────────
    "blue_green": {
        "top_bg":      (232, 240, 254),
        "bottom_bg":   (228, 244, 232),
        "bg":          (240, 248, 255),
        "top_text":    ( 24,  44, 108),
        "bottom_text": ( 18,  70,  24),
        "accent":      ( 24,  44, 108),
        "divider":     ( 24,  44, 108),
        "border":      ( 24,  44, 108),
        "mid_bg":      (180, 210, 230),
    },
    "ocean": {
        "top_bg":      (220, 238, 252),
        "bottom_bg":   (200, 230, 248),
        "bg":          (225, 240, 255),
        "top_text":    ( 10,  60, 120),
        "bottom_text": ( 10,  80, 140),
        "accent":      ( 10,  80, 180),
        "divider":     ( 30, 100, 180),
        "border":      ( 20,  70, 150),
        "mid_bg":      (160, 200, 240),
    },
    # ── Warm ──────────────────────────────────────────────────────────────────
    "purple_orange": {
        "top_bg":      (248, 243, 255),
        "bottom_bg":   (255, 248, 236),
        "bg":          (252, 248, 255),
        "top_text":    ( 58,  38, 108),
        "bottom_text": (192,  78,   0),
        "accent":      ( 58,  38, 108),
        "divider":     ( 58,  38, 108),
        "border":      ( 58,  38, 108),
        "mid_bg":      (200, 180, 230),
    },
    "warm_corporate": {
        "top_bg":      (255, 252, 245),
        "bottom_bg":   (252, 242, 228),
        "bg":          (255, 252, 248),
        "top_text":    ( 60,  40,  20),
        "bottom_text": (140,  60,   0),
        "accent":      (200,  80,  20),
        "divider":     (170,  70,  10),
        "border":      (130,  60,   0),
        "mid_bg":      (230, 200, 160),
    },
    "sunset": {
        "top_bg":      (255, 240, 225),
        "bottom_bg":   (255, 218, 185),
        "bg":          (255, 245, 235),
        "top_text":    (140,  40,   0),
        "bottom_text": (100,  20,   0),
        "accent":      (210,  70,  10),
        "divider":     (190,  60,  10),
        "border":      (160,  40,   0),
        "mid_bg":      (240, 185, 130),
    },
    # ── Fresh / Pastel ────────────────────────────────────────────────────────
    "pastel": {
        "top_bg":      (255, 244, 250),
        "bottom_bg":   (240, 248, 255),
        "bg":          (252, 248, 255),
        "top_text":    (100,  30,  80),
        "bottom_text": ( 30,  60, 120),
        "accent":      (180,  60, 130),
        "divider":     (200, 160, 190),
        "border":      (180, 140, 170),
        "mid_bg":      (235, 210, 240),
    },
    "forest": {
        "top_bg":      (238, 248, 236),
        "bottom_bg":   (218, 240, 215),
        "bg":          (235, 248, 232),
        "top_text":    ( 20,  70,  20),
        "bottom_text": ( 10,  55,  10),
        "accent":      ( 30,  90,  30),
        "divider":     ( 40, 100,  40),
        "border":      ( 25,  80,  25),
        "mid_bg":      (170, 215, 165),
    },
}

THEME_NAMES = list(THEMES.keys())
