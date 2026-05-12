"""
emoji_layout.py — Smart zone-based emoji positioning for Quadro Texto.

Each layout declares "free area zones" as normalized rects (x0, y0, x1, y1),
where values are fractions of (w, h).  The emoji is rendered centered at the
chosen zone's midpoint.  This avoids the "lost in the corner" problem by
routing the emoji into genuinely empty regions of each layout.

Zone schema:
    {
        "id":     str,                  # logical name (used by position mapping)
        "rect":   (x0, y0, x1, y1),    # fractions of w / h
        "weight": "subtle"|"balanced"|"featured",
    }

Zone weight guidelines:
  subtle   — small corner zone; prefers subtle / small emoji
  balanced — medium free area; standard decoration
  featured — large clear area; can carry a big emoji as a visual element
"""

from __future__ import annotations

import random

# ── Zone definitions ──────────────────────────────────────────────────────────
# Zones are derived from layout geometry analysis (icons / text positions).
# Each layout's icons and text tend to occupy the LEFT portion; right areas
# are usually free.  Exceptions (sketch_note, marker_board, doodle_card) have
# icons on the far-right, so their free zone is the mid-right area.

LAYOUT_ZONES: dict[str, list[dict]] = {
    # split: top half has long main text (~65-85% wide); bottom half has short
    # time text (~35-50% wide).  Prefer the wide open lower-right area.
    "split": [
        {"id": "bottom_free",  "rect": (0.60, 0.60, 0.95, 0.97), "weight": "featured"},
        {"id": "lower_right",  "rect": (0.68, 0.50, 0.95, 0.74), "weight": "balanced"},
    ],
    # poster: text centred.  Bottom corners free; top-right corner free.
    # Door icon sits at ~(91%, 89%) — avoid bottom-right corner.
    "poster": [
        {"id": "top_right",   "rect": (0.65, 0.03, 0.95, 0.23), "weight": "subtle"},
        {"id": "bottom_left", "rect": (0.03, 0.76, 0.38, 0.97), "weight": "balanced"},
        {"id": "top_left",    "rect": (0.03, 0.03, 0.35, 0.23), "weight": "subtle"},
    ],
    # minimal: pure centred text.  All four corner regions are free.
    "minimal": [
        {"id": "top_right",    "rect": (0.65, 0.03, 0.97, 0.24), "weight": "balanced"},
        {"id": "bottom_right", "rect": (0.65, 0.76, 0.97, 0.97), "weight": "balanced"},
        {"id": "top_left",     "rect": (0.03, 0.03, 0.35, 0.24), "weight": "subtle"},
        {"id": "bottom_left",  "rect": (0.03, 0.76, 0.35, 0.97), "weight": "balanced"},
    ],
    # badge: wide pill in top-60%.  Large free area to the right below the pill.
    "badge": [
        {"id": "lower_right", "rect": (0.60, 0.52, 0.96, 0.93), "weight": "featured"},
        {"id": "right_center", "rect": (0.66, 0.22, 0.96, 0.48), "weight": "balanced"},
    ],
    # dashboard: right panel has wide main text (can reach 85%).  Lower-right
    # region (right of short "19h" text) is reliably free.
    "dashboard": [
        {"id": "lower_right",  "rect": (0.66, 0.56, 0.97, 0.95), "weight": "featured"},
        {"id": "right_center", "rect": (0.72, 0.22, 0.97, 0.48), "weight": "balanced"},
    ],
    # blueprint: text-heavy left editorial area; emoji fits better in the lower-right field.
    "blueprint": [
        {"id": "lower_right", "rect": (0.64, 0.52, 0.93, 0.88), "weight": "featured"},
        {"id": "right_zone", "rect": (0.66, 0.34, 0.92, 0.60), "weight": "balanced"},
    ],
    # doodle: text + underline/arrow takes 0%-60% width.  Right zone is free but
    # the arrow/underline goes to ~75% at y≈47%.  Use upper-right above arrow OR
    # lower-right below the bottom text.
    "doodle": [
        {"id": "lower_right", "rect": (0.48, 0.62, 0.95, 0.93), "weight": "featured"},
        {"id": "upper_right", "rect": (0.65, 0.05, 0.95, 0.38), "weight": "balanced"},
    ],
    # framed: inner split layout.  Right half of each frame section is free.
    "framed": [
        {"id": "top_right",    "rect": (0.60, 0.07, 0.91, 0.47), "weight": "balanced"},
        {"id": "bottom_right", "rect": (0.60, 0.53, 0.91, 0.93), "weight": "balanced"},
    ],
    # sticker: top/bottom accent stripes (11.5% each).  Right of middle area is free.
    "sticker": [
        {"id": "lower_right",  "rect": (0.62, 0.54, 0.96, 0.92), "weight": "featured"},
        {"id": "right_center", "rect": (0.66, 0.24, 0.96, 0.50), "weight": "balanced"},
    ],
    # lateral: content fills 14%-85% of width.  Only far-right strip (85%+) and
    # lower-right region (past the short time text) are genuinely free.
    "lateral": [
        {"id": "lower_right", "rect": (0.72, 0.56, 0.97, 0.93), "weight": "featured"},
        {"id": "right_zone",  "rect": (0.76, 0.18, 0.97, 0.42), "weight": "balanced"},
    ],
    # sketch_note: icons on far-right (~82%) at top and mid.
    # Free zone: between text end (~52%) and icon column (~78%).
    "sketch_note": [
        {"id": "mid_right",  "rect": (0.52, 0.16, 0.78, 0.88), "weight": "featured"},
        {"id": "top_right",  "rect": (0.65, 0.05, 0.88, 0.24), "weight": "balanced"},
    ],
    # marker_board: icons also on far-right (~82-84%).
    # Free mid-right: text ends around 53%, icons at 82%.
    "marker_board": [
        {"id": "mid_right",   "rect": (0.56, 0.15, 0.80, 0.88), "weight": "featured"},
        {"id": "lower_right", "rect": (0.56, 0.55, 0.80, 0.88), "weight": "balanced"},
    ],
    # doodle_card: 2 stacked cards; icons at far-right (~85%) of each card.
    # Free right-of-text zone in each card (52-79%).
    "doodle_card": [
        {"id": "top_card_right",    "rect": (0.52, 0.07, 0.79, 0.44), "weight": "balanced"},
        {"id": "bottom_card_right", "rect": (0.52, 0.57, 0.79, 0.88), "weight": "balanced"},
        {"id": "top_right",         "rect": (0.65, 0.03, 0.95, 0.10), "weight": "subtle"},
    ],
    "hero_banner": [
        {"id": "lower_right", "rect": (0.60, 0.56, 0.95, 0.93), "weight": "featured"},
        {"id": "right_center", "rect": (0.72, 0.12, 0.95, 0.42), "weight": "balanced"},
    ],
    "editorial": [
        {"id": "right_zone", "rect": (0.70, 0.28, 0.95, 0.56), "weight": "balanced"},
        {"id": "bottom_left", "rect": (0.03, 0.72, 0.30, 0.95), "weight": "balanced"},
    ],
    "modern_widget": [
        {"id": "lower_right", "rect": (0.62, 0.56, 0.95, 0.92), "weight": "featured"},
        {"id": "right_zone", "rect": (0.70, 0.18, 0.95, 0.48), "weight": "balanced"},
    ],
    "focus_mode": [
        {"id": "top_right", "rect": (0.68, 0.06, 0.95, 0.24), "weight": "balanced"},
        {"id": "bottom_right", "rect": (0.68, 0.76, 0.95, 0.95), "weight": "balanced"},
        {"id": "top_left", "rect": (0.05, 0.06, 0.30, 0.24), "weight": "subtle"},
    ],
    "split_hero": [
        {"id": "right_zone", "rect": (0.66, 0.34, 0.95, 0.60), "weight": "balanced"},
        {"id": "top_right", "rect": (0.72, 0.08, 0.95, 0.26), "weight": "subtle"},
    ],
}

# Fallback zones when a layout is not in the registry
_DEFAULT_ZONES: list[dict] = [
    {"id": "top_right",    "rect": (0.65, 0.03, 0.97, 0.25), "weight": "subtle"},
    {"id": "bottom_right", "rect": (0.65, 0.75, 0.97, 0.97), "weight": "balanced"},
]

# Position setting → ordered list of preferred zone IDs to search
_POSITION_TO_ZONE_IDS: dict[str, list[str]] = {
    "top_right":    ["top_right",    "top_corner",  "upper_right",  "right_zone"],
    "bottom_right": ["bottom_right", "lower_right", "bottom_free",  "right_center"],
    "bottom_left":  ["bottom_left",  "panel_bottom"],
    "top_left":     ["top_left"],
    "near_clock":   ["top_right",    "top_corner",  "mid_right",    "top_card_right",  "upper_right"],
    "near_exit":    ["bottom_right", "lower_right", "bottom_free",  "panel_bottom",    "bottom_card_right"],
    "right_zone":   ["right_zone",   "lower_right", "bottom_free",  "right_center",    "mid_right"],
}

_WEIGHT_RANK: dict[str, int] = {"subtle": 0, "balanced": 1, "featured": 2}


# ── Public helpers ────────────────────────────────────────────────────────────

def get_layout_free_areas(layout_key: str, w: int, h: int) -> list[dict]:
    """Return zones for *layout_key* with pixel-coordinate ``px`` field added."""
    raw = LAYOUT_ZONES.get(layout_key, _DEFAULT_ZONES)
    result: list[dict] = []
    for zone in raw:
        x0f, y0f, x1f, y1f = zone["rect"]
        px = (int(x0f * w), int(y0f * h), int(x1f * w), int(y1f * h))
        result.append({
            "id":     zone["id"],
            "px":     px,
            "weight": zone["weight"],
            "area":   (px[2] - px[0]) * (px[3] - px[1]),
        })
    return result


def calculate_adaptive_emoji_size(layout_key: str, w: int, h: int,
                                   zone_id: str | None = None) -> int:
    """
    Return an emoji pixel size that fills roughly 45 % of the chosen zone's
    smallest dimension.  Clamped to [60, 30 % of shortest canvas side].
    """
    zones = get_layout_free_areas(layout_key, w, h)
    if zone_id:
        target = next((z for z in zones if z["id"] == zone_id), None)
    else:
        target = max(zones, key=lambda z: z["area"]) if zones else None

    if not target:
        return max(60, int(min(w, h) * 0.13))

    x0, y0, x1, y1 = target["px"]
    zone_w, zone_h = x1 - x0, y1 - y0
    raw = int(min(zone_w, zone_h) * 0.70)
    return max(80, min(raw, int(min(w, h) * 0.46)))


def choose_best_emoji_position(
    layout_key: str,
    requested_position: str,
    w: int,
    h: int,
    emoji_size_px: int,
    opts: dict | None = None,
) -> tuple[int, int, str]:
    """
    Return ``(center_x, center_y, zone_id)``.

    The emoji should be pasted so that its centre is at ``(center_x, center_y)``.
    """
    opts = opts or {}
    show_border = opts.get("show_border", True)
    bm = int(min(w, h) * 0.035) if show_border else int(min(w, h) * 0.018)

    zones = get_layout_free_areas(layout_key, w, h)
    if not zones:
        cx = w - bm - emoji_size_px // 2
        cy = bm + emoji_size_px // 2
        return cx, cy, "fallback"

    pos = str(requested_position or "random").strip().lower()

    if pos == "adaptive":
        chosen = max(zones, key=lambda z: z["area"])

    elif pos == "random":
        # Weighted random: featured zones get more probability
        weights = [_WEIGHT_RANK[z["weight"]] + 1 for z in zones]
        chosen = random.choices(zones, weights=weights, k=1)[0]

    else:
        candidate_ids = _POSITION_TO_ZONE_IDS.get(pos, [pos])
        chosen = None
        for cid in candidate_ids:
            chosen = next((z for z in zones if z["id"] == cid), None)
            if chosen:
                break
        if not chosen:
            if "right" in pos:
                chosen = next((z for z in zones if "right" in z["id"]), None)
            elif "left" in pos:
                chosen = next((z for z in zones if "left" in z["id"]), None)
            chosen = chosen or zones[0]

    x0, y0, x1, y1 = chosen["px"]
    cx = (x0 + x1) // 2
    cy = (y0 + y1) // 2

    # Clamp so the emoji doesn't overflow the canvas edge
    half = emoji_size_px // 2 + bm
    cx = max(half, min(w - half, cx))
    cy = max(half, min(h - half, cy))

    return cx, cy, chosen["id"]


def get_visual_balance_score(zone: dict, w: int, h: int) -> float:
    """Heuristic quality score for a zone (higher = better visual balance)."""
    x0, y0, x1, y1 = zone["px"]
    area_frac = zone["area"] / (w * h)
    cx_frac = (x0 + x1) / 2 / w
    cy_frac = (y0 + y1) / 2 / h
    # Prefer zones away from dead centre (where content usually is)
    off_centre = abs(cx_frac - 0.5) + abs(cy_frac - 0.5)
    return area_frac * 0.6 + off_centre * 0.4
