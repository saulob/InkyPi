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

_ICON_MIN_SIZE = 56
_PANEL_ICON_MIN_SIZE = 80
_PREMIUM_ICON_MIN_SIZE = 72

_SUPPRESS_LAYOUT_ICONS: dict[str, set[str]] = {
    "minimal": {"clock", "door"},
    "focus_mode": {"clock", "door"},
    "editorial": {"clock"},
    "poster": {"clock"},
}

_LAYOUT_ICON_MIN: dict[str, dict[str, int]] = {
    "dashboard": {"clock": _PANEL_ICON_MIN_SIZE, "door": _PANEL_ICON_MIN_SIZE},
    "lateral": {"clock": _PANEL_ICON_MIN_SIZE, "door": _PANEL_ICON_MIN_SIZE},
    "modern_widget": {"clock": _PANEL_ICON_MIN_SIZE, "door": 72},
    "framed": {"clock": 72, "door": 72},
    "split": {"clock": 72, "door": 72},
    "badge": {"clock": 72},
    "sticker": {"clock": 72},
    "hero_banner": {"clock": 72, "door": 72},
    "split_hero": {"clock": 72, "door": 72},
    "poster": {"door": 72},
    "blueprint": {"clock": _PREMIUM_ICON_MIN_SIZE},
}


def _normalise_box(box: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = [int(v) for v in box]
    return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)


def _flatten_occupied_boxes(occupied_boxes: dict | None) -> list[tuple[int, int, int, int]]:
    if not occupied_boxes:
        return []
    result: list[tuple[int, int, int, int]] = []
    for value in occupied_boxes.values():
        if not value:
            continue
        if isinstance(value, tuple) and len(value) == 4:
            result.append(_normalise_box(value))
            continue
        for box in value:
            if isinstance(box, tuple) and len(box) == 4:
                result.append(_normalise_box(box))
    return result


def add_occupied_box(
    occupied_boxes: dict | None,
    name: str,
    box: tuple[int, int, int, int] | None,
) -> dict | None:
    """Append *box* under *name* in the occupied-box registry."""
    if occupied_boxes is None or box is None:
        return occupied_boxes
    norm = _normalise_box(box)
    if norm[2] <= norm[0] or norm[3] <= norm[1]:
        return occupied_boxes
    occupied_boxes.setdefault(name, []).append(norm)
    return occupied_boxes


def boxes_overlap(
    box1: tuple[int, int, int, int],
    box2: tuple[int, int, int, int],
    padding: int = 0,
) -> bool:
    """Return True when two boxes intersect, expanded by *padding* pixels."""
    ax0, ay0, ax1, ay1 = _normalise_box(box1)
    bx0, by0, bx1, by1 = _normalise_box(box2)
    pad = max(0, int(padding))
    return not (
        ax1 + pad <= bx0 or
        bx1 + pad <= ax0 or
        ay1 + pad <= by0 or
        by1 + pad <= ay0
    )


def register_border_safe_area(
    occupied_boxes: dict | None,
    w: int,
    h: int,
    show_border: bool = True,
) -> None:
    """Reserve thin strips near the outer frame so emoji never hugs the border."""
    margin = int(min(w, h) * (0.040 if show_border else 0.022))
    if margin <= 0 or occupied_boxes is None:
        return
    add_occupied_box(occupied_boxes, "border_safe_area", (0, 0, w, margin))
    add_occupied_box(occupied_boxes, "border_safe_area", (0, h - margin, w, h))
    add_occupied_box(occupied_boxes, "border_safe_area", (0, 0, margin, h))
    add_occupied_box(occupied_boxes, "border_safe_area", (w - margin, 0, w, h))


def should_show_icon(layout_name: str, icon_name: str, available_size: int) -> bool:
    """Return True when the icon has enough space and adds value in this layout."""
    layout = str(layout_name or "").strip().lower()
    icon = str(icon_name or "").strip().lower()
    if available_size < _ICON_MIN_SIZE:
        return False
    if icon in _SUPPRESS_LAYOUT_ICONS.get(layout, set()):
        return False
    min_size = _LAYOUT_ICON_MIN.get(layout, {}).get(icon, _ICON_MIN_SIZE)
    return available_size >= min_size


def _ordered_zones(layout_key: str, requested_position: str, w: int, h: int) -> list[dict]:
    zones = get_layout_free_areas(layout_key, w, h)
    if not zones:
        return []

    pos = str(requested_position or "random").strip().lower()

    if pos == "adaptive":
        return sorted(zones, key=lambda z: z["area"], reverse=True)

    if pos == "random":
        shuffled = list(zones)
        random.shuffle(shuffled)
        return sorted(
            shuffled,
            key=lambda z: (_WEIGHT_RANK.get(z["weight"], 0), z["area"]),
            reverse=True,
        )

    candidate_ids = _POSITION_TO_ZONE_IDS.get(pos, [pos])
    matched: list[dict] = []
    seen_ids: set[str] = set()
    for cid in candidate_ids:
        for zone in zones:
            if zone["id"] == cid and zone["id"] not in seen_ids:
                matched.append(zone)
                seen_ids.add(zone["id"])
    if "right" in pos:
        for zone in zones:
            if "right" in zone["id"] and zone["id"] not in seen_ids:
                matched.append(zone)
                seen_ids.add(zone["id"])
    elif "left" in pos:
        for zone in zones:
            if "left" in zone["id"] and zone["id"] not in seen_ids:
                matched.append(zone)
                seen_ids.add(zone["id"])

    for zone in zones:
        if zone["id"] not in seen_ids:
            matched.append(zone)
    return matched


def _zone_anchor_candidates(
    zone: dict,
    emoji_size_px: int,
) -> list[tuple[int, int]]:
    x0, y0, x1, y1 = zone["px"]
    half = emoji_size_px // 2
    inset = max(8, int(emoji_size_px * 0.10))
    left = x0 + half + inset
    right = x1 - half - inset
    top = y0 + half + inset
    bottom = y1 - half - inset
    if left > right or top > bottom:
        return []

    mid_x = (left + right) // 2
    mid_y = (top + bottom) // 2
    third_x = (left * 2 + right) // 3
    third_y = (top * 2 + bottom) // 3
    two_third_x = (left + right * 2) // 3
    two_third_y = (top + bottom * 2) // 3
    candidates = [
        (mid_x, mid_y),
        (left, top),
        (right, top),
        (left, bottom),
        (right, bottom),
        (mid_x, top),
        (mid_x, bottom),
        (third_x, mid_y),
        (two_third_x, mid_y),
        (mid_x, third_y),
        (mid_x, two_third_y),
    ]
    result: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for item in candidates:
        if item not in seen:
            result.append(item)
            seen.add(item)
    return result


def find_free_emoji_anchor(
    layout_name: str,
    occupied_boxes: dict | None,
    w: int,
    h: int,
    emoji_size_px: int,
    requested_position: str = "random",
    padding: int = 12,
) -> tuple[int, int, str] | None:
    """Find the best non-overlapping emoji anchor inside this layout's free zones."""
    occupied = _flatten_occupied_boxes(occupied_boxes)
    half = emoji_size_px // 2

    for zone in _ordered_zones(layout_name, requested_position, w, h):
        for cx, cy in _zone_anchor_candidates(zone, emoji_size_px):
            emoji_box = (cx - half, cy - half, cx + half, cy + half)
            if emoji_box[0] < 0 or emoji_box[1] < 0 or emoji_box[2] > w or emoji_box[3] > h:
                continue
            if any(boxes_overlap(emoji_box, other, padding=padding) for other in occupied):
                continue
            return cx, cy, zone["id"]
    return None


def place_emoji_safely(
    layout_name: str,
    occupied_boxes: dict | None,
    w: int,
    h: int,
    preferred_size_px: int,
    requested_position: str = "random",
    min_size_px: int = 44,
) -> tuple[int, int, str, int] | None:
    """Try progressively smaller emoji sizes until one fits or return None."""
    tried: list[int] = []
    for factor in (1.00, 0.88, 0.76, 0.64):
        size_px = max(min_size_px, int(preferred_size_px * factor))
        if size_px in tried:
            continue
        tried.append(size_px)
        placed = find_free_emoji_anchor(
            layout_name,
            occupied_boxes,
            w,
            h,
            size_px,
            requested_position=requested_position,
            padding=max(10, int(size_px * 0.10)),
        )
        if placed is not None:
            cx, cy, zone_id = placed
            return cx, cy, zone_id, size_px
    return None


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
