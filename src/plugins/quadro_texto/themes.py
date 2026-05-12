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
        "accent":      (155,  55,   5),
        "divider":     (155,  55,   5),
        "border":      (130,  60,   0),
        "mid_bg":      (230, 200, 160),
    },
    "sunset": {
        "top_bg":      (255, 240, 225),
        "bottom_bg":   (255, 218, 185),
        "bg":          (255, 245, 235),
        "top_text":    (140,  40,   0),
        "bottom_text": (100,  20,   0),
        "accent":      (160,  50,   5),
        "divider":     (155,  45,   5),
        "border":      (140,  35,   0),
        "mid_bg":      (235, 175, 115),
    },
    # ── Fresh / Pastel ────────────────────────────────────────────────────────
    "pastel": {
        "top_bg":      (255, 244, 250),
        "bottom_bg":   (240, 248, 255),
        "bg":          (252, 248, 255),
        "top_text":    (100,  30,  80),
        "bottom_text": ( 30,  60, 120),
        "accent":      (150,  30, 110),
        "divider":     (100,  50,  90),
        "border":      (110,  55, 100),
        "mid_bg":      (220, 190, 230),
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
    # ── E-paper safe ──────────────────────────────────────────────────────────
    # These themes guarantee strong contrast and are designed specifically for
    # e-paper displays.  All text/bg pairs exceed WCAG AAA (7:1) contrast.
    "eink_safe": {
        # Warm off-white background — closest to real e-paper paper white
        "top_bg":      (248, 246, 240),
        "bottom_bg":   (236, 233, 226),
        "bg":          (245, 243, 237),
        "top_text":    ( 15,  15,  15),
        "bottom_text": ( 15,  15,  15),
        "accent":      ( 25,  35, 120),
        "divider":     ( 55,  55,  55),
        "border":      ( 40,  40,  40),
        "mid_bg":      (210, 206, 196),
    },
    "eink_high_contrast": {
        # Pure white background + pure black text: maximum possible contrast
        "top_bg":      (255, 255, 255),
        "bottom_bg":   (255, 255, 255),
        "bg":          (255, 255, 255),
        "top_text":    (  0,   0,   0),
        "bottom_text": (  0,   0,   0),
        "accent":      (  0,   0,   0),
        "divider":     (  0,   0,   0),
        "border":      (  0,   0,   0),
        "mid_bg":      (195, 195, 195),
    },
    "eink_soft": {
        # Warm light-gray background with dark warm accents
        "top_bg":      (238, 235, 228),
        "bottom_bg":   (226, 223, 215),
        "bg":          (235, 232, 225),
        "top_text":    ( 28,  22,  14),
        "bottom_text": ( 28,  22,  14),
        "accent":      ( 75,  55,  15),
        "divider":     ( 65,  60,  50),
        "border":      ( 50,  45,  35),
        "mid_bg":      (198, 193, 182),
    },
    "eink_clean": {
        # Clean white with deep blue-gray text and accents
        "top_bg":      (255, 255, 255),
        "bottom_bg":   (244, 247, 252),
        "bg":          (255, 255, 255),
        "top_text":    ( 18,  28,  52),
        "bottom_text": ( 18,  28,  52),
        "accent":      ( 18,  28,  52),
        "divider":     ( 38,  55,  85),
        "border":      ( 30,  48,  78),
        "mid_bg":      (210, 218, 235),
    },
}

THEME_NAMES = list(THEMES.keys())
