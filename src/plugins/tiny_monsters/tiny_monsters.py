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
# Organic / hand-drawn drawing helpers
# ---------------------------------------------------------------------------

def _wobbly_line(draw, pts, width, fill):
    """Draw a polyline through *pts* with slight hand-drawn wobble."""
    for i in range(len(pts) - 1):
        x1, y1 = pts[i]
        x2, y2 = pts[i + 1]
        draw.line([(x1, y1), (x2, y2)], fill=fill, width=width)


def _bezier_pts(p0, p1, p2, steps=12):
    """Return a list of points along a quadratic Bézier curve."""
    out = []
    for i in range(steps + 1):
        t = i / steps
        u = 1 - t
        x = u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0]
        y = u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]
        out.append((x, y))
    return out


def _cubic_bezier_pts(p0, p1, p2, p3, steps=16):
    """Return a list of points along a cubic Bézier curve."""
    out = []
    for i in range(steps + 1):
        t = i / steps
        u = 1 - t
        x = u**3*p0[0] + 3*u**2*t*p1[0] + 3*u*t**2*p2[0] + t**3*p3[0]
        y = u**3*p0[1] + 3*u**2*t*p1[1] + 3*u*t**2*p2[1] + t**3*p3[1]
        out.append((x, y))
    return out


def _draw_thick_curve(draw, pts, width, fill):
    """Draw a smooth curve through *pts* with consistent width."""
    for i in range(len(pts) - 1):
        draw.line([pts[i], pts[i + 1]], fill=fill, width=width)


def _organic_blob(cx, cy, rx, ry, num_points=40, wobble=0.08):
    """Generate an organic closed shape — like a hand-drawn circle."""
    pts = []
    for i in range(num_points):
        a = 2 * math.pi * i / num_points
        r_jitter = 1.0 + random.uniform(-wobble, wobble)
        pts.append((cx + rx * r_jitter * math.cos(a),
                     cy + ry * r_jitter * math.sin(a)))
    return pts


def _draw_filled_blob(draw, cx, cy, rx, ry, fill, outline, line_w, wobble=0.08):
    """Draw an organic filled blob shape."""
    pts = _organic_blob(cx, cy, rx, ry, wobble=wobble)
    draw.polygon(pts, fill=fill, outline=outline, width=line_w)
    return pts


def _draw_organic_limb(draw, x1, y1, x2, y2, thickness, fill, taper=0.7):
    """Draw a thick organic limb using a Bézier with tapering."""
    mx = (x1 + x2) / 2 + random.uniform(-thickness, thickness) * 0.4
    my = (y1 + y2) / 2 + random.uniform(-thickness, thickness) * 0.3
    pts = _bezier_pts((x1, y1), (mx, my), (x2, y2), steps=10)
    for i in range(len(pts) - 1):
        t = i / max(len(pts) - 1, 1)
        w = max(int(thickness * (1.0 - t * (1.0 - taper))), 2)
        draw.line([pts[i], pts[i + 1]], fill=fill, width=w)


def _draw_organic_leg(draw, x1, y1, x2, y2, thickness, fill, foot_r=0):
    """Draw a thick cartoon leg with optional round foot."""
    _draw_organic_limb(draw, x1, y1, x2, y2, thickness, fill, taper=0.85)
    if foot_r > 0:
        pts = _organic_blob(x2, y2 + foot_r * 0.3, foot_r, foot_r * 0.6, wobble=0.06)
        draw.polygon(pts, fill=fill)


def _draw_expressive_eyes(draw, positions, base_r, primary, secondary, line_w,
                           style="normal", look_dir=0):
    """Draw cartoon eyes at positions. style: normal|sleepy|angry|cute|hollow."""
    for i, (ex, ey) in enumerate(positions):
        r = base_r + random.randint(-1, 1)
        # outer eye with slight wobble
        eye_pts = _organic_blob(ex, ey, r, r, wobble=0.04)
        draw.polygon(eye_pts, fill=secondary, outline=primary, width=line_w)

        if style == "hollow":
            inner = max(r - line_w * 2, 2)
            draw.ellipse([ex - inner, ey - inner, ex + inner, ey + inner],
                         fill=secondary, outline=primary, width=max(line_w - 1, 1))
        else:
            # pupil
            pr = max(r // 3, 2)
            px = ex + int(look_dir * pr * 0.5)
            py = ey + random.randint(-1, 1)
            draw.ellipse([px - pr, py - pr, px + pr, py + pr], fill=primary)
            # highlight
            hr = max(pr // 2, 1)
            draw.ellipse([px - hr - 1, py - hr - 1, px - hr + hr, py - hr + hr],
                         fill=secondary)

        # sleepy = half-closed lid
        if style == "sleepy":
            draw.rectangle([ex - r - 1, ey - r - 1, ex + r + 1, ey - r * 0.2],
                           fill=secondary)
            draw.line([(ex - r, ey - r * 0.2), (ex + r, ey - r * 0.1)],
                      fill=primary, width=line_w)

        # angry = angled brow
        if style == "angry":
            brow_y = ey - r - line_w * 2
            side = -1 if i == 0 else 1
            draw.line([(ex - r * 0.8, brow_y - r * 0.3 * side),
                       (ex + r * 0.8, brow_y + r * 0.3 * side)],
                      fill=primary, width=max(line_w + 1, 3))

        # cute = simple dot brow
        if style == "cute":
            brow_y = ey - r - line_w * 2
            draw.line([(ex - r * 0.4, brow_y), (ex + r * 0.4, brow_y - 2)],
                      fill=primary, width=max(line_w, 2))


def _draw_mouth(draw, cx, cy, width, primary, secondary, line_w,
                style="smile"):
    """Draw a cartoon mouth. Styles: smile|grin|open|confused|teeth|sleepy."""
    hw = width // 2
    if style == "smile":
        pts = _bezier_pts((cx - hw, cy), (cx, cy + hw * 0.7), (cx + hw, cy), steps=10)
        _draw_thick_curve(draw, pts, line_w, primary)
    elif style == "grin":
        pts = _bezier_pts((cx - hw, cy), (cx, cy + hw * 0.8), (cx + hw, cy), steps=10)
        _draw_thick_curve(draw, pts, line_w, primary)
        # teeth line
        draw.line([(cx - hw + 3, cy + 1), (cx + hw - 3, cy + 1)],
                  fill=primary, width=max(line_w - 1, 1))
        # individual teeth
        n_teeth = random.randint(2, 5)
        tw = max(hw * 2 // (n_teeth + 1), 3)
        for i in range(n_teeth):
            tx = cx - hw + 3 + i * (tw + 1)
            draw.line([(tx, cy + 1), (tx, cy + tw * 0.6)],
                      fill=secondary, width=max(line_w - 1, 1))
    elif style == "open":
        mr = max(hw // 2, 4)
        pts = _organic_blob(cx, cy + 2, mr, int(mr * 0.7), wobble=0.06)
        draw.polygon(pts, fill=primary)
    elif style == "confused":
        pts = _bezier_pts((cx - hw * 0.5, cy + 2),
                          (cx, cy - hw * 0.3),
                          (cx + hw * 0.5, cy + 2), steps=8)
        _draw_thick_curve(draw, pts, line_w, primary)
    elif style == "teeth":
        draw.line([(cx - hw, cy), (cx + hw, cy)], fill=primary, width=line_w)
        n_teeth = random.randint(2, 5)
        tw = max(hw * 2 // (n_teeth + 1), 3)
        th = max(tw, 3)
        total = n_teeth * tw + (n_teeth - 1) * 2
        sx = cx - total // 2
        for i in range(n_teeth):
            if random.random() < 0.25:
                continue
            tx = sx + i * (tw + 2)
            draw.polygon(
                [(tx, cy), (tx + tw, cy), (tx + tw // 2, cy + th)],
                fill=secondary, outline=primary, width=max(line_w - 1, 1))
    elif style == "sleepy":
        pts = _bezier_pts((cx - hw * 0.4, cy),
                          (cx, cy + hw * 0.2),
                          (cx + hw * 0.4, cy), steps=6)
        _draw_thick_curve(draw, pts, line_w, primary)


def _draw_simple_spikes(draw, pts_along_curve, spike_h_range, spike_w, fill):
    """Draw triangular spikes along a series of points."""
    for x, y in pts_along_curve:
        sh = random.randint(*spike_h_range)
        sw = spike_w + random.randint(-1, 1)
        draw.polygon([(x, y - sh), (x - sw, y + 2), (x + sw, y + 2)], fill=fill)


def _draw_fur_edge(draw, pts, tuft_len_range, fill, line_w):
    """Draw small fur tufts along an outline."""
    step = max(len(pts) // random.randint(6, 14), 1)
    for i in range(0, len(pts), step):
        px, py = pts[i]
        # direction away from center
        tl = random.randint(*tuft_len_range)
        angle = random.uniform(0, 2 * math.pi)
        tx = px + tl * math.cos(angle)
        ty = py + tl * math.sin(angle)
        draw.line([(px, py), (tx, ty)], fill=fill, width=line_w)


def _draw_stitches(draw, cx, cy, hw, hh, count, primary, line_w):
    """Draw cross-shaped stitches scattered on a body."""
    for _ in range(count):
        sx = cx + random.randint(int(-hw * 0.6), int(hw * 0.6))
        sy = cy + random.randint(int(-hh * 0.5), int(hh * 0.5))
        sl = random.randint(max(int(hw * 0.06), 4), max(int(hw * 0.18), 6))
        angle = random.uniform(-0.5, 0.5)
        x2 = sx + sl * math.cos(angle)
        y2 = sy + sl * math.sin(angle)
        draw.line([(sx, sy), (x2, y2)], fill=primary, width=line_w)
        mid_x, mid_y = (sx + x2) / 2, (sy + y2) / 2
        cl = sl * 0.35
        draw.line([(mid_x - cl * math.sin(angle), mid_y + cl * math.cos(angle)),
                   (mid_x + cl * math.sin(angle), mid_y - cl * math.cos(angle))],
                  fill=primary, width=line_w)


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
# Archetype drawing templates — cartoon doodle style
# ---------------------------------------------------------------------------

def _draw_dinosaur_archetype(draw, cx, cy, zone_w, zone_h, primary, secondary, line_w):
    """Dinosaur: rounded body, curved neck, thick tail, small arms, short legs, back spikes."""
    # --- pose: slight tilt and offset ---
    tilt = random.uniform(-0.03, 0.03)
    lean_x = int(zone_w * random.uniform(-0.02, 0.02))
    bcx = cx + lean_x

    # --- body proportions ---
    body_tier = random.choice(["chubby", "normal", "tall"])
    if body_tier == "chubby":
        body_rx = int(zone_w * random.uniform(0.12, 0.16))
        body_ry = int(zone_h * random.uniform(0.12, 0.16))
    elif body_tier == "normal":
        body_rx = int(zone_w * random.uniform(0.10, 0.14))
        body_ry = int(zone_h * random.uniform(0.14, 0.20))
    else:
        body_rx = int(zone_w * random.uniform(0.08, 0.12))
        body_ry = int(zone_h * random.uniform(0.18, 0.24))

    body_cy = cy + int(zone_h * 0.04)

    # --- head: large relative to body (cartoon proportion) ---
    head_r = max(int(body_rx * random.uniform(0.55, 0.85)), 14)
    neck_tier = random.choice(["none", "short", "long"])
    if neck_tier == "none":
        neck_len = 0
        head_cx = bcx + int(body_rx * 0.4)
        head_cy = body_cy - body_ry - int(head_r * 0.3)
    elif neck_tier == "short":
        neck_len = int(body_ry * random.uniform(0.15, 0.30))
        head_cx = bcx + int(body_rx * random.uniform(0.2, 0.5))
        head_cy = body_cy - body_ry - neck_len - int(head_r * 0.2)
    else:
        neck_len = int(body_ry * random.uniform(0.35, 0.55))
        head_cx = bcx + int(body_rx * random.uniform(0.15, 0.45))
        head_cy = body_cy - body_ry - neck_len - int(head_r * 0.1)

    # --- tail: thick, curved ---
    tail_len = int(zone_w * random.uniform(0.08, 0.18))
    tail_w = max(line_w + 3, int(body_rx * 0.25))
    tail_x0 = bcx - body_rx + int(body_rx * 0.15)
    tail_y0 = body_cy + int(body_ry * random.uniform(0.0, 0.3))
    tail_ctrl = (tail_x0 - tail_len * 0.5, tail_y0 + tail_len * random.uniform(0.3, 0.7))
    tail_end = (tail_x0 - tail_len, tail_y0 + int(tail_len * random.uniform(-0.1, 0.3)))
    tail_pts = _bezier_pts((tail_x0, tail_y0), tail_ctrl, tail_end, steps=10)
    for i in range(len(tail_pts) - 1):
        w = max(tail_w - i * 2, line_w)
        draw.line([tail_pts[i], tail_pts[i + 1]], fill=primary, width=w)

    # --- legs: short, thick (cartoon) ---
    leg_h = int(zone_h * random.uniform(0.08, 0.15))
    leg_w = max(line_w + 3, int(body_rx * 0.22))
    foot_r = max(leg_w, 6)
    for x_off in (-0.3 + random.uniform(-0.08, 0.08), 0.3 + random.uniform(-0.08, 0.08)):
        lx = bcx + int(body_rx * x_off)
        ly = body_cy + body_ry
        _draw_organic_leg(draw, lx, ly, lx + random.randint(-3, 3), ly + leg_h,
                         leg_w, primary, foot_r)

    # --- small arms ---
    arm_len = int(body_rx * random.uniform(0.20, 0.40))
    arm_w = max(line_w + 1, int(body_rx * 0.12))
    arm_x = bcx + int(body_rx * random.uniform(0.5, 0.8))
    arm_y = body_cy - int(body_ry * random.uniform(0.0, 0.2))
    hand_x = arm_x + int(arm_len * random.uniform(0.3, 0.6))
    hand_y = arm_y + int(arm_len * random.uniform(0.5, 0.9))
    _draw_organic_limb(draw, arm_x, arm_y, hand_x, hand_y, arm_w, primary)

    # --- body silhouette (organic blob) ---
    body_pts = _draw_filled_blob(draw, bcx, body_cy, body_rx, body_ry,
                                  secondary, primary, line_w, wobble=0.06)

    # --- back spikes ---
    spike_tier = random.choice(["none", "few", "many"])
    if spike_tier != "none":
        n_spikes = random.randint(2, 4) if spike_tier == "few" else random.randint(5, 8)
        spike_size = random.choice(["small", "large"])
        for i in range(n_spikes):
            t = -0.5 + i * (1.0 / max(n_spikes - 1, 1))
            sx = bcx + int(body_rx * t * 0.8)
            sy = body_cy - body_ry + int(abs(t) * body_ry * 0.15)
            sh = random.randint(int(body_ry * 0.08), int(body_ry * 0.15)) if spike_size == "small" \
                else random.randint(int(body_ry * 0.18), int(body_ry * 0.30))
            sw = max(3, int(body_rx * random.uniform(0.03, 0.06)))
            draw.polygon([(sx, sy - sh), (sx - sw, sy + 1), (sx + sw, sy + 1)], fill=primary)

    # --- neck connection (organic curve) ---
    if neck_len > 0:
        neck_base = (bcx + int(body_rx * 0.3), body_cy - body_ry + int(body_ry * 0.1))
        neck_top = (head_cx - int(head_r * 0.2), head_cy + int(head_r * 0.5))
        neck_ctrl = ((neck_base[0] + neck_top[0]) / 2 + random.randint(-5, 5),
                     (neck_base[1] + neck_top[1]) / 2 + random.randint(-8, 0))
        neck_pts = _bezier_pts(neck_base, neck_ctrl, neck_top, steps=8)
        neck_w = max(line_w + 2, int(head_r * 0.4))
        _draw_thick_curve(draw, neck_pts, neck_w, primary)
        # fill neck with secondary to connect body/head
        draws_fill = neck_w + 2
        for p in neck_pts[1:-1]:
            draw.ellipse([p[0] - draws_fill // 2, p[1] - draws_fill // 2,
                          p[0] + draws_fill // 2, p[1] + draws_fill // 2], fill=secondary)
        _draw_thick_curve(draw, neck_pts, neck_w, primary)

    # --- head (organic blob) ---
    head_pts = _draw_filled_blob(draw, head_cx, head_cy, head_r, int(head_r * 0.9),
                                  secondary, primary, line_w, wobble=0.05)

    # --- face ---
    look_dir = random.choice([-1, 0, 1])
    eye_r = max(int(head_r * random.uniform(0.22, 0.35)), 5)
    eye_y = head_cy - int(head_r * random.uniform(0.05, 0.20))
    eye_spread = head_r * random.uniform(0.25, 0.45)
    eye_style = random.choice(["normal", "cute", "sleepy"])
    _draw_expressive_eyes(draw,
                          [(head_cx - eye_spread, eye_y), (head_cx + eye_spread, eye_y)],
                          eye_r, primary, secondary, line_w,
                          style=eye_style, look_dir=look_dir)

    mouth_style = random.choice(["smile", "grin", "open", "confused"])
    mouth_y = head_cy + int(head_r * random.uniform(0.30, 0.50))
    mouth_w = max(int(head_r * random.uniform(0.40, 0.70)), 8)
    _draw_mouth(draw, head_cx, mouth_y, mouth_w, primary, secondary, line_w, style=mouth_style)

    # spots/scales detail
    if random.random() < 0.4:
        for _ in range(random.randint(2, 5)):
            dx = bcx + random.randint(int(-body_rx * 0.6), int(body_rx * 0.6))
            dy = body_cy + random.randint(int(-body_ry * 0.5), int(body_ry * 0.5))
            dr = random.randint(2, max(int(body_rx * 0.06), 3))
            draw.ellipse([dx - dr, dy - dr, dx + dr, dy + dr], fill=primary)


def _draw_spider_archetype(draw, cx, cy, zone_w, zone_h, primary, secondary, line_w):
    """Spider: rounded body, segmented curved legs with joints, big clustered eyes."""
    # --- body proportions ---
    body_tier = random.choice(["small", "medium", "large"])
    if body_tier == "small":
        abd_rx = int(zone_w * random.uniform(0.05, 0.07))
        abd_ry = int(zone_h * random.uniform(0.06, 0.08))
    elif body_tier == "medium":
        abd_rx = int(zone_w * random.uniform(0.08, 0.11))
        abd_ry = int(zone_h * random.uniform(0.09, 0.13))
    else:
        abd_rx = int(zone_w * random.uniform(0.12, 0.16))
        abd_ry = int(zone_h * random.uniform(0.13, 0.18))

    # head size (cartoon=bigger head)
    head_ratio = random.uniform(0.50, 0.80)
    head_r = max(int(min(abd_rx, abd_ry) * head_ratio), 10)
    head_gap = random.uniform(0.10, 0.35)
    head_cy = cy - abd_ry - int(head_r * (1 - head_gap))

    # --- legs: 3-4 pairs, organic curves ---
    num_pairs = random.choice([3, 3, 4, 4])
    leg_thickness = max(line_w + 1, int(abd_rx * 0.10))
    leg_len_tier = random.choice(["short", "medium", "long"])
    if leg_len_tier == "short":
        seg1 = int(zone_w * random.uniform(0.07, 0.11))
        seg2 = int(zone_w * random.uniform(0.05, 0.08))
    elif leg_len_tier == "medium":
        seg1 = int(zone_w * random.uniform(0.12, 0.17))
        seg2 = int(zone_w * random.uniform(0.08, 0.12))
    else:
        seg1 = int(zone_w * random.uniform(0.18, 0.25))
        seg2 = int(zone_w * random.uniform(0.12, 0.18))

    spread_angles = [0.4, 0.15, -0.10, -0.35][:num_pairs]
    for i in range(num_pairs):
        for side in (-1, 1):
            jit = random.uniform(-0.06, 0.06)
            ax = cx + side * abd_rx * random.uniform(0.7, 0.9)
            ay = cy - abd_ry * 0.3 + i * (abd_ry * random.uniform(0.35, 0.50))
            s1 = int(seg1 * random.uniform(0.88, 1.12))
            s2 = int(seg2 * random.uniform(0.88, 1.12))
            knee_angle = spread_angles[i] + jit
            knee_x = ax + side * s1 * math.cos(knee_angle)
            knee_y = ay - s1 * math.sin(knee_angle) * 0.5
            foot_angle = knee_angle - random.uniform(0.3, 0.6)
            foot_x = knee_x + side * s2 * math.cos(foot_angle)
            foot_y = knee_y + s2 * math.sin(abs(foot_angle) + 0.3)
            # organic curved segments
            ctrl1 = (ax + side * s1 * 0.3, ay - random.uniform(2, 8))
            pts1 = _bezier_pts((ax, ay), ctrl1, (knee_x, knee_y), steps=6)
            _draw_thick_curve(draw, pts1, leg_thickness, primary)
            ctrl2 = (knee_x + side * s2 * 0.3, knee_y + random.uniform(2, 8))
            pts2 = _bezier_pts((knee_x, knee_y), ctrl2, (foot_x, foot_y), steps=6)
            w2 = max(leg_thickness - 1, 2)
            _draw_thick_curve(draw, pts2, w2, primary)
            # joint dot
            jr = max(leg_thickness - 1, 2)
            draw.ellipse([knee_x - jr, knee_y - jr, knee_x + jr, knee_y + jr], fill=primary)

    # --- body silhouette ---
    _draw_filled_blob(draw, cx, cy, abd_rx, abd_ry, secondary, primary, line_w, wobble=0.06)

    # head
    _draw_filled_blob(draw, cx, head_cy, head_r, int(head_r * 0.95),
                       secondary, primary, line_w, wobble=0.05)

    # --- eyes: 2, 4, 6, 8 clustered ---
    num_eyes = random.choice([2, 2, 4, 6, 8])
    eye_r = max(int(head_r * random.uniform(0.18, 0.32)), 4)
    sp_x = head_r * random.uniform(0.25, 0.50)
    sp_y = head_r * random.uniform(0.15, 0.30)
    if num_eyes == 2:
        positions = [(cx - sp_x, head_cy), (cx + sp_x, head_cy)]
    elif num_eyes == 4:
        positions = [(cx - sp_x, head_cy - sp_y), (cx + sp_x, head_cy - sp_y),
                     (cx - sp_x * 0.6, head_cy + sp_y), (cx + sp_x * 0.6, head_cy + sp_y)]
    elif num_eyes == 6:
        positions = [(cx - sp_x, head_cy - sp_y), (cx + sp_x, head_cy - sp_y),
                     (cx - sp_x * 0.7, head_cy), (cx + sp_x * 0.7, head_cy),
                     (cx - sp_x * 0.4, head_cy + sp_y), (cx + sp_x * 0.4, head_cy + sp_y)]
    else:
        positions = [(cx - sp_x, head_cy - sp_y), (cx + sp_x, head_cy - sp_y),
                     (cx - sp_x * 0.8, head_cy - sp_y * 0.3), (cx + sp_x * 0.8, head_cy - sp_y * 0.3),
                     (cx - sp_x * 0.6, head_cy + sp_y * 0.3), (cx + sp_x * 0.6, head_cy + sp_y * 0.3),
                     (cx - sp_x * 0.35, head_cy + sp_y), (cx + sp_x * 0.35, head_cy + sp_y)]
    _draw_expressive_eyes(draw, positions, eye_r, primary, secondary, line_w,
                          style=random.choice(["normal", "cute"]))

    # mandibles / smile
    m_y = head_cy + head_r - 2
    mouth_style = random.choice(["smile", "open", "confused"])
    _draw_mouth(draw, cx, m_y, max(int(head_r * 0.5), 6), primary, secondary, line_w,
                style=mouth_style)


def _draw_werewolf_archetype(draw, cx, cy, zone_w, zone_h, primary, secondary, line_w):
    """Werewolf: upright body, fur edges, pointed ears, claws, toothy grin."""
    # --- pose ---
    lean = random.uniform(-0.02, 0.02) * zone_w
    bcx = cx + int(lean)

    # --- body (large torso, cartoon) ---
    build = random.choice(["lean", "stocky", "hulking"])
    if build == "lean":
        body_hw = int(zone_w * random.uniform(0.08, 0.12))
        body_hh = int(zone_h * random.uniform(0.20, 0.26))
    elif build == "stocky":
        body_hw = int(zone_w * random.uniform(0.12, 0.16))
        body_hh = int(zone_h * random.uniform(0.16, 0.22))
    else:
        body_hw = int(zone_w * random.uniform(0.14, 0.20))
        body_hh = int(zone_h * random.uniform(0.20, 0.28))

    body_cy = cy + int(zone_h * 0.02)

    # --- legs (thick, short — cartoon proportions) ---
    leg_h = int(zone_h * random.uniform(0.08, 0.16))
    leg_w = max(line_w + 3, int(body_hw * 0.28))
    foot_r = max(leg_w + 1, 7)
    for x_off in (-0.28 + random.uniform(-0.06, 0.06), 0.28 + random.uniform(-0.06, 0.06)):
        lx = bcx + int(body_hw * x_off)
        ly = body_cy + body_hh
        _draw_organic_leg(draw, lx, ly, lx + random.randint(-4, 4), ly + leg_h,
                         leg_w, primary, foot_r)

    # --- arms (thick, with claws) ---
    arm_w = max(line_w + 2, int(body_hw * 0.18))
    arm_len = int(body_hw * random.uniform(0.50, 0.90))
    arm_pose = random.choice(["neutral", "raised", "lowered"])
    claw_count = random.choice([2, 3, 4])
    for side_name, side in (("left", -1), ("right", 1)):
        ax = bcx + side * body_hw
        ay = body_cy - int(body_hh * random.uniform(0.05, 0.20))
        if arm_pose == "raised":
            hand_x = ax + side * arm_len * random.uniform(0.7, 1.0)
            hand_y = ay - arm_len * random.uniform(0.3, 0.6)
        elif arm_pose == "lowered":
            hand_x = ax + side * arm_len * random.uniform(0.6, 0.9)
            hand_y = ay + arm_len * random.uniform(0.4, 0.7)
        else:
            hand_x = ax + side * arm_len * random.uniform(0.6, 0.9)
            hand_y = ay + arm_len * random.uniform(0.1, 0.3)
        _draw_organic_limb(draw, ax, ay, hand_x, hand_y, arm_w, primary, taper=0.6)
        # claws
        claw_len = max(arm_len // 4, 5)
        angle = math.atan2(hand_y - ay, hand_x - ax)
        spread = math.pi * 0.4
        for ci in range(claw_count):
            a = angle - spread / 2 + (spread / max(claw_count - 1, 1)) * ci
            tx = hand_x + claw_len * math.cos(a)
            ty = hand_y + claw_len * math.sin(a)
            draw.line([(hand_x, hand_y), (tx, ty)], fill=primary, width=max(line_w, 2))

    # --- body silhouette ---
    body_pts = _draw_filled_blob(draw, bcx, body_cy, body_hw, body_hh,
                                  secondary, primary, line_w, wobble=0.07)

    # --- fur tufts along body edge ---
    _draw_fur_edge(draw, body_pts, (int(body_hw * 0.04), int(body_hw * 0.14)),
                   primary, line_w)

    # --- ears (pointed, triangular) ---
    ear_h = max(int(body_hh * random.uniform(0.12, 0.22)), 12)
    ear_w = max(int(body_hw * random.uniform(0.10, 0.16)), 8)
    for direction in (-1, 1):
        ex = bcx + direction * int(body_hw * random.uniform(0.25, 0.40))
        ey = body_cy - body_hh
        tilt = random.randint(-int(ear_w * 0.2), int(ear_w * 0.2))
        pts = [(ex + tilt, ey - ear_h),
               (ex - direction * ear_w, ey + line_w),
               (ex + direction * (ear_w // 3), ey + line_w)]
        draw.polygon(pts, fill=secondary, outline=primary, width=line_w)

    # --- face ---
    eye_r = max(int(min(body_hw, body_hh) * random.uniform(0.09, 0.14)), 5)
    eye_y = body_cy - int(body_hh * random.uniform(0.22, 0.35))
    eye_spread = body_hw * random.uniform(0.30, 0.50)
    eye_style = random.choice(["angry", "normal"])
    _draw_expressive_eyes(draw,
                          [(bcx - eye_spread, eye_y), (bcx + eye_spread, eye_y)],
                          eye_r, primary, secondary, line_w,
                          style=eye_style)

    # toothy grin
    mouth_y = body_cy + int(body_hh * random.uniform(0.05, 0.18))
    mouth_w = max(int(body_hw * random.uniform(0.30, 0.50)), 10)
    _draw_mouth(draw, bcx, mouth_y, mouth_w, primary, secondary, line_w, style="grin")


def _draw_zombie_archetype(draw, cx, cy, zone_w, zone_h, primary, secondary, line_w):
    """Zombie: loose posture, slightly bent limbs, uneven face, stitches."""
    # --- posture: tilted ---
    tilt = random.uniform(-0.04, 0.04) * zone_w
    bcx = cx + int(tilt)
    body_lean = random.uniform(-0.03, 0.03) * zone_h

    # --- body ---
    body_tier = random.choice(["thin", "normal", "wide"])
    if body_tier == "thin":
        body_hw = int(zone_w * random.uniform(0.08, 0.11))
        body_hh = int(zone_h * random.uniform(0.20, 0.26))
    elif body_tier == "normal":
        body_hw = int(zone_w * random.uniform(0.11, 0.15))
        body_hh = int(zone_h * random.uniform(0.17, 0.23))
    else:
        body_hw = int(zone_w * random.uniform(0.14, 0.18))
        body_hh = int(zone_h * random.uniform(0.15, 0.21))

    body_cy = cy + int(body_lean)

    # --- arms (bent, hanging, one sometimes missing) ---
    arm_w = max(line_w + 2, int(body_hw * 0.16))
    arm_len = int(body_hw * random.uniform(0.55, 0.95))
    has_both = random.random() < 0.80
    arm_sides = [("left", -1), ("right", 1)]
    if not has_both:
        arm_sides = [arm_sides[random.randint(0, 1)]]
    for side_name, side in arm_sides:
        ax = bcx + side * body_hw
        ay = body_cy - int(body_hh * random.uniform(0.0, 0.15))
        # slouching bent arms
        elbow_x = ax + side * arm_len * random.uniform(0.3, 0.6)
        elbow_y = ay + arm_len * random.uniform(0.2, 0.5)
        hand_x = elbow_x + side * arm_len * random.uniform(0.2, 0.5)
        hand_y = elbow_y + arm_len * random.uniform(0.3, 0.7)
        _draw_organic_limb(draw, ax, ay, elbow_x, elbow_y, arm_w, primary, taper=0.85)
        _draw_organic_limb(draw, elbow_x, elbow_y, hand_x, hand_y,
                          max(arm_w - 1, 2), primary, taper=0.7)

    # --- legs (uneven, bent) ---
    leg_w = max(line_w + 2, int(body_hw * 0.22))
    leg_h = int(zone_h * random.uniform(0.10, 0.18))
    foot_r = max(leg_w + 1, 6)
    asym = random.uniform(0.05, 0.15) * leg_h
    for idx, x_off in enumerate((-0.25, 0.25)):
        lx = bcx + int(body_hw * x_off) + random.randint(-3, 3)
        ly = body_cy + body_hh
        h = leg_h + int(asym if idx == 0 else -asym)
        fx = lx + random.randint(-4, 4)
        _draw_organic_leg(draw, lx, ly, fx, ly + h, leg_w, primary, foot_r)

    # --- body silhouette ---
    body_pts = _draw_filled_blob(draw, bcx, body_cy, body_hw, body_hh,
                                  secondary, primary, line_w, wobble=0.09)

    # --- stitches ---
    num_stitches = random.randint(1, 5)
    _draw_stitches(draw, bcx, body_cy, body_hw, body_hh, num_stitches, primary, line_w)

    # --- face (asymmetric) ---
    left_eye_r = max(int(min(body_hw, body_hh) * random.uniform(0.09, 0.15)), 5)
    right_eye_r = max(int(left_eye_r * random.uniform(0.50, 0.90)), 4)
    eye_y = body_cy - int(body_hh * random.uniform(0.20, 0.30))
    eye_spread = body_hw * random.uniform(0.28, 0.45)

    # one eye might be X (dead)
    dead_eye = random.random() < 0.30
    for idx, (ex, ey_off, er) in enumerate([
        (bcx - eye_spread, random.randint(-2, 2), left_eye_r),
        (bcx + eye_spread, random.randint(0, 3), right_eye_r),
    ]):
        ey = eye_y + ey_off
        eye_pts = _organic_blob(ex, ey, er, er, wobble=0.05)
        draw.polygon(eye_pts, fill=secondary, outline=primary, width=line_w)
        if dead_eye and idx == 1:
            cr = max(er - 2, 2)
            draw.line([(ex - cr, ey - cr), (ex + cr, ey + cr)], fill=primary, width=line_w)
            draw.line([(ex + cr, ey - cr), (ex - cr, ey + cr)], fill=primary, width=line_w)
        else:
            pr = max(er // 3, 2)
            draw.ellipse([ex - pr, ey - pr, ex + pr, ey + pr], fill=primary)

    # mouth (crooked line + missing teeth)
    mouth_y = body_cy + int(body_hh * random.uniform(0.10, 0.22))
    mouth_w = max(int(body_hw * random.uniform(0.25, 0.45)), 8)
    mouth_pts = _bezier_pts((bcx - mouth_w, mouth_y + random.randint(-3, 3)),
                             (bcx, mouth_y + random.randint(-4, 4)),
                             (bcx + mouth_w, mouth_y + random.randint(-3, 3)), steps=8)
    _draw_thick_curve(draw, mouth_pts, line_w, primary)
    # teeth
    n_teeth = random.randint(2, 5)
    tw = max(mouth_w * 2 // (n_teeth + 1), 3)
    th = max(tw, 3)
    total = n_teeth * tw + (n_teeth - 1) * 2
    sx = bcx - total // 2
    for i in range(n_teeth):
        if random.random() < 0.35:
            continue
        tx = sx + i * (tw + 2)
        draw.polygon([(tx, mouth_y), (tx + tw, mouth_y), (tx + tw // 2, mouth_y + th)],
                     fill=secondary, outline=primary, width=max(line_w - 1, 1))

    # cracks/damage detail
    if random.random() < 0.5:
        for _ in range(random.randint(1, 3)):
            crack_x = bcx + random.randint(int(-body_hw * 0.4), int(body_hw * 0.4))
            crack_y = body_cy + random.randint(int(-body_hh * 0.3), int(body_hh * 0.3))
            crack_len = random.randint(4, max(int(body_hw * 0.12), 6))
            angle = random.uniform(-0.8, 0.8)
            draw.line([(crack_x, crack_y),
                       (crack_x + crack_len * math.cos(angle),
                        crack_y + crack_len * math.sin(angle))],
                      fill=primary, width=max(line_w - 1, 1))


def _draw_octopus_archetype(draw, cx, cy, zone_w, zone_h, primary, secondary, line_w):
    """Octopus: round head/dome, thick curling tentacles, soft curves."""
    # --- dome ---
    dome_tier = random.choice(["small", "medium", "large"])
    if dome_tier == "small":
        dome_rx = int(zone_w * random.uniform(0.09, 0.13))
        dome_ry = int(zone_h * random.uniform(0.09, 0.13))
    elif dome_tier == "medium":
        dome_rx = int(zone_w * random.uniform(0.13, 0.18))
        dome_ry = int(zone_h * random.uniform(0.12, 0.17))
    else:
        dome_rx = int(zone_w * random.uniform(0.18, 0.24))
        dome_ry = int(zone_h * random.uniform(0.16, 0.22))

    dome_shape = random.choice(["round", "wide"])
    if dome_shape == "wide":
        dome_rx = int(dome_rx * 1.2)
        dome_ry = int(dome_ry * 0.85)

    dome_cy = cy - int(zone_h * random.uniform(0.04, 0.10))

    # --- tentacles: thick, curling ---
    n_tentacles = random.randint(4, 8)
    tent_w = max(line_w + 2, int(dome_rx * 0.15))
    tent_len_tier = random.choice(["short", "medium", "long"])
    tent_spread = dome_rx * random.uniform(1.2, 1.8)
    tent_step = tent_spread / max(n_tentacles - 1, 1)
    tent_start_y = dome_cy + dome_ry - line_w

    for i in range(n_tentacles):
        tx = cx - tent_spread / 2 + i * tent_step + random.uniform(-4, 4)
        if tent_len_tier == "short":
            length = int(zone_h * random.uniform(0.12, 0.20))
        elif tent_len_tier == "medium":
            length = int(zone_h * random.uniform(0.22, 0.34))
        else:
            length = int(zone_h * random.uniform(0.35, 0.48))
        # organic curving tentacle
        sway = dome_rx * random.uniform(0.08, 0.22)
        pts = [(tx, tent_start_y)]
        segs = random.randint(4, 6)
        seg_len = length / segs
        for j in range(segs):
            d = 1 if j % 2 == 0 else -1
            nx = pts[-1][0] + random.uniform(sway * 0.3, sway) * d
            ny = pts[-1][1] + seg_len
            pts.append((nx, ny))
        for j in range(len(pts) - 1):
            w = max(tent_w - j, 2)
            draw.line([pts[j], pts[j + 1]], fill=primary, width=w)
        # tip dot
        r = max(2, tent_w // 2)
        draw.ellipse([pts[-1][0] - r, pts[-1][1] - r, pts[-1][0] + r, pts[-1][1] + r], fill=primary)

    # --- dome silhouette (organic) ---
    _draw_filled_blob(draw, cx, dome_cy, dome_rx, dome_ry,
                       secondary, primary, line_w, wobble=0.05)

    # --- face ---
    eye_r = max(int(dome_rx * random.uniform(0.14, 0.25)), 5)
    eye_y = dome_cy - int(dome_ry * random.uniform(0.02, 0.18))
    spread = dome_rx * random.uniform(0.30, 0.55)
    n_eyes = random.choice([2, 2, 3])
    if n_eyes == 2:
        positions = [(cx - spread, eye_y), (cx + spread, eye_y)]
    else:
        positions = [(cx - spread, eye_y), (cx, eye_y - int(eye_r * 0.3)), (cx + spread, eye_y)]
    eye_style = random.choice(["normal", "cute", "sleepy"])
    _draw_expressive_eyes(draw, positions, eye_r, primary, secondary, line_w, style=eye_style)

    mouth_y = dome_cy + int(dome_ry * random.uniform(0.25, 0.45))
    mouth_style = random.choice(["smile", "open", "confused"])
    _draw_mouth(draw, cx, mouth_y, max(int(dome_rx * 0.3), 6), primary, secondary, line_w,
                style=mouth_style)

    # spots detail
    if random.random() < 0.35:
        for _ in range(random.randint(2, 5)):
            dx = cx + random.randint(int(-dome_rx * 0.5), int(dome_rx * 0.5))
            dy = dome_cy + random.randint(int(-dome_ry * 0.4), int(dome_ry * 0.4))
            dr = random.randint(2, max(int(dome_rx * 0.06), 3))
            draw.ellipse([dx - dr, dy - dr, dx + dr, dy + dr], fill=primary)


def _draw_dragon_archetype(draw, cx, cy, zone_w, zone_h, primary, secondary, line_w):
    """Dragon: curved body, simple membrane wings, tail, spikes, expressive face."""
    lean = random.uniform(-0.02, 0.02) * zone_w
    bcx = cx + int(lean)

    # --- body ---
    body_tier = random.choice(["compact", "wide", "tall"])
    if body_tier == "compact":
        body_hw = int(zone_w * random.uniform(0.10, 0.14))
        body_hh = int(zone_h * random.uniform(0.13, 0.18))
    elif body_tier == "wide":
        body_hw = int(zone_w * random.uniform(0.14, 0.20))
        body_hh = int(zone_h * random.uniform(0.12, 0.16))
    else:
        body_hw = int(zone_w * random.uniform(0.10, 0.14))
        body_hh = int(zone_h * random.uniform(0.18, 0.25))

    body_cy = cy + int(zone_h * 0.02)

    # --- wings (membrane with curves) ---
    wing_tier = random.choice(["none", "small", "large", "large"])
    if wing_tier != "none":
        if wing_tier == "small":
            wing_w = int(zone_w * random.uniform(0.07, 0.12))
            wing_h = int(zone_h * random.uniform(0.10, 0.16))
        else:
            wing_w = int(zone_w * random.uniform(0.14, 0.22))
            wing_h = int(zone_h * random.uniform(0.18, 0.30))
        for side in (-1, 1):
            wx = bcx + side * body_hw
            wy = body_cy - int(body_hh * random.uniform(0.2, 0.4))
            tip = (wx + side * wing_w, wy - wing_h)
            bot = (wx + side * int(wing_w * 0.3), wy + int(wing_h * 0.15))
            # membrane with curved edge
            curve_pts = _bezier_pts((wx, wy), tip, bot, steps=10)
            # fill wing
            wing_poly = [(wx, wy)] + curve_pts + [bot]
            draw.polygon(wing_poly, fill=secondary, outline=primary, width=line_w)
            # membrane ribs
            n_ribs = random.randint(1, 3)
            for ri in range(n_ribs):
                t = (ri + 1) / (n_ribs + 1)
                rib_end = curve_pts[int(t * (len(curve_pts) - 1))]
                draw.line([(wx, wy), rib_end], fill=primary, width=max(line_w - 1, 1))

    # --- tail (curved) ---
    tail_len = int(zone_w * random.uniform(0.08, 0.20))
    tail_w = max(line_w + 2, int(body_hw * 0.18))
    tail_side = random.choice([-1, 1])
    tail_x0 = bcx + tail_side * body_hw
    tail_y0 = body_cy + int(body_hh * random.uniform(0.2, 0.5))
    tail_ctrl = (tail_x0 + tail_side * tail_len * 0.5,
                 tail_y0 + tail_len * random.uniform(0.2, 0.5))
    tail_end = (tail_x0 + tail_side * tail_len,
                tail_y0 + int(tail_len * random.uniform(-0.1, 0.2)))
    tail_pts = _bezier_pts((tail_x0, tail_y0), tail_ctrl, tail_end, steps=10)
    for i in range(len(tail_pts) - 1):
        w = max(tail_w - i, line_w)
        draw.line([tail_pts[i], tail_pts[i + 1]], fill=primary, width=w)
    # tail tip
    tip_style = random.choice(["arrow", "round", "none"])
    ex, ey = tail_pts[-1]
    if tip_style == "arrow":
        tw = max(int(tail_len * 0.08), 3)
        draw.polygon([(ex, ey - tw), (ex + tail_side * tw * 2, ey), (ex, ey + tw)], fill=primary)
    elif tip_style == "round":
        tr = max(int(tail_len * 0.05), 3)
        draw.ellipse([ex - tr, ey - tr, ex + tr, ey + tr], fill=primary)

    # --- legs ---
    leg_h = int(zone_h * random.uniform(0.08, 0.15))
    leg_w = max(line_w + 2, int(body_hw * 0.20))
    foot_r = max(leg_w, 5)
    n_legs = random.choice([2, 2, 4])
    if n_legs == 2:
        leg_xs = [-0.20, 0.20]
    else:
        leg_xs = [-0.32, -0.10, 0.10, 0.32]
    for x_off in leg_xs:
        lx = bcx + int(body_hw * x_off) + random.randint(-2, 2)
        ly = body_cy + body_hh
        _draw_organic_leg(draw, lx, ly, lx + random.randint(-3, 3), ly + leg_h,
                         leg_w, primary, foot_r)

    # --- body silhouette ---
    body_pts = _draw_filled_blob(draw, bcx, body_cy, body_hw, body_hh,
                                  secondary, primary, line_w, wobble=0.06)

    # --- spikes on back ---
    spike_tier = random.choice(["none", "few", "many"])
    if spike_tier != "none":
        n_sp = random.randint(2, 4) if spike_tier == "few" else random.randint(5, 8)
        for i in range(n_sp):
            t = -0.4 + i * (0.8 / max(n_sp - 1, 1))
            sx = bcx + int(body_hw * t)
            sy = body_cy - body_hh + int(abs(t) * body_hh * 0.12)
            sh = random.randint(int(body_hh * 0.08), int(body_hh * 0.25))
            sw = max(3, int(body_hw * 0.04))
            draw.polygon([(sx, sy - sh), (sx - sw, sy + 1), (sx + sw, sy + 1)], fill=primary)

    # --- horns ---
    horn_h = int(body_hh * random.uniform(0.15, 0.40))
    horn_w = max(int(body_hw * 0.05), 4)
    for x_r in (-0.22, 0.22):
        hx = bcx + int(body_hw * x_r) + random.randint(-3, 3)
        hy = body_cy - body_hh
        d = random.choice([-1, 1])
        draw.polygon([(hx + d * horn_w, hy - horn_h), (hx - horn_w, hy + 2), (hx + horn_w, hy + 2)],
                     fill=primary)

    # --- face ---
    eye_r = max(int(min(body_hw, body_hh) * random.uniform(0.10, 0.16)), 5)
    eye_y = body_cy - int(body_hh * random.uniform(0.18, 0.32))
    eye_spread = body_hw * random.uniform(0.30, 0.50)
    eye_style = random.choice(["normal", "angry", "cute"])
    _draw_expressive_eyes(draw,
                          [(bcx - eye_spread, eye_y), (bcx + eye_spread, eye_y)],
                          eye_r, primary, secondary, line_w, style=eye_style)

    mouth_y = body_cy + int(body_hh * random.uniform(0.12, 0.28))
    mouth_w = max(int(body_hw * random.uniform(0.30, 0.50)), 8)
    mouth_style = random.choice(["grin", "teeth", "smile"])
    _draw_mouth(draw, bcx, mouth_y, mouth_w, primary, secondary, line_w, style=mouth_style)


def _draw_cthulhu_archetype(draw, cx, cy, zone_w, zone_h, primary, secondary, line_w):
    """Cthulhu: large head, tentacles from mouth, soft flowing shapes, compact body."""
    # --- head (oversized, cartoon) ---
    head_tier = random.choice(["large", "very_large"])
    if head_tier == "large":
        head_rx = int(zone_w * random.uniform(0.13, 0.18))
        head_ry = int(zone_h * random.uniform(0.15, 0.20))
    else:
        head_rx = int(zone_w * random.uniform(0.19, 0.24))
        head_ry = int(zone_h * random.uniform(0.21, 0.28))
    head_cy = cy - int(zone_h * random.uniform(0.04, 0.10))

    # --- body (compact, beneath head) ---
    body_hw = int(head_rx * random.uniform(0.40, 0.65))
    body_hh = int(head_ry * random.uniform(0.40, 0.60))
    body_cy = head_cy + head_ry + body_hh - int(body_hh * random.uniform(0.10, 0.25))

    # --- wings (small, optional) ---
    if random.random() < 0.55:
        wing_w = int(zone_w * random.uniform(0.05, 0.12))
        wing_h = int(zone_h * random.uniform(0.08, 0.16))
        for side in (-1, 1):
            wx = cx + side * body_hw
            wy = body_cy - int(body_hh * random.uniform(0.1, 0.3))
            tip = (wx + side * wing_w, wy - wing_h)
            bot = (wx + side * int(wing_w * 0.25), wy + int(wing_h * 0.15))
            draw.polygon([(wx, wy), tip, bot], fill=secondary, outline=primary, width=line_w)

    # --- small arms ---
    arm_w = max(line_w + 1, int(body_hw * 0.15))
    arm_len = int(body_hw * random.uniform(0.45, 0.80))
    for side in (-1, 1):
        ax = cx + side * body_hw
        ay = body_cy
        hand_x = ax + side * arm_len * random.uniform(0.7, 1.1)
        hand_y = ay + arm_len * random.uniform(0.3, 0.6)
        _draw_organic_limb(draw, ax, ay, hand_x, hand_y, arm_w, primary)

    # --- body silhouette ---
    _draw_filled_blob(draw, cx, body_cy, body_hw, body_hh,
                       secondary, primary, line_w, wobble=0.06)

    # --- head silhouette (organic, large) ---
    _draw_filled_blob(draw, cx, head_cy, head_rx, head_ry,
                       secondary, primary, line_w, wobble=0.07)

    # --- horns ---
    horn_h = int(head_ry * random.uniform(0.18, 0.38))
    horn_w = max(int(head_rx * 0.05), 3)
    for x_off in (-0.25, 0.25):
        hx = cx + int(head_rx * x_off) + random.randint(-3, 3)
        hy = head_cy - head_ry
        draw.polygon([(hx, hy - horn_h), (hx - horn_w, hy + 2), (hx + horn_w, hy + 2)], fill=primary)

    # --- face ---
    eye_r = max(int(head_rx * random.uniform(0.10, 0.17)), 5)
    eye_y = head_cy - int(head_ry * random.uniform(0.08, 0.25))
    eye_spread = head_rx * random.uniform(0.30, 0.50)
    n_eyes = random.choice([2, 2, 3, 4])
    if n_eyes == 2:
        positions = [(cx - eye_spread, eye_y), (cx + eye_spread, eye_y)]
    elif n_eyes == 3:
        positions = [(cx - eye_spread, eye_y), (cx, eye_y - int(eye_r * 0.4)), (cx + eye_spread, eye_y)]
    else:
        positions = [(cx - eye_spread, eye_y - int(eye_r * 0.2)),
                     (cx + eye_spread, eye_y - int(eye_r * 0.2)),
                     (cx - eye_spread * 0.5, eye_y + int(eye_r * 0.3)),
                     (cx + eye_spread * 0.5, eye_y + int(eye_r * 0.3))]
    _draw_expressive_eyes(draw, positions, eye_r, primary, secondary, line_w,
                          style=random.choice(["normal", "angry", "sleepy"]))

    # --- mouth tentacles ---
    tent_total = random.randint(3, 7)
    tent_spread = head_rx * random.uniform(0.6, 1.0)
    tent_step = tent_spread / max(tent_total - 1, 1)
    tent_start_y = head_cy + int(head_ry * random.uniform(0.35, 0.55))
    tent_w = max(line_w + 1, int(head_rx * 0.06))
    tent_len_tier = random.choice(["short", "long"])
    for i in range(tent_total):
        tx = cx - tent_spread / 2 + i * tent_step + random.uniform(-2, 2)
        if tent_len_tier == "short":
            length = int(head_ry * random.uniform(0.25, 0.45))
        else:
            length = int(head_ry * random.uniform(0.50, 0.85))
        sway = head_rx * random.uniform(0.05, 0.15)
        _curvy_tentacle(draw, tx, tent_start_y, length, sway, tent_w, primary)


def _draw_ghost_archetype(draw, cx, cy, zone_w, zone_h, primary, secondary, line_w):
    """Ghost: soft rounded top, wavy bottom, floating shape, simple expressive face."""
    # --- size ---
    size_tier = random.choice(["small", "medium", "large"])
    if size_tier == "small":
        body_w = int(zone_w * random.uniform(0.18, 0.24))
        body_h = int(zone_h * random.uniform(0.40, 0.50))
    elif size_tier == "medium":
        body_w = int(zone_w * random.uniform(0.24, 0.32))
        body_h = int(zone_h * random.uniform(0.50, 0.65))
    else:
        body_w = int(zone_w * random.uniform(0.30, 0.38))
        body_h = int(zone_h * random.uniform(0.58, 0.72))

    # --- ghost outline (dome top, wavy bottom) ---
    ghost_pts = _ghost_outline_points(cx, cy, body_w, body_h)
    body_geo = _build_body_geometry(cx, cy, body_w, body_h, "ghost")

    # --- arms (organic curves) ---
    arm_style = random.choice(["none", "stubs", "reaching", "one_only"])
    if arm_style != "none":
        arm_w = max(line_w + 1, int(body_w * 0.06))
        if arm_style == "stubs":
            arm_len = int(body_w * random.uniform(0.10, 0.18))
        else:
            arm_len = int(body_w * random.uniform(0.20, 0.35))
        sides = [("left", -1), ("right", 1)]
        if arm_style == "one_only":
            sides = [sides[random.randint(0, 1)]]
        for side_name, side in sides:
            y_off = random.uniform(-0.12, 0.05)
            ax, ay = _body_side_anchor(body_geo, side_name, y_off, inset=arm_w)
            hand_x = ax + side * arm_len
            hand_y = ay + arm_len * random.uniform(-0.4, 0.2)
            _draw_organic_limb(draw, ax, ay, hand_x, hand_y, arm_w, primary, taper=0.5)

    # --- body fill ---
    _draw_polygon_body(draw, ghost_pts, secondary, primary, line_w)

    # --- face ---
    n_eyes = random.choices([1, 2, 3], weights=[15, 60, 25])[0]
    eye_r = max(int(min(body_w, body_h) * random.uniform(0.05, 0.10)), 5)
    eye_y = cy - int(body_h * random.uniform(0.10, 0.22))
    hollow = random.random() < 0.55
    if n_eyes == 1:
        positions = [(cx, eye_y)]
    else:
        spread = body_w * random.uniform(0.18, 0.30)
        if n_eyes == 2:
            positions = [(cx - spread, eye_y + random.randint(-2, 2)),
                         (cx + spread, eye_y + random.randint(-2, 2))]
        else:
            positions = [(cx - spread, eye_y + random.randint(-2, 2)),
                         (cx, eye_y - int(eye_r * 0.5)),
                         (cx + spread, eye_y + random.randint(-2, 2))]
    _draw_expressive_eyes(draw, positions, eye_r, primary, secondary, line_w,
                          style="hollow" if hollow else random.choice(["normal", "sleepy", "cute"]))

    # mouth
    mouth_style = random.choice(["open", "confused", "smile", "none"])
    if mouth_style != "none":
        mouth_y = cy + int(body_h * random.uniform(0.03, 0.12))
        _draw_mouth(draw, cx, mouth_y, max(int(body_w * 0.15), 6),
                    primary, secondary, line_w, style=mouth_style)


def _draw_default_archetype(draw, cx, cy, zone_w, zone_h, primary, secondary, line_w):
    """Default: randomized organic creature with various features."""
    lean = random.uniform(-0.02, 0.02) * zone_w
    bcx = cx + int(lean)

    body_hw = int(zone_w * random.uniform(0.10, 0.18))
    body_hh = int(zone_h * random.uniform(0.14, 0.24))

    use_tentacles = random.random() < 0.25
    use_arms = random.random() < 0.75
    use_wings = random.random() < 0.20
    use_tail = random.random() < 0.25
    use_horns = random.random() < 0.30
    n_legs = 0 if use_tentacles else random.choices([2, 3, 4], weights=[60, 20, 20])[0]

    body_cy = cy + int(zone_h * 0.02)

    # wings
    if use_wings:
        wing_w = int(body_hw * random.uniform(0.35, 0.60))
        wing_h = int(body_hh * random.uniform(0.45, 0.70))
        for side in (-1, 1):
            wx = bcx + side * body_hw
            wy = body_cy - int(body_hh * 0.15)
            tip = (wx + side * wing_w, wy - wing_h)
            bot = (wx + side * int(wing_w * 0.3), wy + int(wing_h * 0.12))
            draw.polygon([(wx, wy), tip, bot], fill=secondary, outline=primary, width=line_w)

    # tail
    if use_tail:
        tail_side = random.choice([-1, 1])
        tail_len = int(body_hw * random.uniform(0.40, 0.70))
        tx0 = bcx + tail_side * body_hw
        ty0 = body_cy + int(body_hh * 0.2)
        tail_end = (tx0 + tail_side * tail_len, ty0 + int(body_hh * 0.15))
        tail_ctrl = ((tx0 + tail_end[0]) / 2, ty0 + tail_len * 0.3)
        pts = _bezier_pts((tx0, ty0), tail_ctrl, tail_end, steps=8)
        for i in range(len(pts) - 1):
            w = max(line_w + 1 - i // 3, line_w)
            draw.line([pts[i], pts[i + 1]], fill=primary, width=w)

    # tentacles or legs
    if use_tentacles:
        n_t = random.randint(4, 7)
        tent_w = max(line_w + 2, int(body_hw * 0.10))
        spread = 0.70
        step = spread / max(n_t - 1, 1)
        for i in range(n_t):
            x_r = (-spread / 2) + i * step
            tx = bcx + int(body_hw * x_r)
            ty = body_cy + body_hh
            length = int(body_hh * random.uniform(0.50, 0.85))
            sway = body_hw * 0.12
            _curvy_tentacle(draw, tx, ty, length, sway, tent_w, primary)
    elif n_legs > 0:
        leg_w = max(line_w + 2, int(body_hw * 0.18))
        leg_h = int(zone_h * random.uniform(0.08, 0.16))
        foot_r = max(leg_w + 1, 5)
        spread = 0.50
        step = spread / max(n_legs - 1, 1) if n_legs > 1 else 0
        for i in range(n_legs):
            x_r = (-spread / 2 + i * step) if n_legs > 1 else 0
            lx = bcx + int(body_hw * x_r)
            ly = body_cy + body_hh
            _draw_organic_leg(draw, lx, ly, lx + random.randint(-3, 3), ly + leg_h,
                             leg_w, primary, foot_r)

    # arms
    if use_arms:
        arm_w = max(line_w + 1, int(body_hw * 0.12))
        arm_len = int(body_hw * random.uniform(0.45, 0.75))
        for side in (-1, 1):
            ax = bcx + side * body_hw
            ay = body_cy - int(body_hh * random.uniform(-0.05, 0.10))
            hand_x = ax + side * arm_len * random.uniform(0.7, 1.0)
            hand_y = ay + arm_len * random.uniform(0.1, 0.5)
            _draw_organic_limb(draw, ax, ay, hand_x, hand_y, arm_w, primary)

    # body
    body_pts = _draw_filled_blob(draw, bcx, body_cy, body_hw, body_hh,
                                  secondary, primary, line_w, wobble=0.08)

    # horns
    if use_horns:
        horn_count = random.choice([1, 2])
        horn_h = int(body_hh * random.uniform(0.18, 0.35))
        horn_w = max(int(body_hw * 0.05), 4)
        ratios = [0.0] if horn_count == 1 else [-0.20, 0.20]
        for x_r in ratios:
            hx = bcx + int(body_hw * x_r)
            hy = body_cy - body_hh
            draw.polygon([(hx, hy - horn_h), (hx - horn_w, hy + 2), (hx + horn_w, hy + 2)],
                         fill=primary)

    # face
    n_eyes = random.choices([1, 2, 3], weights=[20, 55, 25])[0]
    eye_r = max(int(min(body_hw, body_hh) * 0.10), 5)
    eye_y = body_cy - int(body_hh * 0.18)
    eye_zone_w = body_hw * 0.50
    if n_eyes == 1:
        positions = [(bcx, eye_y)]
    else:
        spacing = eye_zone_w / max(n_eyes - 1, 1)
        sx = bcx - eye_zone_w / 2
        positions = [(sx + i * spacing, eye_y) for i in range(n_eyes)]
    _draw_expressive_eyes(draw, positions, eye_r, primary, secondary, line_w,
                          style=random.choice(["normal", "cute", "sleepy"]))

    mouth_y = body_cy + int(body_hh * 0.22)
    mouth_w = max(int(body_hw * random.uniform(0.15, 0.35)), 6)
    _draw_mouth(draw, bcx, mouth_y, mouth_w, primary, secondary, line_w,
                style=random.choice(["smile", "open", "confused", "grin"]))


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
