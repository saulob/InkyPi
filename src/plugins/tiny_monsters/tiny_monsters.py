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


# ---------------------------------------------------------------------------
# Catmull-Rom spline helpers for smooth curves through control points
# ---------------------------------------------------------------------------

def _catmull_rom_segment(p0, p1, p2, p3, steps=8):
    """Return points along a Catmull-Rom spline segment between p1 and p2."""
    pts = []
    for i in range(steps + 1):
        t = i / steps
        t2, t3 = t * t, t * t * t
        x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t
                    + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                    + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
        y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t
                    + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                    + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
        pts.append((x, y))
    return pts


def _catmull_rom_closed(controls, steps_per_seg=6):
    """Smooth closed curve through control points using Catmull-Rom splines."""
    n = len(controls)
    if n < 3:
        return list(controls)
    pts = []
    for i in range(n):
        seg = _catmull_rom_segment(
            controls[(i - 1) % n], controls[i],
            controls[(i + 1) % n], controls[(i + 2) % n],
            steps_per_seg)
        pts.extend(seg[:-1])
    return pts


def _catmull_rom_open(controls, steps_per_seg=6):
    """Smooth open curve through control points using Catmull-Rom splines."""
    n = len(controls)
    if n < 2:
        return list(controls)
    ext = [controls[0]] + list(controls) + [controls[-1]]
    pts = []
    for i in range(1, len(ext) - 2):
        seg = _catmull_rom_segment(ext[i - 1], ext[i], ext[i + 1], ext[i + 2],
                                   steps_per_seg)
        if i > 1:
            seg = seg[1:]
        pts.extend(seg)
    return pts


# ---------------------------------------------------------------------------
# Polygon-based stroke for smooth tapered limbs and tentacles
# ---------------------------------------------------------------------------

def _stroke_path_poly(draw, pts, base_w, fill, taper_start=1.0, taper_end=0.3):
    """Draw a thick stroked path as a filled polygon with smooth tapering."""
    if len(pts) < 2:
        return
    left, right = [], []
    for i, (x, y) in enumerate(pts):
        t = i / max(len(pts) - 1, 1)
        hw = base_w * 0.5 * (taper_start + (taper_end - taper_start) * t)
        if i == 0:
            dx, dy = pts[1][0] - x, pts[1][1] - y
        elif i == len(pts) - 1:
            dx, dy = x - pts[-2][0], y - pts[-2][1]
        else:
            dx, dy = pts[i + 1][0] - pts[i - 1][0], pts[i + 1][1] - pts[i - 1][1]
        ln = math.hypot(dx, dy) or 1
        nx, ny = -dy / ln, dx / ln
        left.append((x + nx * hw, y + ny * hw))
        right.append((x - nx * hw, y - ny * hw))
    draw.polygon(left + right[::-1], fill=fill)


# ---------------------------------------------------------------------------
# Organic body-shape generators with varied silhouettes
# ---------------------------------------------------------------------------

def _pear_blob(cx, cy, rx, ry, num_controls=12, wobble=0.10):
    """Pear/teardrop shape: wider at bottom, narrower at top."""
    controls = []
    for i in range(num_controls):
        a = 2 * math.pi * i / num_controls
        widen = 1.0 + 0.25 * max(0, math.sin(a))
        r_jitter = 1.0 + random.uniform(-wobble, wobble)
        controls.append((cx + rx * widen * r_jitter * math.cos(a),
                         cy + ry * r_jitter * math.sin(a)))
    return _catmull_rom_closed(controls, steps_per_seg=6)


def _bean_blob(cx, cy, rx, ry, num_controls=12, wobble=0.08):
    """Bean/kidney shape: indented on one side."""
    controls = []
    for i in range(num_controls):
        a = 2 * math.pi * i / num_controls
        indent = 1.0 - 0.18 * max(0, math.cos(a)) * (0.5 + 0.5 * math.sin(a))
        r_jitter = 1.0 + random.uniform(-wobble, wobble)
        controls.append((cx + rx * indent * r_jitter * math.cos(a),
                         cy + ry * r_jitter * math.sin(a)))
    return _catmull_rom_closed(controls, steps_per_seg=6)


def _squat_blob(cx, cy, rx, ry, num_controls=12, wobble=0.10):
    """Squat shape: wider with flat-ish bottom and round top."""
    controls = []
    for i in range(num_controls):
        a = 2 * math.pi * i / num_controls
        if math.sin(a) > 0.3:
            stretch = 1.0 + 0.15 * math.sin(a)
        elif math.sin(a) < -0.3:
            stretch = 1.0 - 0.08 * abs(math.sin(a))
        else:
            stretch = 1.0
        r_jitter = 1.0 + random.uniform(-wobble, wobble)
        controls.append((cx + rx * stretch * r_jitter * math.cos(a),
                         cy + ry * r_jitter * math.sin(a)))
    return _catmull_rom_closed(controls, steps_per_seg=6)


# ---------------------------------------------------------------------------
# Core organic shape primitives (Catmull-Rom smoothed)
# ---------------------------------------------------------------------------

def _organic_blob(cx, cy, rx, ry, num_controls=12, wobble=0.12):
    """Generate an organic closed shape using Catmull-Rom spline smoothing."""
    controls = []
    for i in range(num_controls):
        a = 2 * math.pi * i / num_controls
        r_jitter = 1.0 + random.uniform(-wobble, wobble)
        controls.append((cx + rx * r_jitter * math.cos(a),
                         cy + ry * r_jitter * math.sin(a)))
    return _catmull_rom_closed(controls, steps_per_seg=6)


def _draw_filled_blob(draw, cx, cy, rx, ry, fill, outline, line_w, wobble=0.10,
                       shape_func=None):
    """Draw an organic filled shape with smooth spline-based outline."""
    if shape_func:
        pts = shape_func(cx, cy, rx, ry, wobble=wobble)
    else:
        pts = _organic_blob(cx, cy, rx, ry, wobble=wobble)
    draw.polygon(pts, fill=fill, outline=outline, width=line_w)
    return pts


def _draw_organic_limb(draw, x1, y1, x2, y2, thickness, fill, taper=0.7):
    """Draw a thick organic limb with smooth cubic Bezier and polygon tapering."""
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy) or 1
    px, py = -dy / length, dx / length
    sway = random.uniform(-thickness, thickness) * 0.5
    c1 = (x1 + dx * 0.3 + px * sway, y1 + dy * 0.3 + py * sway)
    c2 = (x1 + dx * 0.7 - px * sway * 0.6, y1 + dy * 0.7 - py * sway * 0.6)
    pts = _cubic_bezier_pts((x1, y1), c1, c2, (x2, y2), steps=14)
    _stroke_path_poly(draw, pts, thickness, fill, taper_start=1.0, taper_end=taper)


def _draw_organic_leg(draw, x1, y1, x2, y2, thickness, fill, foot_r=0):
    """Draw a thick cartoon leg with optional organic foot."""
    _draw_organic_limb(draw, x1, y1, x2, y2, thickness, fill, taper=0.85)
    if foot_r > 0:
        fx, fy = x2, y2 + foot_r * 0.25
        pts = _organic_blob(fx, fy, foot_r, foot_r * 0.55, num_controls=10, wobble=0.08)
        draw.polygon(pts, fill=fill)


def _draw_expressive_eyes(draw, positions, base_r, primary, secondary, line_w,
                           style="normal", look_dir=0):
    """Draw cartoon doodle eyes with organic shapes and layered detail."""
    for i, (ex, ey) in enumerate(positions):
        r = base_r + random.randint(-1, 1)
        # Smooth organic eye white using Catmull-Rom
        eye_pts = _organic_blob(ex, ey, r, r * 1.05, num_controls=10, wobble=0.04)
        draw.polygon(eye_pts, fill=secondary, outline=primary, width=line_w)

        if style == "hollow":
            inner = max(r - line_w * 2, 2)
            inner_pts = _organic_blob(ex, ey, inner, inner, num_controls=8, wobble=0.03)
            draw.polygon(inner_pts, fill=secondary, outline=primary, width=max(line_w - 1, 1))
        else:
            # Iris (larger, organic)
            ir = max(int(r * 0.55), 3)
            ix = ex + int(look_dir * ir * 0.35)
            iy = ey + random.randint(-1, 1)
            iris_pts = _organic_blob(ix, iy, ir, ir, num_controls=8, wobble=0.03)
            draw.polygon(iris_pts, fill=primary)
            # Pupil center
            pr = max(ir // 2, 2)
            draw.ellipse([ix - pr, iy - pr, ix + pr, iy + pr], fill=primary)
            # Main highlight
            hr = max(pr // 2, 1)
            hx = ix - int(ir * 0.25)
            hy = iy - int(ir * 0.25)
            draw.ellipse([hx - hr, hy - hr, hx + hr, hy + hr], fill=secondary)
            # Tiny second highlight for illustrated look
            hr2 = max(hr - 1, 1)
            draw.ellipse([ix + hr, iy + hr, ix + hr + hr2, iy + hr + hr2],
                         fill=secondary)

        # Sleepy: organic curved lid
        if style == "sleepy":
            lid_pts = _bezier_pts((ex - r * 1.1, ey - r * 0.1),
                                  (ex, ey - r * 0.4),
                                  (ex + r * 1.1, ey - r * 0.05), steps=10)
            lid_poly = [(ex - r - 2, ey - r - 2)] + lid_pts + [(ex + r + 2, ey - r - 2)]
            draw.polygon(lid_poly, fill=secondary)
            _draw_thick_curve(draw, lid_pts, max(line_w, 2), primary)

        # Angry: curved angled brow
        if style == "angry":
            brow_y = ey - r - line_w * 2
            side = -1 if i == 0 else 1
            brow_pts = _bezier_pts(
                (ex - r * 0.9, brow_y - r * 0.35 * side),
                (ex, brow_y + r * 0.1 * side),
                (ex + r * 0.9, brow_y + r * 0.35 * side), steps=8)
            _draw_thick_curve(draw, brow_pts, max(line_w + 1, 3), primary)

        # Cute: small curved brow
        if style == "cute":
            brow_y = ey - r - line_w * 2
            brow_pts = _bezier_pts(
                (ex - r * 0.45, brow_y),
                (ex, brow_y - max(r * 0.15, 2)),
                (ex + r * 0.45, brow_y), steps=6)
            _draw_thick_curve(draw, brow_pts, max(line_w, 2), primary)

def _draw_mouth(draw, cx, cy, width, primary, secondary, line_w,
                style="smile"):
    """Draw an organic cartoon mouth with smooth curves."""
    hw = width // 2
    if style == "smile":
        controls = [(cx - hw, cy), (cx - hw * 0.3, cy + hw * 0.3),
                    (cx + hw * 0.3, cy + hw * 0.35), (cx + hw, cy)]
        pts = _catmull_rom_open(controls, steps_per_seg=8)
        _draw_thick_curve(draw, pts, line_w, primary)
    elif style == "grin":
        # Wide curved grin filled with teeth
        controls = [(cx - hw, cy - hw * 0.1), (cx - hw * 0.4, cy + hw * 0.5),
                    (cx + hw * 0.4, cy + hw * 0.5), (cx + hw, cy - hw * 0.1)]
        outline = _catmull_rom_open(controls, steps_per_seg=8)
        grin_poly = list(outline)
        draw.polygon(grin_poly, fill=primary)
        # Organic teeth inside grin
        n_teeth = random.randint(2, 5)
        if n_teeth > 0:
            tw = max(hw * 2 // (n_teeth + 1), 3)
            th = max(int(hw * 0.35), 3)
            total = n_teeth * tw + (n_teeth - 1) * 2
            sx = cx - total // 2
            for ti in range(n_teeth):
                tx = sx + ti * (tw + 2)
                tooth_y = cy + int(hw * 0.05)
                tooth_pts = _organic_blob(tx + tw // 2, tooth_y,
                                           tw // 2, th // 2,
                                           num_controls=6, wobble=0.06)
                draw.polygon(tooth_pts, fill=secondary)
    elif style == "open":
        mr = max(hw // 2, 4)
        pts = _organic_blob(cx, cy + 2, mr, int(mr * 0.7),
                             num_controls=8, wobble=0.08)
        draw.polygon(pts, fill=primary)
    elif style == "confused":
        controls = [(cx - hw * 0.5, cy + 2), (cx - hw * 0.15, cy - hw * 0.25),
                    (cx + hw * 0.15, cy + hw * 0.15), (cx + hw * 0.5, cy - hw * 0.1)]
        pts = _catmull_rom_open(controls, steps_per_seg=6)
        _draw_thick_curve(draw, pts, line_w, primary)
    elif style == "teeth":
        mouth_pts = _bezier_pts((cx - hw, cy + random.randint(-2, 2)),
                                (cx, cy + random.randint(-2, 2)),
                                (cx + hw, cy + random.randint(-2, 2)), steps=8)
        _draw_thick_curve(draw, mouth_pts, line_w, primary)
        n_teeth = random.randint(2, 5)
        tw = max(hw * 2 // (n_teeth + 1), 3)
        th = max(tw, 3)
        total = n_teeth * tw + (n_teeth - 1) * 2
        sx = cx - total // 2
        for ti in range(n_teeth):
            if random.random() < 0.25:
                continue
            tx = sx + ti * (tw + 2)
            tooth_pts = [(tx, cy), (tx + tw, cy),
                         (tx + tw * 0.7 + random.randint(-1, 1), cy + th),
                         (tx + tw * 0.3 + random.randint(-1, 1), cy + th)]
            draw.polygon(tooth_pts, fill=secondary, outline=primary,
                         width=max(line_w - 1, 1))
    elif style == "sleepy":
        controls = [(cx - hw * 0.4, cy), (cx, cy + hw * 0.15),
                    (cx + hw * 0.4, cy)]
        pts = _catmull_rom_open(controls, steps_per_seg=6)
        _draw_thick_curve(draw, pts, line_w, primary)

def _draw_simple_spikes(draw, pts_along_curve, spike_h_range, spike_w, fill):
    """Draw triangular spikes along a series of points."""
    for x, y in pts_along_curve:
        sh = random.randint(*spike_h_range)
        sw = spike_w + random.randint(-1, 1)
        draw.polygon([(x, y - sh), (x - sw, y + 2), (x + sw, y + 2)], fill=fill)


def _draw_fur_edge(draw, pts, tuft_len_range, fill, line_w):
    """Draw soft fur tufts along an outline using curved strokes."""
    step = max(len(pts) // random.randint(6, 14), 1)
    for i in range(0, len(pts), step):
        px, py = pts[i]
        tl = random.randint(*tuft_len_range)
        angle = random.uniform(0, 2 * math.pi)
        mx = px + tl * 0.5 * math.cos(angle + random.uniform(-0.4, 0.4))
        my = py + tl * 0.5 * math.sin(angle + random.uniform(-0.4, 0.4))
        tx = px + tl * math.cos(angle)
        ty = py + tl * math.sin(angle)
        tuft_pts = _bezier_pts((px, py), (mx, my), (tx, ty), steps=6)
        _draw_thick_curve(draw, tuft_pts, line_w, fill)


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
    """Draw a tentacle with smooth organic Catmull-Rom curves and polygon tapering."""
    controls = [(sx, sy)]
    segs = random.randint(3, 5)
    seg_len = length / segs
    for i in range(segs):
        d = 1 if i % 2 == 0 else -1
        x = controls[-1][0] + random.uniform(sway_range * 0.3, sway_range) * d
        y = controls[-1][1] + seg_len
        controls.append((x, y))
    pts = _catmull_rom_open(controls, steps_per_seg=6)
    _stroke_path_poly(draw, pts, tent_w, primary, taper_start=1.0, taper_end=0.2)
    # Rounded tip
    r = max(2, tent_w // 3)
    tip = pts[-1]
    draw.ellipse([tip[0] - r, tip[1] - r, tip[0] + r, tip[1] + r], fill=primary)


def _draw_polygon_body(draw, points, fill, outline, line_w):
    """Draw a body from pre-computed polygon points."""
    draw.polygon(points, fill=fill, outline=outline, width=line_w)


def _oval_silhouette(cx, cy, rx, ry, wobble=0.0):
    return _ellipse_points(cx, cy, rx, ry)


def _round_silhouette(cx, cy, rx, ry, wobble=0.0):
    radius = min(rx, ry)
    return _ellipse_points(cx, cy, radius, radius)


def _rounded_rect_silhouette(cx, cy, rx, ry, wobble=0.0):
    return _rounded_rect_points(cx, cy, rx, ry, max(min(rx, ry) / 3, 1))


def _squared_silhouette(cx, cy, rx, ry, wobble=0.0):
    return _rounded_rect_points(cx, cy, rx, ry, max(min(rx, ry) / 8, 1))


def _capsule_silhouette(cx, cy, rx, ry, wobble=0.0):
    return _rounded_rect_points(cx, cy, rx, ry, max(min(rx, ry) / 2.2, 1))


BODY_SHAPES = {
    "oval": _oval_silhouette,
    "round": _round_silhouette,
    "rounded_rect": _rounded_rect_silhouette,
    "squared": _squared_silhouette,
    "capsule": _capsule_silhouette,
}


def _pick_template(templates):
    return random.choice(templates)


DINOSAUR_TEMPLATES = [
    {"body_tier": "tall", "body_shape": "oval", "neck_tier": "long", "spike_tier": "few",
     "eye_style": "cute", "mouth_style": "smile", "tail_tier": "long"},
    {"body_tier": "chubby", "body_shape": "squared", "neck_tier": "short", "spike_tier": "many",
     "eye_style": "angry", "mouth_style": "grin", "tail_tier": "thick"},
    {"body_tier": "normal", "body_shape": "round", "neck_tier": "none", "spike_tier": "none",
     "eye_style": "normal", "mouth_style": "smile", "tail_tier": "short"},
    {"body_tier": "normal", "body_shape": "rounded_rect", "neck_tier": "medium", "spike_tier": "plates",
     "eye_style": "sleepy", "mouth_style": "open", "tail_tier": "medium"},
]

SPIDER_TEMPLATES = [
    {"abdomen_tier": "small", "abdomen_shape": "oval", "head_ratio": 0.70, "num_pairs": 4,
     "leg_len_tier": "long", "eye_count": 8, "mouth_style": "smile"},
    {"abdomen_tier": "medium", "abdomen_shape": "round", "head_ratio": 0.58, "num_pairs": 3,
     "leg_len_tier": "medium", "eye_count": 6, "mouth_style": "confused"},
    {"abdomen_tier": "large", "abdomen_shape": "oval", "head_ratio": 0.62, "num_pairs": 4,
     "leg_len_tier": "short", "eye_count": 4, "mouth_style": "open"},
    {"abdomen_tier": "medium", "abdomen_shape": "capsule", "head_ratio": 0.52, "num_pairs": 4,
     "leg_len_tier": "long", "eye_count": 2, "mouth_style": "smile"},
]

WEREWOLF_TEMPLATES = [
    {"build": "lean", "body_shape": "rounded_rect", "arm_pose": "raised", "eye_style": "angry",
     "mouth_style": "grin", "fur_tier": "sparse"},
    {"build": "stocky", "body_shape": "squared", "arm_pose": "lowered", "eye_style": "normal",
     "mouth_style": "smile", "fur_tier": "heavy"},
    {"build": "hulking", "body_shape": "oval", "arm_pose": "reaching", "eye_style": "angry",
     "mouth_style": "teeth", "fur_tier": "heavy"},
    {"build": "hunched", "body_shape": "capsule", "arm_pose": "raised", "eye_style": "cute",
     "mouth_style": "open", "fur_tier": "spiky"},
]

ZOMBIE_TEMPLATES = [
    {"body_tier": "thin", "body_shape": "rounded_rect", "arm_mode": "both", "eye_dead": True,
     "mouth_style": "confused"},
    {"body_tier": "normal", "body_shape": "squared", "arm_mode": "one", "eye_dead": False,
     "mouth_style": "open"},
    {"body_tier": "wide", "body_shape": "oval", "arm_mode": "both", "eye_dead": True,
     "mouth_style": "teeth"},
    {"body_tier": "thin", "body_shape": "capsule", "arm_mode": "both", "eye_dead": False,
     "mouth_style": "smile"},
]

OCTOPUS_TEMPLATES = [
    {"dome_tier": "small", "dome_shape": "round", "n_tentacles": 8, "tent_len_tier": "long",
     "eye_count": 2, "mouth_style": "smile"},
    {"dome_tier": "medium", "dome_shape": "oval", "n_tentacles": 6, "tent_len_tier": "medium",
     "eye_count": 3, "mouth_style": "open"},
    {"dome_tier": "large", "dome_shape": "capsule", "n_tentacles": 5, "tent_len_tier": "short",
     "eye_count": 2, "mouth_style": "confused"},
    {"dome_tier": "medium", "dome_shape": "round", "n_tentacles": 7, "tent_len_tier": "long",
     "eye_count": 2, "mouth_style": "sleepy"},
]

DRAGON_TEMPLATES = [
    {"body_tier": "compact", "body_shape": "oval", "wing_tier": "large", "n_legs": 2,
     "tail_tier": "long", "spike_tier": "few", "eye_style": "cute", "mouth_style": "grin"},
    {"body_tier": "wide", "body_shape": "squared", "wing_tier": "small", "n_legs": 4,
     "tail_tier": "side", "spike_tier": "many", "eye_style": "normal", "mouth_style": "teeth"},
    {"body_tier": "tall", "body_shape": "rounded_rect", "wing_tier": "large", "n_legs": 2,
     "tail_tier": "long", "spike_tier": "few", "eye_style": "angry", "mouth_style": "smile"},
    {"body_tier": "compact", "body_shape": "round", "wing_tier": "none", "n_legs": 4,
     "tail_tier": "side", "spike_tier": "many", "eye_style": "sleepy", "mouth_style": "open"},
]

CTHULHU_TEMPLATES = [
    {"head_tier": "large", "head_shape": "oval", "body_shape": "round", "n_eyes": 2,
     "tent_total": 5, "tent_len_tier": "long", "horns": True, "wings": False},
    {"head_tier": "very_large", "head_shape": "capsule", "body_shape": "squared", "n_eyes": 4,
     "tent_total": 7, "tent_len_tier": "short", "horns": True, "wings": True},
    {"head_tier": "large", "head_shape": "round", "body_shape": "oval", "n_eyes": 3,
     "tent_total": 6, "tent_len_tier": "long", "horns": False, "wings": True},
    {"head_tier": "very_large", "head_shape": "oval", "body_shape": "rounded_rect", "n_eyes": 2,
     "tent_total": 4, "tent_len_tier": "short", "horns": True, "wings": False},
]

GHOST_TEMPLATES = [
    {"size_tier": "small", "eye_count": 1, "mouth_style": "open", "arm_style": "stubs"},
    {"size_tier": "medium", "eye_count": 2, "mouth_style": "smile", "arm_style": "reaching"},
    {"size_tier": "large", "eye_count": 3, "mouth_style": "confused", "arm_style": "one_only"},
    {"size_tier": "medium", "eye_count": 2, "mouth_style": "none", "arm_style": "none"},
]

DEFAULT_TEMPLATES = [
    {"body_shape": "oval", "use_tentacles": False, "use_wings": True, "use_tail": False,
     "use_horns": True, "n_legs": 2, "eye_count": 2, "mouth_style": "smile"},
    {"body_shape": "rounded_rect", "use_tentacles": True, "use_wings": False, "use_tail": True,
     "use_horns": False, "n_legs": 0, "eye_count": 3, "mouth_style": "open"},
    {"body_shape": "squared", "use_tentacles": False, "use_wings": False, "use_tail": True,
     "use_horns": True, "n_legs": 4, "eye_count": 1, "mouth_style": "grin"},
    {"body_shape": "round", "use_tentacles": False, "use_wings": True, "use_tail": False,
     "use_horns": False, "n_legs": 2, "eye_count": 2, "mouth_style": "cute"},
]


DINOSAUR_POSE_TEMPLATES = [
    {"name": "long_neck_right", "facing": 1, "body_x": -0.05, "body_y": 0.04,
     "force_neck": "long", "stretch_x": 1.00, "stretch_y": 1.00, "leg_spread": 0.32,
     "arm_forward": 0.82, "head_drop": -0.10, "horned": False},
    {"name": "long_neck_left", "facing": -1, "body_x": 0.05, "body_y": 0.04,
     "force_neck": "long", "stretch_x": 1.00, "stretch_y": 1.00, "leg_spread": 0.32,
     "arm_forward": 0.82, "head_drop": -0.10, "horned": False},
    {"name": "upright_trex", "facing": 1, "body_x": 0.00, "body_y": -0.03,
     "force_neck": "none", "stretch_x": 0.95, "stretch_y": 1.20, "leg_spread": 0.22,
     "arm_forward": 0.45, "head_drop": 0.02, "horned": False},
    {"name": "low_horizontal", "facing": -1, "body_x": 0.00, "body_y": 0.10,
     "force_neck": "short", "stretch_x": 1.35, "stretch_y": 0.75, "leg_spread": 0.46,
     "arm_forward": 0.70, "head_drop": 0.08, "horned": False},
    {"name": "triceratops_like", "facing": -1, "body_x": 0.02, "body_y": 0.06,
     "force_neck": "short", "stretch_x": 1.12, "stretch_y": 0.92, "leg_spread": 0.36,
     "arm_forward": 0.62, "head_drop": 0.10, "horned": True},
]

SPIDER_POSE_TEMPLATES = [
    {"name": "wide", "facing": 1, "body_x": 0.00, "body_y": 0.02, "diag": 0.00,
     "front_raise": False, "leg_spread": 1.25, "head_x": 0.00, "head_y": 0.00},
    {"name": "compact", "facing": 1, "body_x": 0.00, "body_y": 0.06, "diag": 0.00,
     "front_raise": False, "leg_spread": 0.80, "head_x": 0.00, "head_y": 0.10},
    {"name": "diagonal", "facing": -1, "body_x": 0.03, "body_y": 0.00, "diag": 0.22,
     "front_raise": False, "leg_spread": 1.05, "head_x": 0.35, "head_y": -0.05},
    {"name": "tall_front_raised", "facing": 1, "body_x": -0.02, "body_y": -0.05, "diag": -0.15,
     "front_raise": True, "leg_spread": 0.95, "head_x": -0.20, "head_y": -0.12},
]

WEREWOLF_POSE_TEMPLATES = [
    {"name": "upright", "body_x": 0.00, "body_y": -0.02, "lean": 0.00, "arm_lift": 0.10},
    {"name": "lunging_left", "body_x": -0.05, "body_y": 0.03, "lean": -0.10, "arm_lift": -0.05},
    {"name": "lunging_right", "body_x": 0.05, "body_y": 0.03, "lean": 0.10, "arm_lift": -0.05},
    {"name": "hunched", "body_x": 0.00, "body_y": 0.08, "lean": -0.04, "arm_lift": 0.18},
]

ZOMBIE_POSE_TEMPLATES = [
    {"name": "tilted_left", "body_x": -0.04, "body_y": 0.04, "lean": -0.10, "drag_leg": -1},
    {"name": "tilted_right", "body_x": 0.04, "body_y": 0.04, "lean": 0.10, "drag_leg": 1},
    {"name": "stagger_forward", "body_x": 0.00, "body_y": 0.08, "lean": -0.04, "drag_leg": -1},
    {"name": "stiff_upright", "body_x": 0.00, "body_y": -0.02, "lean": 0.00, "drag_leg": 0},
]

OCTOPUS_POSE_TEMPLATES = [
    {"name": "centered", "body_x": 0.00, "body_y": -0.02, "tent_bias": 0.00, "fan": 1.00},
    {"name": "drifting_left", "body_x": -0.05, "body_y": 0.02, "tent_bias": -0.20, "fan": 1.20},
    {"name": "drifting_right", "body_x": 0.05, "body_y": 0.02, "tent_bias": 0.20, "fan": 1.20},
    {"name": "top_heavy", "body_x": 0.00, "body_y": -0.08, "tent_bias": 0.00, "fan": 0.80},
]

DRAGON_POSE_TEMPLATES = [
    {"name": "facing_right", "facing": 1, "body_x": -0.03, "body_y": 0.00, "wing_lift": -0.10, "tail_side": 1},
    {"name": "facing_left", "facing": -1, "body_x": 0.03, "body_y": 0.00, "wing_lift": -0.10, "tail_side": -1},
    {"name": "perched", "facing": 1, "body_x": 0.00, "body_y": 0.08, "wing_lift": 0.06, "tail_side": -1},
    {"name": "soaring", "facing": -1, "body_x": 0.00, "body_y": -0.08, "wing_lift": -0.20, "tail_side": 1},
]

CTHULHU_POSE_TEMPLATES = [
    {"name": "centered", "head_x": 0.00, "head_y": -0.02, "body_x": 0.00, "tent_bias": 0.00},
    {"name": "lean_left", "head_x": -0.04, "head_y": 0.00, "body_x": -0.03, "tent_bias": -0.25},
    {"name": "lean_right", "head_x": 0.04, "head_y": 0.00, "body_x": 0.03, "tent_bias": 0.25},
    {"name": "looming", "head_x": 0.00, "head_y": -0.10, "body_x": 0.00, "tent_bias": 0.00},
]

GHOST_POSE_TEMPLATES = [
    {"name": "centered", "body_x": 0.00, "body_y": 0.00, "arm_bias": 0.00},
    {"name": "float_left", "body_x": -0.05, "body_y": -0.04, "arm_bias": -0.08},
    {"name": "float_right", "body_x": 0.05, "body_y": -0.04, "arm_bias": 0.08},
    {"name": "drooping", "body_x": 0.00, "body_y": 0.06, "arm_bias": 0.00},
]

DEFAULT_POSE_TEMPLATES = [
    {"name": "centered", "body_x": 0.00, "body_y": 0.00, "facing": 1},
    {"name": "left", "body_x": -0.05, "body_y": 0.02, "facing": -1},
    {"name": "right", "body_x": 0.05, "body_y": 0.02, "facing": 1},
    {"name": "low", "body_x": 0.00, "body_y": 0.08, "facing": -1},
]


# ---------------------------------------------------------------------------
# Archetype drawing templates — cartoon doodle style
# ---------------------------------------------------------------------------

def _draw_dinosaur_archetype(draw, cx, cy, zone_w, zone_h, primary, secondary, line_w):
    """Dinosaur: rounded body, curved neck, thick tail, small arms, short legs, back spikes."""
    template = _pick_template(DINOSAUR_TEMPLATES)
    pose = _pick_template(DINOSAUR_POSE_TEMPLATES)
    facing = pose["facing"]

    # --- pose: slight tilt and offset ---
    tilt = random.uniform(-0.03, 0.03)
    lean_x = int(zone_w * (pose["body_x"] + random.uniform(-0.01, 0.01)))
    bcx = cx + lean_x

    # --- body proportions ---
    body_tier = template["body_tier"]
    if body_tier == "chubby":
        body_rx = int(zone_w * random.uniform(0.12, 0.16))
        body_ry = int(zone_h * random.uniform(0.12, 0.16))
    elif body_tier == "normal":
        body_rx = int(zone_w * random.uniform(0.10, 0.14))
        body_ry = int(zone_h * random.uniform(0.14, 0.20))
    else:
        body_rx = int(zone_w * random.uniform(0.08, 0.12))
        body_ry = int(zone_h * random.uniform(0.18, 0.24))

    body_rx = int(body_rx * pose["stretch_x"])
    body_ry = int(body_ry * pose["stretch_y"])
    body_cy = cy + int(zone_h * pose["body_y"])

    # --- head: large relative to body (cartoon proportion) ---
    head_r = max(int(body_rx * random.uniform(0.55, 0.85)), 14)
    neck_tier = pose.get("force_neck") or template["neck_tier"]
    if neck_tier == "none":
        neck_len = 0
        head_cx = bcx + facing * int(body_rx * 0.4)
        head_cy = body_cy - body_ry - int(head_r * (0.3 + pose["head_drop"]))
    elif neck_tier == "short":
        neck_len = int(body_ry * random.uniform(0.15, 0.30))
        head_cx = bcx + facing * int(body_rx * random.uniform(0.2, 0.5))
        head_cy = body_cy - body_ry - neck_len - int(head_r * (0.2 + pose["head_drop"]))
    else:
        neck_len = int(body_ry * random.uniform(0.35, 0.55))
        head_cx = bcx + facing * int(body_rx * random.uniform(0.15, 0.45))
        head_cy = body_cy - body_ry - neck_len - int(head_r * (0.1 + pose["head_drop"]))

    # --- tail: thick, curved ---
    tail_tier = template["tail_tier"]
    if tail_tier == "short":
        tail_len = int(zone_w * random.uniform(0.05, 0.10))
    elif tail_tier == "medium":
        tail_len = int(zone_w * random.uniform(0.10, 0.15))
    elif tail_tier == "thick":
        tail_len = int(zone_w * random.uniform(0.08, 0.14))
    else:
        tail_len = int(zone_w * random.uniform(0.16, 0.24))
    tail_w = max(line_w + 3, int(body_rx * 0.25))
    tail_x0 = bcx - facing * body_rx + int(-facing * body_rx * 0.15)
    tail_y0 = body_cy + int(body_ry * random.uniform(0.0, 0.3))
    tail_ctrl = (tail_x0 - facing * tail_len * 0.5, tail_y0 + tail_len * random.uniform(0.3, 0.7))
    tail_end = (tail_x0 - facing * tail_len, tail_y0 + int(tail_len * random.uniform(-0.1, 0.3)))
    tail_pts = _bezier_pts((tail_x0, tail_y0), tail_ctrl, tail_end, steps=10)
    for i in range(len(tail_pts) - 1):
        w = max(tail_w - i * 2, line_w)
        draw.line([tail_pts[i], tail_pts[i + 1]], fill=primary, width=w)

    # --- legs: short, thick (cartoon) ---
    leg_h = int(zone_h * random.uniform(0.08, 0.15))
    leg_w = max(line_w + 3, int(body_rx * 0.22))
    foot_r = max(leg_w, 6)
    leg_base = pose["leg_spread"]
    for x_off in (-leg_base + random.uniform(-0.06, 0.06), leg_base + random.uniform(-0.06, 0.06)):
        lx = bcx + int(body_rx * x_off)
        ly = body_cy + body_ry
        _draw_organic_leg(draw, lx, ly, lx + random.randint(-3, 3), ly + leg_h,
                         leg_w, primary, foot_r)

    # --- small arms ---
    arm_len = int(body_rx * random.uniform(0.20, 0.40))
    arm_w = max(line_w + 1, int(body_rx * 0.12))
    arm_x = bcx + facing * int(body_rx * random.uniform(0.5, 0.8))
    arm_y = body_cy - int(body_ry * random.uniform(0.0, 0.2))
    hand_x = arm_x + facing * int(arm_len * random.uniform(0.2, pose["arm_forward"]))
    hand_y = arm_y + int(arm_len * random.uniform(0.5, 0.9))
    _draw_organic_limb(draw, arm_x, arm_y, hand_x, hand_y, arm_w, primary)

    # --- body silhouette (organic shape) ---
    body_shape = BODY_SHAPES[template["body_shape"]]
    body_pts = _draw_filled_blob(draw, bcx, body_cy, body_rx, body_ry,
                                  secondary, primary, line_w, wobble=0.08,
                                  shape_func=body_shape)

    # --- back spikes ---
    spike_tier = template["spike_tier"]
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
        neck_base = (bcx + facing * int(body_rx * 0.3), body_cy - body_ry + int(body_ry * 0.1))
        neck_top = (head_cx - facing * int(head_r * 0.2), head_cy + int(head_r * 0.5))
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

    # Triceratops-like frill and horns for profile readability.
    if pose["horned"]:
        frill_r = max(int(head_r * 0.75), 9)
        frill_x = head_cx - facing * int(head_r * 0.45)
        frill_y = head_cy - int(head_r * 0.05)
        draw.ellipse([frill_x - frill_r, frill_y - frill_r,
                      frill_x + frill_r, frill_y + frill_r],
                     fill=secondary, outline=primary, width=line_w)
        horn_len = max(int(head_r * 0.45), 6)
        nose_x = head_cx + facing * int(head_r * 0.6)
        nose_y = head_cy + int(head_r * 0.05)
        draw.line([(nose_x, nose_y),
                   (nose_x + facing * horn_len, nose_y - horn_len // 3)],
                  fill=primary, width=max(line_w - 1, 1))

    # --- head (organic blob) ---
    head_pts = _draw_filled_blob(draw, head_cx, head_cy, head_r, int(head_r * 0.9),
                                  secondary, primary, line_w, wobble=0.06,
                                  shape_func=BODY_SHAPES["round"])

    # --- face ---
    look_dir = facing * random.choice([0, 1])
    eye_r = max(int(head_r * random.uniform(0.22, 0.35)), 5)
    eye_y = head_cy - int(head_r * random.uniform(0.05, 0.20))
    eye_spread = head_r * random.uniform(0.25, 0.45)
    eye_style = template["eye_style"]
    _draw_expressive_eyes(draw,
                          [(head_cx - eye_spread, eye_y), (head_cx + eye_spread, eye_y)],
                          eye_r, primary, secondary, line_w,
                          style=eye_style, look_dir=look_dir)

    mouth_style = template["mouth_style"]
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
    template = _pick_template(SPIDER_TEMPLATES)
    pose = _pick_template(SPIDER_POSE_TEMPLATES)
    facing = pose["facing"]
    scx = cx + int(zone_w * pose["body_x"])
    scy = cy + int(zone_h * pose["body_y"])

    # --- body proportions ---
    body_tier = template["abdomen_tier"]
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
    head_ratio = template["head_ratio"]
    head_r = max(int(min(abd_rx, abd_ry) * head_ratio), 10)
    head_gap = random.uniform(0.10, 0.35)
    head_cx = scx + facing * int(abd_rx * pose["head_x"])
    head_cy = scy - abd_ry - int(head_r * (1 - head_gap + pose["head_y"]))

    # --- legs: 3-4 pairs, organic curves ---
    num_pairs = template["num_pairs"]
    leg_thickness = max(line_w + 1, int(abd_rx * 0.10))
    leg_len_tier = template["leg_len_tier"]
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
    spread_angles = [angle * pose["leg_spread"] + pose["diag"] for angle in spread_angles]
    if pose["front_raise"] and spread_angles:
        spread_angles[0] += 0.38
        if len(spread_angles) > 1:
            spread_angles[1] += 0.18
    for i in range(num_pairs):
        for side in (-1, 1):
            jit = random.uniform(-0.06, 0.06)
            ax = scx + side * abd_rx * random.uniform(0.7, 0.9)
            ay = scy - abd_ry * 0.3 + i * (abd_ry * random.uniform(0.35, 0.50)) + side * pose["diag"] * abd_ry
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

    # --- body silhouette (organic shape) ---
    spider_shape = BODY_SHAPES[template["abdomen_shape"]]
    _draw_filled_blob(draw, scx, scy, abd_rx, abd_ry, secondary, primary, line_w,
                       wobble=0.07, shape_func=spider_shape)

    # head (smooth organic)
    _draw_filled_blob(draw, head_cx, head_cy, head_r, int(head_r * 0.95),
                       secondary, primary, line_w, wobble=0.06,
                       shape_func=BODY_SHAPES["round"])

    # --- eyes: 2, 4, 6, 8 clustered ---
    num_eyes = template["eye_count"]
    eye_r = max(int(head_r * random.uniform(0.18, 0.32)), 4)
    sp_x = head_r * random.uniform(0.25, 0.50)
    sp_y = head_r * random.uniform(0.15, 0.30)
    if num_eyes == 2:
        positions = [(head_cx - sp_x, head_cy), (head_cx + sp_x, head_cy)]
    elif num_eyes == 4:
        positions = [(head_cx - sp_x, head_cy - sp_y), (head_cx + sp_x, head_cy - sp_y),
                     (head_cx - sp_x * 0.6, head_cy + sp_y), (head_cx + sp_x * 0.6, head_cy + sp_y)]
    elif num_eyes == 6:
        positions = [(head_cx - sp_x, head_cy - sp_y), (head_cx + sp_x, head_cy - sp_y),
                     (head_cx - sp_x * 0.7, head_cy), (head_cx + sp_x * 0.7, head_cy),
                     (head_cx - sp_x * 0.4, head_cy + sp_y), (head_cx + sp_x * 0.4, head_cy + sp_y)]
    else:
        positions = [(head_cx - sp_x, head_cy - sp_y), (head_cx + sp_x, head_cy - sp_y),
                     (head_cx - sp_x * 0.8, head_cy - sp_y * 0.3), (head_cx + sp_x * 0.8, head_cy - sp_y * 0.3),
                     (head_cx - sp_x * 0.6, head_cy + sp_y * 0.3), (head_cx + sp_x * 0.6, head_cy + sp_y * 0.3),
                     (head_cx - sp_x * 0.35, head_cy + sp_y), (head_cx + sp_x * 0.35, head_cy + sp_y)]
    _draw_expressive_eyes(draw, positions, eye_r, primary, secondary, line_w,
                          style="cute" if num_eyes >= 6 else "normal")

    # mandibles / smile
    m_y = head_cy + head_r - 2
    mouth_style = template["mouth_style"]
    _draw_mouth(draw, head_cx, m_y, max(int(head_r * 0.5), 6), primary, secondary, line_w,
                style=mouth_style)


def _draw_werewolf_archetype(draw, cx, cy, zone_w, zone_h, primary, secondary, line_w):
    """Werewolf: upright body, fur edges, pointed ears, claws, toothy grin."""
    template = _pick_template(WEREWOLF_TEMPLATES)
    pose = _pick_template(WEREWOLF_POSE_TEMPLATES)

    # --- pose ---
    lean = (pose["lean"] + random.uniform(-0.01, 0.01)) * zone_w
    bcx = cx + int(zone_w * pose["body_x"] + lean)

    # --- body (large torso, cartoon) ---
    build = template["build"]
    if build == "lean":
        body_hw = int(zone_w * random.uniform(0.08, 0.12))
        body_hh = int(zone_h * random.uniform(0.20, 0.26))
    elif build == "stocky":
        body_hw = int(zone_w * random.uniform(0.12, 0.16))
        body_hh = int(zone_h * random.uniform(0.16, 0.22))
    else:
        body_hw = int(zone_w * random.uniform(0.14, 0.20))
        body_hh = int(zone_h * random.uniform(0.20, 0.28))

    body_cy = cy + int(zone_h * (0.02 + pose["body_y"]))

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
    arm_pose = template["arm_pose"]
    claw_count = random.choice([2, 3, 4])
    for side_name, side in (("left", -1), ("right", 1)):
        ax = bcx + side * body_hw
        ay = body_cy - int(body_hh * random.uniform(0.05, 0.20)) - int(body_hh * pose["arm_lift"])
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

    # --- body silhouette (organic shape) ---
    wolf_shape = BODY_SHAPES[template["body_shape"]]
    body_pts = _draw_filled_blob(draw, bcx, body_cy, body_hw, body_hh,
                                  secondary, primary, line_w, wobble=0.08,
                                  shape_func=wolf_shape)

    # --- fur tufts along body edge ---
    fur_tier = template["fur_tier"]
    if fur_tier == "sparse":
        tuft_range = (int(body_hw * 0.03), int(body_hw * 0.07))
    elif fur_tier == "spiky":
        tuft_range = (int(body_hw * 0.06), int(body_hw * 0.12))
    else:
        tuft_range = (int(body_hw * 0.08), int(body_hw * 0.16))
    _draw_fur_edge(draw, body_pts, tuft_range,
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
    eye_style = template["eye_style"]
    _draw_expressive_eyes(draw,
                          [(bcx - eye_spread, eye_y), (bcx + eye_spread, eye_y)],
                          eye_r, primary, secondary, line_w,
                          style=eye_style)

    # toothy grin
    mouth_y = body_cy + int(body_hh * random.uniform(0.05, 0.18))
    mouth_w = max(int(body_hw * random.uniform(0.30, 0.50)), 10)
    _draw_mouth(draw, bcx, mouth_y, mouth_w, primary, secondary, line_w,
                style=template["mouth_style"])


def _draw_zombie_archetype(draw, cx, cy, zone_w, zone_h, primary, secondary, line_w):
    """Zombie: loose posture, slightly bent limbs, uneven face, stitches."""
    template = _pick_template(ZOMBIE_TEMPLATES)
    pose = _pick_template(ZOMBIE_POSE_TEMPLATES)

    # --- posture: tilted ---
    tilt = (pose["lean"] + random.uniform(-0.02, 0.02)) * zone_w
    bcx = cx + int(zone_w * pose["body_x"] + tilt)
    body_lean = random.uniform(-0.03, 0.03) * zone_h

    # --- body ---
    body_tier = template["body_tier"]
    if body_tier == "thin":
        body_hw = int(zone_w * random.uniform(0.08, 0.11))
        body_hh = int(zone_h * random.uniform(0.20, 0.26))
    elif body_tier == "normal":
        body_hw = int(zone_w * random.uniform(0.11, 0.15))
        body_hh = int(zone_h * random.uniform(0.17, 0.23))
    else:
        body_hw = int(zone_w * random.uniform(0.14, 0.18))
        body_hh = int(zone_h * random.uniform(0.15, 0.21))

    body_cy = cy + int(body_lean) + int(zone_h * pose["body_y"])

    # --- arms (bent, hanging, one sometimes missing) ---
    arm_w = max(line_w + 2, int(body_hw * 0.16))
    arm_len = int(body_hw * random.uniform(0.55, 0.95))
    has_both = template["arm_mode"] == "both"
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
        drag = pose["drag_leg"]
        if drag == -1:
            h = leg_h + int(asym if idx == 0 else -asym)
        elif drag == 1:
            h = leg_h + int(-asym if idx == 0 else asym)
        else:
            h = leg_h + int(asym if idx == 0 else -asym)
        fx = lx + random.randint(-4, 4)
        _draw_organic_leg(draw, lx, ly, fx, ly + h, leg_w, primary, foot_r)

    # --- body silhouette (organic shape) ---
    zombie_shape = BODY_SHAPES[template["body_shape"]]
    body_pts = _draw_filled_blob(draw, bcx, body_cy, body_hw, body_hh,
                                  secondary, primary, line_w, wobble=0.10,
                                  shape_func=zombie_shape)

    # --- stitches ---
    num_stitches = random.randint(1, 5)
    _draw_stitches(draw, bcx, body_cy, body_hw, body_hh, num_stitches, primary, line_w)

    # --- face (asymmetric) ---
    left_eye_r = max(int(min(body_hw, body_hh) * random.uniform(0.09, 0.15)), 5)
    right_eye_r = max(int(left_eye_r * random.uniform(0.50, 0.90)), 4)
    eye_y = body_cy - int(body_hh * random.uniform(0.20, 0.30))
    eye_spread = body_hw * random.uniform(0.28, 0.45)

    # one eye might be X (dead)
    dead_eye = template["eye_dead"]
    for idx, (ex, ey_off, er) in enumerate([
        (bcx - eye_spread, random.randint(-2, 2), left_eye_r),
        (bcx + eye_spread, random.randint(0, 3), right_eye_r),
    ]):
        ey = eye_y + ey_off
        eye_pts = BODY_SHAPES["round"](ex, ey, er, er, wobble=0.05)
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
    mouth_style = template["mouth_style"]
    mouth_pts = _bezier_pts((bcx - mouth_w, mouth_y + random.randint(-3, 3)),
                             (bcx, mouth_y + random.randint(-4, 4)),
                             (bcx + mouth_w, mouth_y + random.randint(-3, 3)), steps=8)
    if mouth_style == "smile":
        _draw_thick_curve(draw, mouth_pts, line_w, primary)
    else:
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
    template = _pick_template(OCTOPUS_TEMPLATES)
    pose = _pick_template(OCTOPUS_POSE_TEMPLATES)

    # --- dome ---
    dome_tier = template["dome_tier"]
    if dome_tier == "small":
        dome_rx = int(zone_w * random.uniform(0.09, 0.13))
        dome_ry = int(zone_h * random.uniform(0.09, 0.13))
    elif dome_tier == "medium":
        dome_rx = int(zone_w * random.uniform(0.13, 0.18))
        dome_ry = int(zone_h * random.uniform(0.12, 0.17))
    else:
        dome_rx = int(zone_w * random.uniform(0.18, 0.24))
        dome_ry = int(zone_h * random.uniform(0.16, 0.22))

    dome_shape = template["dome_shape"]
    if dome_shape == "wide":
        dome_rx = int(dome_rx * 1.2)
        dome_ry = int(dome_ry * 0.85)

    dome_cx = cx + int(zone_w * pose["body_x"])
    dome_cy = cy - int(zone_h * random.uniform(0.04, 0.10)) + int(zone_h * pose["body_y"])

    # --- tentacles: thick, curling ---
    n_tentacles = template["n_tentacles"]
    tent_w = max(line_w + 2, int(dome_rx * 0.15))
    tent_len_tier = template["tent_len_tier"]
    tent_spread = dome_rx * random.uniform(1.2, 1.8) * pose["fan"]
    tent_step = tent_spread / max(n_tentacles - 1, 1)
    tent_start_y = dome_cy + dome_ry - line_w

    for i in range(n_tentacles):
        tx = dome_cx - tent_spread / 2 + i * tent_step + random.uniform(-4, 4) + pose["tent_bias"] * dome_rx
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

    # --- dome silhouette (organic shape) ---
    octo_shape = BODY_SHAPES[dome_shape]
    _draw_filled_blob(draw, dome_cx, dome_cy, dome_rx, dome_ry,
                       secondary, primary, line_w, wobble=0.06,
                       shape_func=octo_shape)

    # --- face ---
    eye_r = max(int(dome_rx * random.uniform(0.14, 0.25)), 5)
    eye_y = dome_cy - int(dome_ry * random.uniform(0.02, 0.18))
    spread = dome_rx * random.uniform(0.30, 0.55)
    n_eyes = template["eye_count"]
    if n_eyes == 2:
        positions = [(dome_cx - spread, eye_y), (dome_cx + spread, eye_y)]
    else:
        positions = [(dome_cx - spread, eye_y), (dome_cx, eye_y - int(eye_r * 0.3)), (dome_cx + spread, eye_y)]
    eye_style = random.choice(["normal", "cute", "sleepy"])
    _draw_expressive_eyes(draw, positions, eye_r, primary, secondary, line_w, style=eye_style)

    mouth_y = dome_cy + int(dome_ry * random.uniform(0.25, 0.45))
    mouth_style = template["mouth_style"]
    _draw_mouth(draw, dome_cx, mouth_y, max(int(dome_rx * 0.3), 6), primary, secondary, line_w,
                style=mouth_style)

    # spots detail
    if random.random() < 0.35:
        for _ in range(random.randint(2, 5)):
            dx = dome_cx + random.randint(int(-dome_rx * 0.5), int(dome_rx * 0.5))
            dy = dome_cy + random.randint(int(-dome_ry * 0.4), int(dome_ry * 0.4))
            dr = random.randint(2, max(int(dome_rx * 0.06), 3))
            draw.ellipse([dx - dr, dy - dr, dx + dr, dy + dr], fill=primary)


def _draw_dragon_archetype(draw, cx, cy, zone_w, zone_h, primary, secondary, line_w):
    """Dragon: curved body, simple membrane wings, tail, spikes, expressive face."""
    template = _pick_template(DRAGON_TEMPLATES)
    pose = _pick_template(DRAGON_POSE_TEMPLATES)
    facing = pose["facing"]

    lean = random.uniform(-0.01, 0.01) * zone_w
    bcx = cx + int(zone_w * pose["body_x"] + lean)

    # --- body ---
    body_tier = template["body_tier"]
    if body_tier == "compact":
        body_hw = int(zone_w * random.uniform(0.10, 0.14))
        body_hh = int(zone_h * random.uniform(0.13, 0.18))
    elif body_tier == "wide":
        body_hw = int(zone_w * random.uniform(0.14, 0.20))
        body_hh = int(zone_h * random.uniform(0.12, 0.16))
    else:
        body_hw = int(zone_w * random.uniform(0.10, 0.14))
        body_hh = int(zone_h * random.uniform(0.18, 0.25))

    body_cy = cy + int(zone_h * (0.02 + pose["body_y"]))

    # --- wings (membrane with curves) ---
    wing_tier = template["wing_tier"]
    if wing_tier != "none":
        if wing_tier == "small":
            wing_w = int(zone_w * random.uniform(0.07, 0.12))
            wing_h = int(zone_h * random.uniform(0.10, 0.16))
        else:
            wing_w = int(zone_w * random.uniform(0.14, 0.22))
            wing_h = int(zone_h * random.uniform(0.18, 0.30))
        for side in (-1, 1):
            wx = bcx + side * body_hw
            wy = body_cy - int(body_hh * random.uniform(0.2, 0.4)) + int(body_hh * pose["wing_lift"])
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
    tail_tier = template["tail_tier"]
    if tail_tier == "side":
        tail_len = int(zone_w * random.uniform(0.06, 0.12))
    elif tail_tier == "long":
        tail_len = int(zone_w * random.uniform(0.14, 0.22))
    else:
        tail_len = int(zone_w * random.uniform(0.08, 0.16))
    tail_w = max(line_w + 2, int(body_hw * 0.18))
    tail_side = pose["tail_side"] if tail_tier == "side" else pose["tail_side"]
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
    n_legs = template["n_legs"]
    if n_legs == 2:
        leg_xs = [-0.20, 0.20]
    else:
        leg_xs = [-0.32, -0.10, 0.10, 0.32]
    for x_off in leg_xs:
        lx = bcx + int(body_hw * x_off) + random.randint(-2, 2)
        ly = body_cy + body_hh
        _draw_organic_leg(draw, lx, ly, lx + random.randint(-3, 3), ly + leg_h,
                         leg_w, primary, foot_r)

    # --- body silhouette (organic shape) ---
    dragon_shape = BODY_SHAPES[template["body_shape"]]
    body_pts = _draw_filled_blob(draw, bcx, body_cy, body_hw, body_hh,
                                  secondary, primary, line_w, wobble=0.07,
                                  shape_func=dragon_shape)

    # --- spikes on back ---
    spike_tier = template["spike_tier"]
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
    eye_style = template["eye_style"]
    _draw_expressive_eyes(draw,
                          [(bcx - eye_spread, eye_y), (bcx + eye_spread, eye_y)],
                          eye_r, primary, secondary, line_w, style=eye_style)

    mouth_y = body_cy + int(body_hh * random.uniform(0.12, 0.28))
    mouth_w = max(int(body_hw * random.uniform(0.30, 0.50)), 8)
    mouth_style = template["mouth_style"]
    _draw_mouth(draw, bcx, mouth_y, mouth_w, primary, secondary, line_w, style=mouth_style)


def _draw_cthulhu_archetype(draw, cx, cy, zone_w, zone_h, primary, secondary, line_w):
    """Cthulhu: large head, tentacles from mouth, soft flowing shapes, compact body."""
    template = _pick_template(CTHULHU_TEMPLATES)
    pose = _pick_template(CTHULHU_POSE_TEMPLATES)

    # --- head (oversized, cartoon) ---
    head_tier = template["head_tier"]
    if head_tier == "large":
        head_rx = int(zone_w * random.uniform(0.13, 0.18))
        head_ry = int(zone_h * random.uniform(0.15, 0.20))
    else:
        head_rx = int(zone_w * random.uniform(0.19, 0.24))
        head_ry = int(zone_h * random.uniform(0.21, 0.28))
    head_cx = cx + int(zone_w * pose["head_x"])
    head_cy = cy - int(zone_h * random.uniform(0.04, 0.10)) + int(zone_h * pose["head_y"])

    # --- body (compact, beneath head) ---
    body_hw = int(head_rx * random.uniform(0.40, 0.65))
    body_hh = int(head_ry * random.uniform(0.40, 0.60))
    body_cx = cx + int(zone_w * pose["body_x"])
    body_cy = head_cy + head_ry + body_hh - int(body_hh * random.uniform(0.10, 0.25))

    # --- wings (small, optional) ---
    if template["wings"]:
        wing_w = int(zone_w * random.uniform(0.05, 0.12))
        wing_h = int(zone_h * random.uniform(0.08, 0.16))
        for side in (-1, 1):
            wx = body_cx + side * body_hw
            wy = body_cy - int(body_hh * random.uniform(0.1, 0.3))
            tip = (wx + side * wing_w, wy - wing_h)
            bot = (wx + side * int(wing_w * 0.25), wy + int(wing_h * 0.15))
            draw.polygon([(wx, wy), tip, bot], fill=secondary, outline=primary, width=line_w)

    # --- small arms ---
    arm_w = max(line_w + 1, int(body_hw * 0.15))
    arm_len = int(body_hw * random.uniform(0.45, 0.80))
    for side in (-1, 1):
        ax = body_cx + side * body_hw
        ay = body_cy
        hand_x = ax + side * arm_len * random.uniform(0.7, 1.1)
        hand_y = ay + arm_len * random.uniform(0.3, 0.6)
        _draw_organic_limb(draw, ax, ay, hand_x, hand_y, arm_w, primary)

    # --- body silhouette (organic shape) ---
    _draw_filled_blob(draw, body_cx, body_cy, body_hw, body_hh,
                       secondary, primary, line_w, wobble=0.07,
                       shape_func=BODY_SHAPES[template["body_shape"]])

    # --- head silhouette (organic, large) ---
    _draw_filled_blob(draw, head_cx, head_cy, head_rx, head_ry,
                       secondary, primary, line_w, wobble=0.08,
                       shape_func=BODY_SHAPES[template["head_shape"]])

    # --- horns ---
    horn_h = int(head_ry * random.uniform(0.18, 0.38))
    horn_w = max(int(head_rx * 0.05), 3)
    for x_off in (-0.25, 0.25):
        hx = head_cx + int(head_rx * x_off) + random.randint(-3, 3)
        hy = head_cy - head_ry
        draw.polygon([(hx, hy - horn_h), (hx - horn_w, hy + 2), (hx + horn_w, hy + 2)], fill=primary)

    # --- face ---
    eye_r = max(int(head_rx * random.uniform(0.10, 0.17)), 5)
    eye_y = head_cy - int(head_ry * random.uniform(0.08, 0.25))
    eye_spread = head_rx * random.uniform(0.30, 0.50)
    n_eyes = template["n_eyes"]
    if n_eyes == 2:
        positions = [(head_cx - eye_spread, eye_y), (head_cx + eye_spread, eye_y)]
    elif n_eyes == 3:
        positions = [(head_cx - eye_spread, eye_y), (head_cx, eye_y - int(eye_r * 0.4)), (head_cx + eye_spread, eye_y)]
    else:
        positions = [(head_cx - eye_spread, eye_y - int(eye_r * 0.2)),
                     (head_cx + eye_spread, eye_y - int(eye_r * 0.2)),
                     (head_cx - eye_spread * 0.5, eye_y + int(eye_r * 0.3)),
                     (head_cx + eye_spread * 0.5, eye_y + int(eye_r * 0.3))]
    _draw_expressive_eyes(draw, positions, eye_r, primary, secondary, line_w,
                          style=random.choice(["normal", "angry", "sleepy"]))

    # --- mouth tentacles ---
    tent_total = template["tent_total"]
    tent_spread = head_rx * random.uniform(0.6, 1.0)
    tent_step = tent_spread / max(tent_total - 1, 1)
    tent_start_y = head_cy + int(head_ry * random.uniform(0.35, 0.55))
    tent_w = max(line_w + 1, int(head_rx * 0.06))
    tent_len_tier = template["tent_len_tier"]
    for i in range(tent_total):
        tx = head_cx - tent_spread / 2 + i * tent_step + random.uniform(-2, 2) + pose["tent_bias"] * head_rx
        if tent_len_tier == "short":
            length = int(head_ry * random.uniform(0.25, 0.45))
        else:
            length = int(head_ry * random.uniform(0.50, 0.85))
        sway = head_rx * random.uniform(0.05, 0.15)
        _curvy_tentacle(draw, tx, tent_start_y, length, sway, tent_w, primary)


def _draw_ghost_archetype(draw, cx, cy, zone_w, zone_h, primary, secondary, line_w):
    """Ghost: soft rounded top, wavy bottom, floating shape, simple expressive face."""
    template = _pick_template(GHOST_TEMPLATES)
    pose = _pick_template(GHOST_POSE_TEMPLATES)

    # --- size ---
    size_tier = template["size_tier"]
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
    gcx = cx + int(zone_w * pose["body_x"])
    gcy = cy + int(zone_h * pose["body_y"])
    ghost_pts = _ghost_outline_points(gcx, gcy, body_w, body_h)
    body_geo = _build_body_geometry(gcx, gcy, body_w, body_h, "ghost")

    # --- arms (organic curves) ---
    arm_style = template["arm_style"]
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
            y_off = random.uniform(-0.12, 0.05) + pose["arm_bias"]
            ax, ay = _body_side_anchor(body_geo, side_name, y_off, inset=arm_w)
            hand_x = ax + side * arm_len
            hand_y = ay + arm_len * random.uniform(-0.4, 0.2)
            _draw_organic_limb(draw, ax, ay, hand_x, hand_y, arm_w, primary, taper=0.5)

    # --- body fill ---
    _draw_polygon_body(draw, ghost_pts, secondary, primary, line_w)

    # --- face ---
    n_eyes = template["eye_count"]
    eye_r = max(int(min(body_w, body_h) * random.uniform(0.05, 0.10)), 5)
    eye_y = gcy - int(body_h * random.uniform(0.10, 0.22))
    hollow = random.random() < 0.55
    if n_eyes == 1:
        positions = [(gcx, eye_y)]
    else:
        spread = body_w * random.uniform(0.18, 0.30)
        if n_eyes == 2:
            positions = [(gcx - spread, eye_y + random.randint(-2, 2)),
                         (gcx + spread, eye_y + random.randint(-2, 2))]
        else:
            positions = [(gcx - spread, eye_y + random.randint(-2, 2)),
                         (gcx, eye_y - int(eye_r * 0.5)),
                         (gcx + spread, eye_y + random.randint(-2, 2))]
    _draw_expressive_eyes(draw, positions, eye_r, primary, secondary, line_w,
                          style="hollow" if hollow else random.choice(["normal", "sleepy", "cute"]))

    # mouth
    mouth_style = template["mouth_style"]
    if mouth_style != "none":
        mouth_y = gcy + int(body_h * random.uniform(0.03, 0.12))
        _draw_mouth(draw, gcx, mouth_y, max(int(body_w * 0.15), 6),
                    primary, secondary, line_w, style=mouth_style)


def _draw_default_archetype(draw, cx, cy, zone_w, zone_h, primary, secondary, line_w):
    """Default: randomized organic creature with various features."""
    template = _pick_template(DEFAULT_TEMPLATES)
    pose = _pick_template(DEFAULT_POSE_TEMPLATES)

    lean = random.uniform(-0.01, 0.01) * zone_w
    bcx = cx + int(zone_w * pose["body_x"] + lean)
    facing = pose["facing"]

    body_hw = int(zone_w * random.uniform(0.10, 0.18))
    body_hh = int(zone_h * random.uniform(0.14, 0.24))

    use_tentacles = template["use_tentacles"]
    use_arms = random.random() < 0.75
    use_wings = template["use_wings"]
    use_tail = template["use_tail"]
    use_horns = template["use_horns"]
    n_legs = template["n_legs"] if not use_tentacles else 0

    body_cy = cy + int(zone_h * (0.02 + pose["body_y"]))

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
        tail_side = facing
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

    # body (organic shape)
    default_shape = BODY_SHAPES[template["body_shape"]]
    body_pts = _draw_filled_blob(draw, bcx, body_cy, body_hw, body_hh,
                                  secondary, primary, line_w, wobble=0.10,
                                  shape_func=default_shape)

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
    n_eyes = template["eye_count"]
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
                style=template["mouth_style"])


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

        # Render monster at 2x resolution for smooth anti-aliased edges
        ss = 2
        monster_img = Image.new("RGB",
                                (width * ss, monster_zone_h * ss),
                                secondary_color)
        monster_draw = ImageDraw.Draw(monster_img)
        drawer = ARCHETYPE_DRAWERS[archetype]
        drawer(monster_draw,
               (width // 2) * ss, (monster_zone_h // 2) * ss,
               width * ss, monster_zone_h * ss,
               primary_color, secondary_color, line_w * ss)
        monster_img = monster_img.resize((width, monster_zone_h), Image.LANCZOS)
        image.paste(monster_img, (0, title_zone_h))

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
