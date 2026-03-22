import logging
import math
import random

from PIL import Image, ImageColor, ImageDraw

from plugins.base_plugin.base_plugin import BasePlugin
from utils.app_utils import get_font

logger = logging.getLogger(__name__)

SYLLABLES = [
    "zo", "ki", "mu", "bo", "lu", "ga", "ri", "po", "ne", "da",
    "fi", "to", "bi", "go", "nu", "ka", "mi", "ro", "le", "su",
    "ba", "di", "fu", "ko", "na", "pi", "ta", "wo", "ze", "hu",
    "blo", "gri", "dro", "fli", "snu", "kra", "plu", "tri", "glo", "spi",
    "bru", "cho", "qui", "shi", "whi", "thu", "ska", "twi", "fra", "slo",
]

ARCHETYPE_ORDER = [
    "zombie", "werewolf", "octopus", "dragon",
    "spider", "dinosaur", "cthulhu", "ghost", "default",
]


def generate_monster_name():
    """Generate a short playful monster name (1-3 syllables)."""
    count = random.choices([1, 2, 3], weights=[25, 50, 25])[0]
    parts = random.sample(SYLLABLES, count)
    return "".join(parts).capitalize()


# ---------------------------------------------------------------------------
# Low-level geometry utilities (kept for anchoring, tests, and reuse)
# ---------------------------------------------------------------------------

def _smooth_blob_points(cx, cy, rx, ry, num_points=48, low=0.90, high=1.10):
    raw = [random.uniform(low, high) for _ in range(num_points)]
    smoothed = [
        (raw[(index - 1) % num_points] + raw[index] + raw[(index + 1) % num_points]) / 3
        for index in range(num_points)
    ]
    points = []
    for index in range(num_points):
        angle = (2 * math.pi * index) / num_points
        points.append(
            (
                cx + rx * smoothed[index] * math.cos(angle),
                cy + ry * smoothed[index] * math.sin(angle),
            )
        )
    return points


def _ellipse_points(cx, cy, rx, ry, num_points=72):
    return [
        (
            cx + rx * math.cos((2 * math.pi * index) / num_points),
            cy + ry * math.sin((2 * math.pi * index) / num_points),
        )
        for index in range(num_points)
    ]


def _rounded_rect_points(cx, cy, half_w, half_h, radius, arc_points=10):
    radius = max(0, min(radius, half_w, half_h))
    if radius == 0:
        return [
            (cx - half_w, cy - half_h),
            (cx + half_w, cy - half_h),
            (cx + half_w, cy + half_h),
            (cx - half_w, cy + half_h),
        ]

    centers = [
        (cx + half_w - radius, cy - half_h + radius, -math.pi / 2, 0),
        (cx + half_w - radius, cy + half_h - radius, 0, math.pi / 2),
        (cx - half_w + radius, cy + half_h - radius, math.pi / 2, math.pi),
        (cx - half_w + radius, cy - half_h + radius, math.pi, 3 * math.pi / 2),
    ]
    points = []
    for arc_cx, arc_cy, start_angle, end_angle in centers:
        for step in range(arc_points + 1):
            angle = start_angle + ((end_angle - start_angle) * step / arc_points)
            points.append((arc_cx + radius * math.cos(angle), arc_cy + radius * math.sin(angle)))
    return points


def _ghost_outline_points(cx, cy, body_w, body_h):
    half_w = body_w / 2
    half_h = body_h / 2
    left_x = cx - half_w
    right_x = cx + half_w
    top_y = cy - half_h
    bottom_y = cy + half_h
    top_h = body_h * 0.72
    side_bottom_y = top_y + top_h * 0.82
    cap_center_y = top_y + top_h * 0.46
    cap_radius_y = max(top_h * 0.46, 1)

    points = [(left_x, side_bottom_y)]
    for step in range(24):
        angle = math.pi - (math.pi * step / 23)
        points.append((cx + half_w * math.cos(angle), cap_center_y - cap_radius_y * math.sin(angle)))
    points.append((right_x, side_bottom_y))

    wave_count = 4
    step = body_w / wave_count
    for index in range(wave_count, -1, -1):
        wave_x = left_x + index * step
        wave_y = bottom_y - (body_h * 0.10 if index % 2 == 0 else 0)
        points.append((wave_x, wave_y))
    return points


def _build_body_geometry(cx, cy, body_w, body_h, shape):
    half_w = body_w / 2
    half_h = body_h / 2

    if shape == "round":
        radius = min(half_w, half_h)
        points = _ellipse_points(cx, cy, radius, radius)
    elif shape == "oval":
        points = _ellipse_points(cx, cy, half_w, half_h)
    elif shape == "blob":
        points = _smooth_blob_points(cx, cy, half_w, half_h)
    elif shape == "rounded_rect":
        points = _rounded_rect_points(cx, cy, half_w, half_h, min(half_w, half_h) / 3)
    elif shape == "squared":
        points = _rounded_rect_points(cx, cy, half_w, half_h, min(half_w, half_h) / 8)
    elif shape == "ghost":
        points = _ghost_outline_points(cx, cy, body_w, body_h)
    else:
        points = _ellipse_points(cx, cy, half_w, half_h)

    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return {
        "cx": cx,
        "cy": cy,
        "body_w": body_w,
        "body_h": body_h,
        "shape": shape,
        "points": points,
        "left": min(xs),
        "right": max(xs),
        "top": min(ys),
        "bottom": max(ys),
    }


def _polygon_edges(points):
    for index in range(len(points)):
        yield points[index], points[(index + 1) % len(points)]


def _dedupe_sorted(values, epsilon=0.5):
    result = []
    for value in sorted(values):
        if not result or abs(value - result[-1]) > epsilon:
            result.append(value)
    return result


def _horizontal_intersections(points, y):
    intersections = []
    for (x1, y1), (x2, y2) in _polygon_edges(points):
        if abs(y2 - y1) < 1e-6:
            if abs(y - y1) < 0.5:
                intersections.extend([x1, x2])
            continue
        if y < min(y1, y2) or y > max(y1, y2):
            continue
        ratio = (y - y1) / (y2 - y1)
        if 0 <= ratio <= 1:
            intersections.append(x1 + ratio * (x2 - x1))
    return _dedupe_sorted(intersections)


def _vertical_intersections(points, x):
    intersections = []
    for (x1, y1), (x2, y2) in _polygon_edges(points):
        if abs(x2 - x1) < 1e-6:
            if abs(x - x1) < 0.5:
                intersections.extend([y1, y2])
            continue
        if x < min(x1, x2) or x > max(x1, x2):
            continue
        ratio = (x - x1) / (x2 - x1)
        if 0 <= ratio <= 1:
            intersections.append(y1 + ratio * (y2 - y1))
    return _dedupe_sorted(intersections)


def _move_toward_center(body_geometry, point, inset):
    if inset <= 0:
        return point
    dx = body_geometry["cx"] - point[0]
    dy = body_geometry["cy"] - point[1]
    distance = math.hypot(dx, dy)
    if distance == 0:
        return point
    scale = min(inset, distance) / distance
    return (point[0] + dx * scale, point[1] + dy * scale)


def _body_side_anchor(body_geometry, side, y_ratio, inset=0):
    target_y = body_geometry["cy"] + max(min(y_ratio, 0.95), -0.95) * (body_geometry["body_h"] / 2)
    xs = _horizontal_intersections(body_geometry["points"], target_y)
    if xs:
        point = (min(xs), target_y) if side == "left" else (max(xs), target_y)
    else:
        fallback_x = body_geometry["left"] if side == "left" else body_geometry["right"]
        point = (fallback_x, target_y)
    return _move_toward_center(body_geometry, point, inset)


def _body_vertical_anchor(body_geometry, edge, x_ratio, inset=0):
    target_x = body_geometry["cx"] + max(min(x_ratio, 0.95), -0.95) * (body_geometry["body_w"] / 2)
    ys = _vertical_intersections(body_geometry["points"], target_x)
    if ys:
        point = (target_x, min(ys)) if edge == "top" else (target_x, max(ys))
    else:
        fallback_y = body_geometry["top"] if edge == "top" else body_geometry["bottom"]
        point = (target_x, fallback_y)
    return _move_toward_center(body_geometry, point, inset)


def _point_in_polygon(point, polygon):
    px, py = point
    inside = False
    for (x1, y1), (x2, y2) in _polygon_edges(polygon):
        crosses = ((y1 > py) != (y2 > py)) and (px < (x2 - x1) * (py - y1) / ((y2 - y1) or 1e-6) + x1)
        if crosses:
            inside = not inside
    return inside


def _sample_point_in_body(body_geometry, x_span, y_span):
    for _ in range(24):
        x = body_geometry["cx"] + random.uniform(*x_span) * (body_geometry["body_w"] / 2)
        y = body_geometry["cy"] + random.uniform(*y_span) * (body_geometry["body_h"] / 2)
        if _point_in_polygon((x, y), body_geometry["points"]):
            return x, y
    return body_geometry["cx"], body_geometry["cy"]


# ---------------------------------------------------------------------------
# Shared drawing primitives
# ---------------------------------------------------------------------------

def _simple_eyes(draw, positions, base_r, primary, secondary, line_w,
                 pupil_offset=True, brow=False, hollow=False):
    """Draw eyes at given (x, y) positions with consistent style."""
    for ex, ey in positions:
        r = random.randint(int(base_r * 0.88), int(base_r * 1.12))
        draw.ellipse(
            [ex - r, ey - r, ex + r, ey + r],
            fill=secondary, outline=primary, width=line_w,
        )
        if hollow:
            inner_r = max(r - line_w * 2, 2)
            draw.ellipse(
                [ex - inner_r, ey - inner_r, ex + inner_r, ey + inner_r],
                fill=secondary, outline=primary, width=max(line_w - 1, 1),
            )
        else:
            pr = max(r // 3, 2)
            if pupil_offset:
                off = max(pr // 2, 1)
                px = ex + random.randint(-off, off)
                py = ey + random.randint(-off, off)
            else:
                px, py = ex, ey
            draw.ellipse([px - pr, py - pr, px + pr, py + pr], fill=primary)
        if brow:
            by = ey - r - line_w * 2
            tilt = r // 3
            if ex < positions[0][0] + 1 and len(positions) > 1:
                draw.line([(ex - r, by + tilt), (ex + r, by)], fill=primary, width=max(line_w, 2))
            else:
                draw.line([(ex - r, by), (ex + r, by + tilt)], fill=primary, width=max(line_w, 2))


def _draw_claws(draw, hx, hy, angle, count, length, primary, line_w):
    """Draw claw fingers radiating from a hand position."""
    spread = math.pi * 0.5
    start = angle - spread / 2
    for i in range(count):
        a = start + (spread / max(count - 1, 1)) * i if count > 1 else angle
        tx = hx + length * math.cos(a)
        ty = hy + length * math.sin(a)
        draw.line([(hx, hy), (tx, ty)], fill=primary, width=line_w)


def _curvy_tentacle(draw, sx, sy, length, sway_range, tent_w, primary):
    """Draw a single tentacle with organic S-curves, tapering toward the tip."""
    pts = [(sx, sy)]
    segs = random.randint(3, 5)
    seg_len = length / segs
    for i in range(segs):
        d = 1 if i % 2 == 0 else -1
        x = pts[-1][0] + random.uniform(sway_range * 0.3, sway_range) * d
        y = pts[-1][1] + seg_len
        pts.append((x, y))
    for i in range(len(pts) - 1):
        w = max(tent_w - i, 2)
        draw.line([pts[i], pts[i + 1]], fill=primary, width=w)
    r = max(2, tent_w // 2)
    draw.ellipse([pts[-1][0] - r, pts[-1][1] - r, pts[-1][0] + r, pts[-1][1] + r], fill=primary)


def _draw_polygon_body(draw, points, fill, outline, line_w):
    """Draw a body from pre-computed polygon points."""
    draw.polygon(points, fill=fill, outline=outline, width=line_w)


# ---------------------------------------------------------------------------
# Archetype drawing templates
# ---------------------------------------------------------------------------

def _draw_spider_archetype(draw, cx, cy, zone_w, zone_h, primary, secondary, line_w):
    """Spider: small central body + head, 6-8 symmetrical jointed legs."""
    abd_rx = int(zone_w * 0.08) + random.randint(-4, 4)
    abd_ry = int(zone_h * 0.10) + random.randint(-4, 4)
    head_r = int(min(abd_rx, abd_ry) * 0.55)
    head_cy = cy - abd_ry - head_r + int(head_r * 0.35)

    num_pairs = random.choice([3, 4])
    seg1 = int(zone_w * random.uniform(0.12, 0.17))
    seg2 = int(zone_w * random.uniform(0.09, 0.13))
    leg_w = line_w + 1

    upper_angles = [0.50, 0.18, -0.10, -0.38][:num_pairs]
    lower_angles = [0.55, 0.70, 0.85, 0.95][:num_pairs]

    for i in range(num_pairs):
        for side in (-1, 1):
            ax = cx + side * abd_rx * 0.85
            ay = cy - abd_ry * 0.35 + i * (abd_ry * 0.45)

            knee_x = ax + side * seg1 * math.cos(upper_angles[i])
            knee_y = ay - seg1 * math.sin(upper_angles[i])

            foot_x = knee_x + side * seg2 * math.cos(lower_angles[i])
            foot_y = knee_y + seg2 * math.sin(lower_angles[i])

            draw.line([(ax, ay), (knee_x, knee_y)], fill=primary, width=leg_w)
            draw.line([(knee_x, knee_y), (foot_x, foot_y)], fill=primary, width=leg_w)

    draw.ellipse(
        [cx - abd_rx, cy - abd_ry, cx + abd_rx, cy + abd_ry],
        fill=secondary, outline=primary, width=line_w,
    )
    draw.ellipse(
        [cx - head_r, head_cy - head_r, cx + head_r, head_cy + head_r],
        fill=secondary, outline=primary, width=line_w,
    )

    num_eyes = random.choice([2, 4, 6])
    eye_r = max(int(head_r * 0.22), 3)
    sp_x = head_r * 0.40
    sp_y = head_r * 0.25
    if num_eyes == 2:
        positions = [(cx - sp_x, head_cy), (cx + sp_x, head_cy)]
    elif num_eyes == 4:
        positions = [
            (cx - sp_x, head_cy - sp_y), (cx + sp_x, head_cy - sp_y),
            (cx - sp_x * 0.6, head_cy + sp_y), (cx + sp_x * 0.6, head_cy + sp_y),
        ]
    else:
        positions = [
            (cx - sp_x, head_cy - sp_y), (cx + sp_x, head_cy - sp_y),
            (cx - sp_x * 0.7, head_cy), (cx + sp_x * 0.7, head_cy),
            (cx - sp_x * 0.4, head_cy + sp_y), (cx + sp_x * 0.4, head_cy + sp_y),
        ]
    _simple_eyes(draw, positions, eye_r, primary, secondary, line_w)

    m_y = head_cy + head_r
    m_len = max(int(head_r * 0.30), 4)
    draw.line([(cx - 3, m_y), (cx - 5, m_y + m_len)], fill=primary, width=line_w)
    draw.line([(cx + 3, m_y), (cx + 5, m_y + m_len)], fill=primary, width=line_w)


def _draw_dinosaur_archetype(draw, cx, cy, zone_w, zone_h, primary, secondary, line_w):
    """Dinosaur: horizontal body, separate head, tail, tiny arms, big back legs."""
    body_rx = int(zone_w * 0.13) + random.randint(-6, 6)
    body_ry = int(zone_h * 0.12) + random.randint(-4, 4)
    body_cx = cx - int(zone_w * 0.04)
    body_cy = cy

    head_r = int(body_ry * random.uniform(0.58, 0.68))
    head_cx = body_cx + body_rx + head_r - int(head_r * 0.25)
    head_cy = body_cy - int(body_ry * 0.32)

    tail_w = line_w + 3
    tail_x1 = body_cx - body_rx
    tail_y1 = body_cy + int(body_ry * 0.15)
    tail_x2 = tail_x1 - int(zone_w * 0.09)
    tail_y2 = tail_y1 + int(zone_h * 0.05)
    tail_x3 = tail_x2 - int(zone_w * 0.07)
    tail_y3 = tail_y2 + int(zone_h * 0.01)

    leg_w = line_w + 3
    back_leg_h = int(zone_h * random.uniform(0.18, 0.24))
    foot_r = max(leg_w + 2, 6)
    for x_off in (-0.30, 0.08):
        lx = body_cx + int(body_rx * x_off)
        ly = body_cy + body_ry
        draw.line([(lx, ly), (lx, ly + back_leg_h)], fill=primary, width=leg_w)
        draw.ellipse([lx - foot_r, ly + back_leg_h - foot_r // 2,
                      lx + foot_r, ly + back_leg_h + foot_r], fill=primary)

    draw.line([(tail_x1, tail_y1), (tail_x2, tail_y2)], fill=primary, width=tail_w)
    draw.line([(tail_x2, tail_y2), (tail_x3, tail_y3)], fill=primary, width=max(tail_w - 2, line_w))

    draw.ellipse(
        [body_cx - body_rx, body_cy - body_ry, body_cx + body_rx, body_cy + body_ry],
        fill=secondary, outline=primary, width=line_w,
    )

    num_spines = random.randint(3, 6)
    for i in range(num_spines):
        t = -0.5 + i * (1.0 / max(num_spines - 1, 1))
        spine_x = body_cx + body_rx * t
        y_edge = body_cy - body_ry * math.sqrt(max(0, 1 - t * t))
        spine_h = random.randint(int(body_ry * 0.14), int(body_ry * 0.24))
        sw = max(3, int(body_rx * 0.035))
        draw.polygon(
            [(spine_x, y_edge - spine_h), (spine_x - sw, y_edge + 2), (spine_x + sw, y_edge + 2)],
            fill=primary,
        )

    arm_len = int(body_rx * 0.28)
    arm_w_s = line_w + 1
    arm_ax = body_cx + int(body_rx * 0.55)
    arm_ay = body_cy - int(body_ry * 0.05)
    hand_x = arm_ax + int(arm_len * 0.45)
    hand_y = arm_ay + int(arm_len * 0.65)
    draw.line([(arm_ax, arm_ay), (hand_x, hand_y)], fill=primary, width=arm_w_s)
    _draw_claws(draw, hand_x, hand_y, 0.3, 2, max(arm_len // 4, 4), primary, line_w)

    neck_x = body_cx + body_rx - int(body_rx * 0.12)
    neck_y = body_cy - int(body_ry * 0.25)
    draw.line([(neck_x, neck_y), (head_cx - int(head_r * 0.35), head_cy + int(head_r * 0.1))],
              fill=primary, width=line_w + 3)

    draw.ellipse(
        [head_cx - head_r, head_cy - head_r, head_cx + head_r, head_cy + head_r],
        fill=secondary, outline=primary, width=line_w,
    )

    eye_x = head_cx + int(head_r * 0.18)
    eye_y = head_cy - int(head_r * 0.20)
    eye_r_size = max(int(head_r * 0.28), 5)
    _simple_eyes(draw, [(eye_x, eye_y)], eye_r_size, primary, secondary, line_w)

    mouth_y = head_cy + int(head_r * 0.35)
    mouth_w = int(head_r * 0.70)
    draw.line([(head_cx - int(mouth_w * 0.1), mouth_y), (head_cx + mouth_w, mouth_y)],
              fill=primary, width=line_w)
    num_teeth = random.randint(3, 5)
    tw = max(mouth_w // (num_teeth + 1), 3)
    th = max(tw, 3)
    for i in range(num_teeth):
        tx = head_cx + int(i * mouth_w / num_teeth)
        draw.polygon(
            [(tx, mouth_y), (tx + tw, mouth_y), (tx + tw // 2, mouth_y + th)],
            fill=secondary, outline=primary, width=max(line_w - 1, 1),
        )


def _draw_octopus_archetype(draw, cx, cy, zone_w, zone_h, primary, secondary, line_w):
    """Octopus: round dome body, 6-8 curling tentacles from bottom, no legs."""
    dome_rx = int(zone_w * random.uniform(0.14, 0.18))
    dome_ry = int(zone_h * random.uniform(0.14, 0.19))
    dome_cy = cy - int(zone_h * 0.08)

    num_tentacles = random.randint(5, 8)
    tent_w = line_w + 2
    tent_spread = dome_rx * 1.6
    tent_step = tent_spread / max(num_tentacles - 1, 1)
    tent_start_x = cx - tent_spread / 2
    tent_start_y = dome_cy + dome_ry - line_w

    for i in range(num_tentacles):
        tx = tent_start_x + i * tent_step
        length = int(zone_h * random.uniform(0.20, 0.34))
        sway = dome_rx * random.uniform(0.08, 0.18)
        _curvy_tentacle(draw, tx, tent_start_y, length, sway, tent_w, primary)

    dome_pts = _ellipse_points(cx, dome_cy, dome_rx, dome_ry)
    _draw_polygon_body(draw, dome_pts, secondary, primary, line_w)

    eye_r = max(int(dome_rx * 0.18), 6)
    eye_y = dome_cy - int(dome_ry * 0.10)
    spread = dome_rx * 0.50
    _simple_eyes(draw, [(cx - spread, eye_y), (cx + spread, eye_y)],
                 eye_r, primary, secondary, line_w)

    mouth_r = max(int(dome_rx * 0.08), 3)
    mouth_y = dome_cy + int(dome_ry * 0.35)
    draw.ellipse([cx - mouth_r, mouth_y - mouth_r, cx + mouth_r, mouth_y + mouth_r],
                 fill=primary)


def _draw_dragon_archetype(draw, cx, cy, zone_w, zone_h, primary, secondary, line_w):
    """Dragon: stocky body, prominent horns, bat wings, tail, 4 legs, teeth."""
    body_hw = int(zone_w * random.uniform(0.12, 0.15))
    body_hh = int(zone_h * random.uniform(0.15, 0.19))
    body_shape = random.choice(["oval", "blob", "rounded_rect"])
    body_geo = _build_body_geometry(cx, cy, body_hw * 2, body_hh * 2, body_shape)

    wing_w = int(zone_w * random.uniform(0.10, 0.16))
    wing_h = int(zone_h * random.uniform(0.16, 0.24))
    for side in (-1, 1):
        wx, wy = _body_side_anchor(body_geo, "left" if side < 0 else "right", -0.25, inset=line_w)
        tip_x = wx + side * wing_w
        tip_y = wy - wing_h
        mid_x = wx + side * wing_w * 0.3
        mid_y = wy + wing_h * 0.15
        scallop_x = wx + side * wing_w * 0.55
        scallop_y = wy - wing_h * 0.2
        draw.polygon(
            [(wx, wy), (tip_x, tip_y), (scallop_x, scallop_y), (mid_x, mid_y)],
            outline=primary, width=line_w,
        )
        draw.line([(wx, wy), (tip_x, tip_y)], fill=primary, width=line_w)

    tail_side = random.choice([-1, 1])
    tail_ax, tail_ay = _body_side_anchor(body_geo, "left" if tail_side < 0 else "right", 0.35, inset=line_w)
    tail_len = int(zone_w * random.uniform(0.10, 0.16))
    mid_x = tail_ax + tail_side * tail_len * 0.55
    mid_y = tail_ay + body_hh * 0.15
    end_x = mid_x + tail_side * tail_len * 0.45
    end_y = mid_y + body_hh * 0.10
    draw.line([(tail_ax, tail_ay), (mid_x, mid_y)], fill=primary, width=line_w + 2)
    draw.line([(mid_x, mid_y), (end_x, end_y)], fill=primary, width=line_w + 1)
    tip_w = max(int(tail_len * 0.08), 3)
    draw.polygon(
        [(end_x, end_y - tip_w), (end_x + tail_side * tip_w * 2, end_y), (end_x, end_y + tip_w)],
        fill=primary,
    )

    leg_w = line_w + 2
    leg_h = int(zone_h * random.uniform(0.12, 0.18))
    foot_r = max(leg_w + 1, 5)
    for x_ratio in (-0.30, -0.10, 0.10, 0.30):
        lx, ly = _body_vertical_anchor(body_geo, "bottom", x_ratio, inset=leg_w)
        draw.line([(lx, ly), (lx, ly + leg_h)], fill=primary, width=leg_w)
        draw.ellipse([lx - foot_r, ly + leg_h - foot_r // 2,
                      lx + foot_r, ly + leg_h + foot_r], fill=primary)

    _draw_polygon_body(draw, body_geo["points"], secondary, primary, line_w)

    num_spines = random.randint(3, 5)
    for i in range(num_spines):
        x_r = -0.35 + i * (0.70 / max(num_spines - 1, 1))
        sx, sy = _body_vertical_anchor(body_geo, "top", x_r, inset=line_w)
        spine_h = random.randint(int(body_hh * 0.10), int(body_hh * 0.18))
        sw = max(3, int(body_hw * 0.04))
        draw.polygon([(sx, sy - spine_h), (sx - sw, sy + 2), (sx + sw, sy + 2)], fill=primary)

    horn_h = int(body_hh * random.uniform(0.28, 0.42))
    horn_w = max(int(body_hw * 0.06), 4)
    for x_r in (-0.22, 0.22):
        hx, hy = _body_vertical_anchor(body_geo, "top", x_r, inset=line_w)
        direction = random.choice([-1, 1])
        draw.polygon(
            [(hx + direction * horn_w, hy - horn_h), (hx - horn_w, hy + line_w), (hx + horn_w, hy + line_w)],
            fill=primary,
        )

    eye_r = max(int(min(body_hw, body_hh) * 0.12), 5)
    eye_y = cy - int(body_hh * 0.20)
    eye_spread = body_hw * 0.45
    _simple_eyes(draw, [(cx - eye_spread, eye_y), (cx + eye_spread, eye_y)],
                 eye_r, primary, secondary, line_w, brow=True)

    mouth_y = cy + int(body_hh * 0.22)
    mouth_w = int(body_hw * 0.40)
    draw.arc([cx - mouth_w, mouth_y - mouth_w // 2, cx + mouth_w, mouth_y + mouth_w // 2],
             start=0, end=180, fill=primary, width=line_w)
    num_teeth = random.randint(3, 5)
    tw = max(mouth_w // (num_teeth + 1), 3)
    th = max(tw, 3)
    total_tw = num_teeth * tw + (num_teeth - 1) * 2
    sx = cx - total_tw // 2
    for i in range(num_teeth):
        tx = sx + i * (tw + 2)
        draw.polygon(
            [(tx, mouth_y - 1), (tx + tw, mouth_y - 1), (tx + tw // 2, mouth_y + th)],
            fill=secondary, outline=primary, width=max(line_w - 1, 1),
        )


def _draw_werewolf_archetype(draw, cx, cy, zone_w, zone_h, primary, secondary, line_w):
    """Werewolf: tall upright body, pointed ears, fangs, clawed hands."""
    body_hw = int(zone_w * random.uniform(0.11, 0.14))
    body_hh = int(zone_h * random.uniform(0.20, 0.26))
    body_shape = random.choice(["blob", "oval"])
    body_geo = _build_body_geometry(cx, cy, body_hw * 2, body_hh * 2, body_shape)

    arm_w = line_w + 2
    arm_len = int(body_hw * random.uniform(0.55, 0.75))
    claw_len = max(arm_len // 4, 6)
    for side_name, side in (("left", -1), ("right", 1)):
        ax, ay = _body_side_anchor(body_geo, side_name, -0.10, inset=arm_w)
        elbow_x = ax + side * arm_len * 0.6
        elbow_y = ay + arm_len * 0.25
        hand_x = elbow_x + side * arm_len * 0.4
        hand_y = elbow_y + arm_len * 0.45
        draw.line([(ax, ay), (elbow_x, elbow_y)], fill=primary, width=arm_w)
        draw.line([(elbow_x, elbow_y), (hand_x, hand_y)], fill=primary, width=arm_w)
        angle = math.pi - 0.25 if side < 0 else 0.25
        _draw_claws(draw, hand_x, hand_y, angle, 3, claw_len, primary, line_w)

    leg_w = line_w + 3
    leg_h = int(zone_h * random.uniform(0.13, 0.18))
    foot_r = max(leg_w + 1, 6)
    for x_r in (-0.25, 0.25):
        lx, ly = _body_vertical_anchor(body_geo, "bottom", x_r, inset=leg_w)
        draw.line([(lx, ly), (lx, ly + leg_h)], fill=primary, width=leg_w)
        draw.ellipse([lx - foot_r, ly + leg_h - foot_r // 2,
                      lx + foot_r, ly + leg_h + foot_r], fill=primary)

    _draw_polygon_body(draw, body_geo["points"], secondary, primary, line_w)

    ear_h = max(int(body_hh * 0.16), 14)
    ear_w = max(int(body_hw * 0.12), 8)
    for x_r, direction in ((-0.28, -1), (0.28, 1)):
        ex, ey = _body_vertical_anchor(body_geo, "top", x_r, inset=line_w)
        points = [
            (ex, ey - ear_h),
            (ex - direction * ear_w, ey + line_w),
            (ex + direction * (ear_w // 3), ey + line_w),
        ]
        draw.polygon(points, fill=secondary, outline=primary, width=line_w)

    fur_count = random.randint(4, 8)
    for _ in range(fur_count):
        angle = random.uniform(0, 2 * math.pi)
        edge_x = cx + body_hw * math.cos(angle)
        edge_y = cy + body_hh * math.sin(angle)
        tuft_len = random.randint(int(body_hw * 0.05), int(body_hw * 0.12))
        tx = edge_x + tuft_len * math.cos(angle)
        ty = edge_y + tuft_len * math.sin(angle)
        draw.line([(edge_x, edge_y), (tx, ty)], fill=primary, width=line_w)

    eye_r = max(int(min(body_hw, body_hh) * 0.09), 5)
    eye_y = cy - int(body_hh * 0.25)
    eye_spread = body_hw * 0.40
    _simple_eyes(draw, [(cx - eye_spread, eye_y), (cx + eye_spread, eye_y)],
                 eye_r, primary, secondary, line_w, brow=True)

    mouth_y = cy + int(body_hh * 0.10)
    mouth_w = max(int(body_hw * 0.35), 8)
    draw.arc([cx - mouth_w, mouth_y - mouth_w // 2, cx + mouth_w, mouth_y + mouth_w // 2],
             start=0, end=180, fill=primary, width=line_w)
    fang_h = max(int(mouth_w * 0.5), 5)
    fang_w = max(int(mouth_w * 0.18), 3)
    for fang_x in (cx - mouth_w + fang_w, cx + mouth_w - fang_w * 2):
        draw.polygon(
            [(fang_x, mouth_y - 1), (fang_x + fang_w, mouth_y - 1),
             (fang_x + fang_w // 2, mouth_y + fang_h)],
            fill=secondary, outline=primary, width=max(line_w - 1, 1),
        )


def _draw_zombie_archetype(draw, cx, cy, zone_w, zone_h, primary, secondary, line_w):
    """Zombie: asymmetric face, stitches, hanging arms, shuffling legs."""
    body_hw = int(zone_w * random.uniform(0.11, 0.15))
    body_hh = int(zone_h * random.uniform(0.18, 0.24))
    tilt = random.uniform(-0.04, 0.04) * zone_w
    body_cx = cx + tilt
    body_shape = random.choice(["rounded_rect", "squared", "round"])
    body_geo = _build_body_geometry(body_cx, cy, body_hw * 2, body_hh * 2, body_shape)

    arm_w = line_w + 2
    arm_len = int(body_hw * random.uniform(0.65, 0.85))
    for side_name, side, y_off in (("left", -1, 0.05), ("right", 1, -0.10)):
        ax, ay = _body_side_anchor(body_geo, side_name, y_off, inset=arm_w)
        hand_x = ax + side * arm_len * 0.75
        hand_y = ay + arm_len * random.uniform(0.70, 1.0)
        draw.line([(ax, ay), (hand_x, hand_y)], fill=primary, width=arm_w)
        _draw_claws(draw, hand_x, hand_y, math.pi / 2 + side * 0.2, 3,
                    max(arm_len // 5, 5), primary, line_w)

    leg_w = line_w + 3
    leg_h = int(zone_h * random.uniform(0.14, 0.19))
    foot_r = max(leg_w + 1, 5)
    offsets = [(-0.22, 0), (0.22, leg_h * 0.08)]
    for x_r, y_extra in offsets:
        lx, ly = _body_vertical_anchor(body_geo, "bottom", x_r, inset=leg_w)
        draw.line([(lx, ly), (lx, ly + leg_h + y_extra)], fill=primary, width=leg_w)
        draw.ellipse([lx - foot_r, ly + leg_h + y_extra - foot_r // 2,
                      lx + foot_r, ly + leg_h + y_extra + foot_r], fill=primary)

    _draw_polygon_body(draw, body_geo["points"], secondary, primary, line_w)

    left_eye_r = max(int(min(body_hw, body_hh) * random.uniform(0.09, 0.13)), 5)
    right_eye_r = max(int(left_eye_r * random.uniform(0.60, 0.85)), 4)
    eye_y = cy - int(body_hh * 0.22)
    eye_spread = body_hw * 0.35
    left_pos = (body_cx - eye_spread, eye_y)
    right_pos = (body_cx + eye_spread, eye_y + random.randint(0, int(left_eye_r * 0.4)))

    for ex, ey, er in [(left_pos[0], left_pos[1], left_eye_r), (right_pos[0], right_pos[1], right_eye_r)]:
        draw.ellipse([ex - er, ey - er, ex + er, ey + er], fill=secondary, outline=primary, width=line_w)
        pr = max(er // 3, 2)
        draw.ellipse([ex - pr, ey - pr, ex + pr, ey + pr], fill=primary)

    num_stitches = random.randint(2, 4)
    for _ in range(num_stitches):
        sx = body_cx + random.randint(int(-body_hw * 0.6), int(body_hw * 0.6))
        sy = cy + random.randint(int(-body_hh * 0.4), int(body_hh * 0.4))
        stitch_len = random.randint(int(body_hw * 0.08), int(body_hw * 0.16))
        angle = random.uniform(-0.4, 0.4)
        x2 = sx + stitch_len * math.cos(angle)
        y2 = sy + stitch_len * math.sin(angle)
        draw.line([(sx, sy), (x2, y2)], fill=primary, width=line_w)
        mid_x = (sx + x2) / 2
        mid_y = (sy + y2) / 2
        cross_len = stitch_len * 0.3
        draw.line([(mid_x - cross_len * math.sin(angle), mid_y + cross_len * math.cos(angle)),
                   (mid_x + cross_len * math.sin(angle), mid_y - cross_len * math.cos(angle))],
                  fill=primary, width=line_w)

    mouth_y = cy + int(body_hh * 0.15)
    mouth_w = max(int(body_hw * 0.30), 7)
    draw.line([(body_cx - mouth_w, mouth_y), (body_cx + mouth_w, mouth_y)], fill=primary, width=line_w)
    num_teeth = random.randint(3, 5)
    tw = max(mouth_w * 2 // (num_teeth + 1), 3)
    th = max(tw, 3)
    total_tw = num_teeth * tw + (num_teeth - 1) * 2
    start_x = body_cx - total_tw // 2
    for i in range(num_teeth):
        if random.random() < 0.3:
            continue
        tx = start_x + i * (tw + 2)
        draw.rectangle([tx, mouth_y, tx + tw, mouth_y + th],
                        fill=secondary, outline=primary, width=max(line_w - 1, 1))


def _draw_cthulhu_archetype(draw, cx, cy, zone_w, zone_h, primary, secondary, line_w):
    """Cthulhu: huge head, narrow body, face tentacles, small wings."""
    head_rx = int(zone_w * random.uniform(0.14, 0.18))
    head_ry = int(zone_h * random.uniform(0.17, 0.22))
    head_cy = cy - int(zone_h * 0.06)
    head_shape = random.choice(["blob", "oval"])
    head_pts = (_smooth_blob_points(cx, head_cy, head_rx, head_ry)
                if head_shape == "blob" else _ellipse_points(cx, head_cy, head_rx, head_ry))

    body_hw = int(head_rx * 0.55)
    body_hh = int(head_ry * 0.60)
    body_cy = head_cy + head_ry + body_hh - int(body_hh * 0.25)
    body_pts = _ellipse_points(cx, body_cy, body_hw, body_hh)

    wing_w = int(zone_w * random.uniform(0.06, 0.10))
    wing_h = int(zone_h * random.uniform(0.10, 0.16))
    for side in (-1, 1):
        wx = cx + side * body_hw
        wy = body_cy - int(body_hh * 0.2)
        tip_x = wx + side * wing_w
        tip_y = wy - wing_h
        bot_x = wx + side * int(wing_w * 0.3)
        bot_y = wy + int(wing_h * 0.15)
        draw.polygon([(wx, wy), (tip_x, tip_y), (bot_x, bot_y)], outline=primary, width=line_w)

    arm_w = line_w + 1
    arm_len = int(body_hw * 0.6)
    for side in (-1, 1):
        ax = cx + side * body_hw * 0.9
        ay = body_cy
        hand_x = ax + side * arm_len
        hand_y = ay + arm_len * 0.5
        draw.line([(ax, ay), (hand_x, hand_y)], fill=primary, width=arm_w)
        _draw_claws(draw, hand_x, hand_y, math.pi - 0.2 if side < 0 else 0.2, 3,
                    max(arm_len // 3, 5), primary, line_w)

    _draw_polygon_body(draw, body_pts, secondary, primary, line_w)
    _draw_polygon_body(draw, head_pts, secondary, primary, line_w)

    horn_h = int(head_ry * random.uniform(0.18, 0.30))
    horn_w_px = max(int(head_rx * 0.05), 3)
    for x_off in (-0.25, 0.25):
        hx = cx + head_rx * x_off
        hy = head_cy - head_ry * 0.9
        draw.polygon([(hx, hy - horn_h), (hx - horn_w_px, hy + 2), (hx + horn_w_px, hy + 2)],
                     fill=primary)

    eye_r = max(int(head_rx * 0.12), 5)
    eye_y = head_cy - int(head_ry * 0.15)
    eye_spread = head_rx * 0.45
    num_eyes = random.choice([2, 3])
    if num_eyes == 2:
        positions = [(cx - eye_spread, eye_y), (cx + eye_spread, eye_y)]
    else:
        positions = [(cx - eye_spread, eye_y), (cx, eye_y - int(eye_r * 0.5)), (cx + eye_spread, eye_y)]
    _simple_eyes(draw, positions, eye_r, primary, secondary, line_w, brow=True)

    tent_total = random.randint(4, 7)
    tent_spread = head_rx * 1.0
    tent_step = tent_spread / max(tent_total - 1, 1)
    tent_start_x = cx - tent_spread / 2
    tent_start_y = head_cy + int(head_ry * 0.55)
    tent_w = line_w + 1
    for i in range(tent_total):
        tx = tent_start_x + i * tent_step
        length = int(head_ry * random.uniform(0.45, 0.75))
        sway = head_rx * 0.10
        _curvy_tentacle(draw, tx, tent_start_y, length, sway, tent_w, primary)


def _draw_ghost_archetype(draw, cx, cy, zone_w, zone_h, primary, secondary, line_w):
    """Ghost: dome top, wavy bottom, hollow eyes, small mouth, no legs."""
    body_w = int(zone_w * random.uniform(0.24, 0.32))
    body_h = int(zone_h * random.uniform(0.55, 0.66))
    ghost_pts = _ghost_outline_points(cx, cy, body_w, body_h)
    body_geo = _build_body_geometry(cx, cy, body_w, body_h, "ghost")

    has_arms = random.random() < 0.5
    if has_arms:
        arm_w = line_w + 1
        arm_len = int(body_w * 0.18)
        for side_name, side in (("left", -1), ("right", 1)):
            ax, ay = _body_side_anchor(body_geo, side_name, -0.05, inset=arm_w)
            hand_x = ax + side * arm_len
            hand_y = ay - arm_len * 0.3
            draw.line([(ax, ay), (hand_x, hand_y)], fill=primary, width=arm_w)

    _draw_polygon_body(draw, ghost_pts, secondary, primary, line_w)

    eye_r = max(int(min(body_w, body_h) * 0.07), 6)
    eye_y = cy - int(body_h * 0.15)
    eye_spread = body_w * 0.22
    _simple_eyes(draw, [(cx - eye_spread, eye_y), (cx + eye_spread, eye_y)],
                 eye_r, primary, secondary, line_w, hollow=True)

    mouth_r = max(int(body_w * 0.05), 4)
    mouth_y = cy + int(body_h * 0.05)
    draw.ellipse([cx - mouth_r, mouth_y - int(mouth_r * 1.3),
                  cx + mouth_r, mouth_y + int(mouth_r * 1.3)],
                 outline=primary, width=line_w)


def _draw_default_archetype(draw, cx, cy, zone_w, zone_h, primary, secondary, line_w):
    """Default: fully random monster with random body, limbs, and features."""
    body_hw = int(zone_w * random.uniform(0.12, 0.18))
    body_hh = int(zone_h * random.uniform(0.16, 0.24))
    body_shape = random.choice(["round", "oval", "blob", "rounded_rect", "squared"])
    body_geo = _build_body_geometry(cx, cy, body_hw * 2, body_hh * 2, body_shape)

    use_tentacles = random.random() < 0.25
    use_arms = random.random() < 0.75
    use_wings = random.random() < 0.20
    use_tail = random.random() < 0.25
    use_horns = random.random() < 0.30
    num_legs = 0 if use_tentacles else random.choices([2, 3, 4], weights=[60, 20, 20])[0]

    if use_wings:
        wing_w = int(body_hw * random.uniform(0.35, 0.55))
        wing_h = int(body_hh * random.uniform(0.45, 0.65))
        for side_name, side in (("left", -1), ("right", 1)):
            wx, wy = _body_side_anchor(body_geo, side_name, -0.15, inset=line_w)
            draw.polygon(
                [(wx, wy),
                 (wx + side * wing_w, wy - wing_h),
                 (wx + side * int(wing_w * 0.3), wy + int(wing_h * 0.15))],
                outline=primary, width=line_w,
            )

    if use_tail:
        tail_side = random.choice([-1, 1])
        tail_ax, tail_ay = _body_side_anchor(body_geo, "left" if tail_side < 0 else "right", 0.25, inset=line_w)
        tail_len = int(body_hw * random.uniform(0.40, 0.65))
        end_x = tail_ax + tail_side * tail_len
        end_y = tail_ay + int(body_hh * 0.15)
        draw.line([(tail_ax, tail_ay), (end_x, end_y)], fill=primary, width=line_w + 1)

    if use_tentacles:
        num_t = random.randint(4, 7)
        tent_w = line_w + 2
        spread = 0.70
        step = spread / max(num_t - 1, 1)
        for i in range(num_t):
            x_r = (-spread / 2) + i * step
            tx, ty = _body_vertical_anchor(body_geo, "bottom", x_r, inset=tent_w)
            length = int(body_hh * random.uniform(0.50, 0.85))
            sway = body_hw * 0.12
            _curvy_tentacle(draw, tx, ty, length, sway, tent_w, primary)
    else:
        leg_w = line_w + 3
        leg_h = int(zone_h * random.uniform(0.10, 0.18))
        foot_r = max(leg_w + 1, 5)
        if num_legs > 0:
            spread = 0.50
            step = spread / max(num_legs - 1, 1) if num_legs > 1 else 0
            for i in range(num_legs):
                x_r = (-spread / 2 + i * step) if num_legs > 1 else 0
                lx, ly = _body_vertical_anchor(body_geo, "bottom", x_r, inset=leg_w)
                draw.line([(lx, ly), (lx, ly + leg_h)], fill=primary, width=leg_w)
                draw.ellipse([lx - foot_r, ly + leg_h - foot_r // 2,
                              lx + foot_r, ly + leg_h + foot_r], fill=primary)

    if use_arms:
        arm_w = line_w + 2
        arm_len = int(body_hw * random.uniform(0.45, 0.70))
        arm_style = random.choice(["short", "raised", "normal"])
        for side_name, side in (("left", -1), ("right", 1)):
            ax, ay = _body_side_anchor(body_geo, side_name, -0.02, inset=arm_w)
            if arm_style == "short":
                end_x, end_y = ax + side * arm_len, ay
            elif arm_style == "raised":
                end_x, end_y = ax + side * arm_len, ay - arm_len * 0.65
            else:
                end_x, end_y = ax + side * arm_len, ay + arm_len * 0.30
            draw.line([(ax, ay), (end_x, end_y)], fill=primary, width=arm_w)
            finger_len = max(arm_len // 4, 5)
            angle = math.atan2(end_y - ay, end_x - ax)
            _draw_claws(draw, end_x, end_y, angle, random.randint(2, 3), finger_len, primary, line_w)

    _draw_polygon_body(draw, body_geo["points"], secondary, primary, line_w)

    if use_horns:
        horn_count = random.choice([1, 2])
        horn_h = int(body_hh * random.uniform(0.20, 0.35))
        horn_w_px = max(int(body_hw * 0.05), 4)
        ratios = [0.0] if horn_count == 1 else [-0.20, 0.20]
        for x_r in ratios:
            hx, hy = _body_vertical_anchor(body_geo, "top", x_r, inset=line_w)
            draw.polygon([(hx, hy - horn_h), (hx - horn_w_px, hy + 2), (hx + horn_w_px, hy + 2)],
                         fill=primary)

    num_eyes = random.choices([1, 2, 3], weights=[20, 55, 25])[0]
    eye_r = max(int(min(body_hw, body_hh) * 0.10), 5)
    eye_y = cy - int(body_hh * 0.18)
    eye_zone_w = body_hw * 0.50
    if num_eyes == 1:
        positions = [(cx, eye_y)]
    else:
        spacing = eye_zone_w / max(num_eyes - 1, 1)
        start_x = cx - eye_zone_w / 2
        positions = [(start_x + i * spacing, eye_y) for i in range(num_eyes)]
    _simple_eyes(draw, positions, eye_r, primary, secondary, line_w)

    mouth_y = cy + int(body_hh * 0.22)
    mouth_w = max(int(body_hw * random.uniform(0.15, 0.30)), 6)
    style = random.choice(["smile", "open", "small", "teeth"])
    if style == "smile":
        draw.arc([cx - mouth_w, mouth_y - mouth_w // 2, cx + mouth_w, mouth_y + mouth_w // 2],
                 start=0, end=180, fill=primary, width=line_w)
    elif style == "open":
        ry = max(mouth_w * 2 // 3, 5)
        draw.ellipse([cx - mouth_w, mouth_y - ry, cx + mouth_w, mouth_y + ry], fill=primary)
    elif style == "small":
        sr = max(mouth_w // 3, 4)
        draw.ellipse([cx - sr, mouth_y - sr, cx + sr, mouth_y + sr], fill=primary)
    elif style == "teeth":
        draw.arc([cx - mouth_w, mouth_y - mouth_w // 2, cx + mouth_w, mouth_y + mouth_w // 2],
                 start=0, end=180, fill=primary, width=line_w)
        num_teeth = random.randint(2, 4)
        tw = max(mouth_w // (num_teeth + 1), 3)
        th = max(tw, 3)
        total_tw = num_teeth * tw + (num_teeth - 1) * 2
        sx = cx - total_tw // 2
        for i in range(num_teeth):
            tx = sx + i * (tw + 2)
            draw.rectangle([tx, mouth_y - 1, tx + tw, mouth_y + th],
                            fill=secondary, outline=primary, width=max(line_w - 1, 1))


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

ARCHETYPE_DRAWERS = {
    "spider": _draw_spider_archetype,
    "dinosaur": _draw_dinosaur_archetype,
    "octopus": _draw_octopus_archetype,
    "dragon": _draw_dragon_archetype,
    "werewolf": _draw_werewolf_archetype,
    "zombie": _draw_zombie_archetype,
    "cthulhu": _draw_cthulhu_archetype,
    "ghost": _draw_ghost_archetype,
    "default": _draw_default_archetype,
}


def _pick_archetype(mode):
    """Resolve the archetype mode from settings into a concrete archetype name."""
    if mode == "random":
        return random.choice(ARCHETYPE_ORDER)
    if mode in ARCHETYPE_DRAWERS:
        return mode
    return random.choice(ARCHETYPE_ORDER)


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------

class TinyMonsters(BasePlugin):
    """Generate cute monsters with archetype-specific silhouettes and structure."""

    def generate_image(self, settings, device_config):
        primary_color = ImageColor.getcolor(settings.get("primaryColor") or "#000000", "RGB")
        secondary_color = ImageColor.getcolor(settings.get("secondaryColor") or "#ffffff", "RGB")
        archetype_mode = settings.get("archetype") or "random"

        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]

        width, height = dimensions
        image = Image.new("RGB", (width, height), secondary_color)
        draw = ImageDraw.Draw(image)

        line_w = max(int(min(width, height) * 0.008), 3)
        title_zone_h = int(height * 0.10)
        name_zone_h = int(height * 0.10)
        monster_zone_h = height - title_zone_h - name_zone_h
        monster_cx = width // 2
        monster_cy = title_zone_h + monster_zone_h // 2

        title_font = get_font("Jost", max(int(height * 0.05), 16), "bold")
        if title_font:
            draw.text((width // 2, title_zone_h // 2), "Tiny Monsters",
                      font=title_font, fill=primary_color, anchor="mm")

        monster_name = generate_monster_name()
        archetype = _pick_archetype(archetype_mode)

        drawer = ARCHETYPE_DRAWERS[archetype]
        drawer(draw, monster_cx, monster_cy, width, monster_zone_h,
               primary_color, secondary_color, line_w)

        name_font = get_font("Jost", max(int(height * 0.045), 14))
        if name_font:
            archetype_label = archetype.replace("_", " ").title()
            draw.text(
                (width // 2, height - name_zone_h // 2),
                f"{monster_name} - {archetype_label}",
                font=name_font,
                fill=primary_color,
                anchor="mm",
            )

        return image
