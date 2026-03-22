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

BODY_SHAPES = ["round", "oval", "blob", "rounded_rect", "squared"]
MOUTH_STYLES = ["smile", "open", "small", "big", "teeth"]
HORN_SHAPES = ["triangle", "curved"]
ARCHETYPE_ORDER = [
    "zombie",
    "werewolf",
    "octopus",
    "dragon",
    "spider",
    "dinosaur",
    "cthulhu",
    "ghost",
    "default",
]

ARCHETYPES = {
    "zombie": {
        "body_shapes": ["round", "rounded_rect", "squared"],
        "eyes": [1, 2],
        "mouth_styles": ["open", "small"],
        "horns": [0],
        "arm_styles": ["normal", "short"],
        "body_width": (0.40, 0.48),
        "body_height": (0.52, 0.62),
        "extras": [],
    },
    "werewolf": {
        "body_shapes": ["oval", "blob"],
        "eyes": [2],
        "mouth_styles": ["teeth"],
        "horns": [0],
        "arm_styles": ["raised", "normal"],
        "body_width": (0.38, 0.46),
        "body_height": (0.54, 0.64),
        "extras": ["ears"],
    },
    "octopus": {
        "body_shapes": ["round", "blob"],
        "eyes": [1, 2, 3],
        "mouth_styles": ["smile", "small", "open"],
        "horns": [0],
        "arm_styles": ["none"],
        "body_width": (0.36, 0.46),
        "body_height": (0.44, 0.54),
        "extras": ["tentacles_only"],
    },
    "dragon": {
        "body_shapes": ["oval", "rounded_rect", "blob"],
        "eyes": [1, 2],
        "mouth_styles": ["smile", "open", "teeth"],
        "horns": [1, 2],
        "arm_styles": ["short", "normal"],
        "body_width": (0.42, 0.52),
        "body_height": (0.50, 0.60),
        "extras": ["wings", "tail"],
    },
    "spider": {
        "body_shapes": ["round", "oval"],
        "eyes": [2, 3],
        "mouth_styles": ["small", "open"],
        "horns": [0],
        "arm_styles": ["none"],
        "body_width": (0.26, 0.34),
        "body_height": (0.28, 0.38),
        "extras": ["spider_legs"],
    },
    "dinosaur": {
        "body_shapes": ["oval", "rounded_rect", "blob"],
        "eyes": [1, 2],
        "mouth_styles": ["smile", "open"],
        "horns": [0, 1],
        "arm_styles": ["short"],
        "body_width": (0.44, 0.54),
        "body_height": (0.50, 0.62),
        "extras": ["tail"],
    },
    "cthulhu": {
        "body_shapes": ["blob", "oval"],
        "eyes": [2, 3],
        "mouth_styles": ["small", "open"],
        "horns": [0, 1],
        "arm_styles": ["normal"],
        "body_width": (0.40, 0.50),
        "body_height": (0.52, 0.62),
        "extras": ["face_tentacles", "dots"],
    },
    "ghost": {
        "body_shapes": ["ghost"],
        "eyes": [1, 2],
        "mouth_styles": ["small", "open", "smile"],
        "horns": [0],
        "arm_styles": ["short", "raised"],
        "body_width": (0.36, 0.46),
        "body_height": (0.56, 0.66),
        "extras": [],
    },
    "default": {
        "body_shapes": BODY_SHAPES,
        "eyes": [1, 2, 3],
        "mouth_styles": MOUTH_STYLES,
        "horns": [0, 1, 2],
        "arm_styles": ["short", "raised", "normal"],
        "body_width": (0.38, 0.50),
        "body_height": (0.52, 0.65),
        "extras": ["wings", "tail", "spots", "dots"],
    },
}


def generate_monster_name():
    """Generate a short playful monster name (1-3 syllables)."""
    count = random.choices([1, 2, 3], weights=[25, 50, 25])[0]
    parts = random.sample(SYLLABLES, count)
    return "".join(parts).capitalize()


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


def _draw_body(draw, body_geometry, fill, outline, line_w):
    draw.polygon(body_geometry["points"], fill=fill, outline=outline, width=line_w)


def _draw_eyes(draw, cx, cy, body_w, body_h, num_eyes, primary, secondary, line_w, archetype):
    eye_zone_y = cy - int(body_h * 0.16)
    eye_zone_w = body_w * (0.48 if archetype == "spider" else 0.52)
    base_radius = max(int(min(body_w, body_h) * 0.08), 6)

    if num_eyes == 1:
        positions = [(cx, eye_zone_y)]
    else:
        spacing = eye_zone_w / max(num_eyes - 1, 1)
        start_x = cx - eye_zone_w / 2
        positions = [(start_x + index * spacing, eye_zone_y) for index in range(num_eyes)]

    for ex, ey in positions:
        if archetype == "spider":
            radius = max(int(base_radius * 0.72), 5)
        elif archetype == "zombie":
            radius = random.randint(int(base_radius * 0.80), int(base_radius * 1.20))
        else:
            radius = random.randint(int(base_radius * 0.85), int(base_radius * 1.15))
        draw.ellipse([ex - radius, ey - radius, ex + radius, ey + radius], fill=secondary, outline=primary, width=line_w)
        pupil_radius = max(radius // 3, 2)
        offset_range = 0 if archetype == "zombie" else max(pupil_radius // 2, 1)
        px = ex + random.randint(-offset_range, offset_range)
        py = ey + random.randint(-offset_range, offset_range)
        draw.ellipse([px - pupil_radius, py - pupil_radius, px + pupil_radius, py + pupil_radius], fill=primary)

        if archetype in {"werewolf", "dragon", "cthulhu"}:
            brow_y = ey - radius - line_w
            tilt = radius // 2
            if ex < cx:
                draw.line([(ex - radius, brow_y + tilt), (ex + radius, brow_y)], fill=primary, width=max(line_w, 2))
            else:
                draw.line([(ex - radius, brow_y), (ex + radius, brow_y + tilt)], fill=primary, width=max(line_w, 2))
        elif archetype == "ghost":
            draw.arc([ex - radius, ey - radius - 2, ex + radius, ey + radius], start=200, end=340, fill=primary, width=max(line_w - 1, 1))


def _draw_mouth(draw, cx, cy, body_w, body_h, style, primary, secondary, line_w, archetype):
    mouth_y = cy + int(body_h * (0.16 if archetype == "spider" else 0.20))
    mouth_w = max(random.randint(int(body_w * 0.10), int(body_w * 0.20)), 7)

    if archetype == "zombie":
        style = "open"
    elif archetype == "werewolf":
        style = "teeth"
    elif archetype == "dragon" and style == "smile":
        style = random.choice(["open", "teeth"])
    elif archetype == "ghost" and style == "open":
        style = random.choice(["small", "smile"])
    elif archetype == "spider":
        style = "small"

    if style == "smile":
        draw.arc([cx - mouth_w, mouth_y - mouth_w // 2, cx + mouth_w, mouth_y + mouth_w // 2], start=0, end=180, fill=primary, width=line_w)
    elif style == "open":
        radius_y = max(mouth_w * 2 // 3, 5)
        draw.ellipse([cx - mouth_w, mouth_y - radius_y, cx + mouth_w, mouth_y + radius_y], fill=primary)
    elif style == "small":
        radius = max(mouth_w // 3, 4)
        draw.ellipse([cx - radius, mouth_y - radius, cx + radius, mouth_y + radius], fill=primary)
    elif style == "big":
        draw.arc([cx - mouth_w, mouth_y - mouth_w, cx + mouth_w, mouth_y + mouth_w], start=0, end=180, fill=primary, width=line_w + 1)
    elif style == "teeth":
        draw.arc([cx - mouth_w, mouth_y - mouth_w // 2, cx + mouth_w, mouth_y + mouth_w // 2], start=0, end=180, fill=primary, width=line_w)
        tooth_w = max(mouth_w // 3, 4)
        tooth_h = max(mouth_w // 4, 3)
        total_teeth = 3 if archetype == "werewolf" else random.randint(2, 4)
        total_width = total_teeth * tooth_w + (total_teeth - 1) * 2
        start_x = cx - total_width // 2
        for index in range(total_teeth):
            tooth_x = start_x + index * (tooth_w + 2)
            draw.rectangle([tooth_x, mouth_y - 1, tooth_x + tooth_w, mouth_y + tooth_h], fill=secondary, outline=primary, width=max(line_w - 1, 1))


def _draw_horns(draw, body_geometry, total_horns, shape, primary, line_w):
    if total_horns <= 0:
        return

    body_h = body_geometry["body_h"]
    body_w = body_geometry["body_w"]
    horn_h = random.randint(int(body_h * 0.16), int(body_h * 0.26))
    horn_w = max(random.randint(int(body_w * 0.04), int(body_w * 0.07)), 4)

    if total_horns == 1:
        x_ratios = [0.0]
    else:
        spread = 0.42
        step = spread / max(total_horns - 1, 1)
        x_ratios = [(-spread / 2) + index * step for index in range(total_horns)]

    for x_ratio in x_ratios:
        anchor_x, anchor_y = _body_vertical_anchor(body_geometry, "top", x_ratio, inset=max(line_w, 2))
        if shape == "triangle":
            draw.polygon(
                [(anchor_x, anchor_y - horn_h), (anchor_x - horn_w, anchor_y + line_w), (anchor_x + horn_w, anchor_y + line_w)],
                fill=primary,
            )
        else:
            direction = random.choice([-1, 1])
            draw.polygon(
                [
                    (anchor_x + direction * horn_w, anchor_y - horn_h),
                    (anchor_x - horn_w, anchor_y + line_w),
                    (anchor_x + horn_w, anchor_y + line_w),
                ],
                fill=primary,
            )


def _draw_ears(draw, body_geometry, primary, secondary, line_w):
    body_h = body_geometry["body_h"]
    body_w = body_geometry["body_w"]
    ear_h = max(int(body_h * 0.18), 12)
    ear_w = max(int(body_w * 0.09), 10)
    for direction, x_ratio in ((-1, -0.24), (1, 0.24)):
        ear_x, ear_y = _body_vertical_anchor(body_geometry, "top", x_ratio, inset=max(line_w, 2))
        points = [
            (ear_x, ear_y - ear_h),
            (ear_x - direction * ear_w, ear_y + line_w),
            (ear_x + direction * (ear_w // 3), ear_y + line_w),
        ]
        draw.polygon(points, fill=secondary, outline=primary, width=line_w)


def _draw_fingers(draw, hand_x, hand_y, angle, total_fingers, finger_len, style, primary, line_w):
    spread = math.pi * 0.50
    start_angle = angle - spread / 2
    for index in range(total_fingers):
        finger_angle = start_angle + (spread / max(total_fingers - 1, 1)) * index if total_fingers > 1 else angle
        tip_x = hand_x + finger_len * math.cos(finger_angle)
        tip_y = hand_y + finger_len * math.sin(finger_angle)
        draw.line([(hand_x, hand_y), (tip_x, tip_y)], fill=primary, width=line_w)
        if style == "rounded":
            radius = max(line_w, 2)
            draw.ellipse([tip_x - radius, tip_y - radius, tip_x + radius, tip_y + radius], fill=primary)


def _draw_arms(draw, body_geometry, arm_style, primary, line_w, small=False, finger_style=None):
    if arm_style == "none":
        return

    body_w = body_geometry["body_w"]
    arm_len = random.randint(int(body_w * (0.10 if small else 0.16)), int(body_w * (0.16 if small else 0.26)))
    arm_w = line_w + 2
    finger_style = finger_style or random.choice(["rounded", "claw"])
    finger_len = max(arm_len // 4, 6)
    total_fingers = random.randint(2, 4)
    y_ratio = -0.02

    if arm_style == "short":
        left_anchor = _body_side_anchor(body_geometry, "left", y_ratio, inset=arm_w)
        right_anchor = _body_side_anchor(body_geometry, "right", y_ratio, inset=arm_w)
        ends = [(left_anchor[0] - arm_len, left_anchor[1], math.pi), (right_anchor[0] + arm_len, right_anchor[1], 0)]
        draw.line([left_anchor, ends[0][:2]], fill=primary, width=arm_w)
        draw.line([right_anchor, ends[1][:2]], fill=primary, width=arm_w)
    elif arm_style == "raised":
        delta_y = arm_len * 0.65
        left_anchor = _body_side_anchor(body_geometry, "left", y_ratio, inset=arm_w)
        right_anchor = _body_side_anchor(body_geometry, "right", y_ratio, inset=arm_w)
        ends = [
            (left_anchor[0] - arm_len, left_anchor[1] - delta_y, math.pi + 0.45),
            (right_anchor[0] + arm_len, right_anchor[1] - delta_y, -0.45),
        ]
        draw.line([left_anchor, ends[0][:2]], fill=primary, width=arm_w)
        draw.line([right_anchor, ends[1][:2]], fill=primary, width=arm_w)
    else:
        delta_y = arm_len * 0.30
        left_anchor = _body_side_anchor(body_geometry, "left", y_ratio, inset=arm_w)
        right_anchor = _body_side_anchor(body_geometry, "right", y_ratio, inset=arm_w)
        ends = [
            (left_anchor[0] - arm_len, left_anchor[1] + delta_y, math.pi - 0.25),
            (right_anchor[0] + arm_len, right_anchor[1] + delta_y, 0.25),
        ]
        draw.line([left_anchor, ends[0][:2]], fill=primary, width=arm_w)
        draw.line([right_anchor, ends[1][:2]], fill=primary, width=arm_w)

    for hand_x, hand_y, angle in ends:
        _draw_fingers(draw, hand_x, hand_y, angle, total_fingers, finger_len, finger_style, primary, line_w)


def _draw_leg_columns(draw, body_geometry, primary, line_w, total_legs=None):
    body_h = body_geometry["body_h"]
    leg_h = random.randint(int(body_h * 0.18), int(body_h * 0.28))
    total_legs = total_legs or random.choices([2, 3, 4], weights=[60, 20, 20])[0]
    leg_w = line_w + 3
    foot_r = max(leg_w + 1, 5)
    spread = 0.52

    if total_legs == 2:
        x_ratios = [-spread / 2, spread / 2]
    else:
        step = spread / max(total_legs - 1, 1)
        x_ratios = [(-spread / 2) + index * step for index in range(total_legs)]

    for x_ratio in x_ratios:
        leg_x, leg_y = _body_vertical_anchor(body_geometry, "bottom", x_ratio, inset=leg_w)
        draw.line([(leg_x, leg_y), (leg_x, leg_y + leg_h)], fill=primary, width=leg_w)
        draw.ellipse([leg_x - foot_r, leg_y + leg_h - foot_r // 2, leg_x + foot_r, leg_y + leg_h + foot_r], fill=primary)


def _draw_bottom_tentacles(draw, body_geometry, primary, line_w, total=None):
    body_w = body_geometry["body_w"]
    body_h = body_geometry["body_h"]
    total = total or random.randint(3, 5)
    spread = 0.72
    step = spread / max(total - 1, 1)
    tent_w = line_w + 2

    for index in range(total):
        x_ratio = (-spread / 2) + index * step
        tx, start_y = _body_vertical_anchor(body_geometry, "bottom", x_ratio, inset=tent_w)
        length = random.randint(int(body_h * 0.20), int(body_h * 0.36))
        sway = random.uniform(-body_w * 0.07, body_w * 0.07)
        points = [
            (tx, start_y),
            (tx + sway, start_y + length * 0.33),
            (tx - sway * 0.5, start_y + length * 0.66),
            (tx + sway * 0.2, start_y + length),
        ]
        for point_index in range(len(points) - 1):
            draw.line([points[point_index], points[point_index + 1]], fill=primary, width=tent_w)
        end_x, end_y = points[-1]
        radius = max(tent_w, 3)
        draw.ellipse([end_x - radius, end_y - radius, end_x + radius, end_y + radius], fill=primary)


def _draw_face_tentacles(draw, cx, cy, body_w, body_h, primary, line_w):
    total = random.randint(4, 6)
    mouth_y = cy + int(body_h * 0.10)
    spread = body_w * 0.34
    step = spread / max(total - 1, 1)
    start_x = cx - spread / 2
    tent_w = line_w + 1

    for index in range(total):
        tx = start_x + index * step
        length = random.randint(int(body_h * 0.10), int(body_h * 0.18))
        sway = random.uniform(-body_w * 0.04, body_w * 0.04)
        end_x = tx + sway
        end_y = mouth_y + length
        draw.line([(tx, mouth_y), (end_x, end_y)], fill=primary, width=tent_w)
        radius = max(tent_w, 2)
        draw.ellipse([end_x - radius, end_y - radius, end_x + radius, end_y + radius], fill=primary)


def _draw_spider_legs(draw, body_geometry, primary, line_w):
    total_pairs = 4
    leg_w = line_w + 1
    body_w = body_geometry["body_w"]
    body_h = body_geometry["body_h"]
    y_offsets = [-0.20, -0.05, 0.10, 0.24]
    lengths = [0.26, 0.30, 0.28, 0.24]

    for direction in (-1, 1):
        for index in range(total_pairs):
            anchor_x, anchor_y = _body_side_anchor(
                body_geometry,
                "left" if direction < 0 else "right",
                y_offsets[index],
                inset=leg_w,
            )
            joint_x = anchor_x + direction * int(body_w * lengths[index])
            joint_y = anchor_y + int(body_h * (0.05 if index < 2 else 0.16))
            end_x = joint_x + direction * int(body_w * 0.16)
            end_y = joint_y + int(body_h * (0.04 if index < 2 else 0.10))
            draw.line([(anchor_x, anchor_y), (joint_x, joint_y)], fill=primary, width=leg_w)
            draw.line([(joint_x, joint_y), (end_x, end_y)], fill=primary, width=leg_w)


def _draw_extras(draw, body_geometry, primary, line_w, features):
    cx = body_geometry["cx"]
    cy = body_geometry["cy"]
    body_w = body_geometry["body_w"]
    body_h = body_geometry["body_h"]
    if "wings" in features:
        wing_w = random.randint(int(body_w * 0.12), int(body_w * 0.18))
        wing_h = random.randint(int(body_h * 0.18), int(body_h * 0.26))
        left_anchor = _body_side_anchor(body_geometry, "left", -0.10, inset=line_w + 1)
        right_anchor = _body_side_anchor(body_geometry, "right", -0.10, inset=line_w + 1)
        draw.polygon(
            [left_anchor, (left_anchor[0] - wing_w, left_anchor[1] - wing_h), (left_anchor[0] - wing_w // 4, left_anchor[1] + wing_h // 5)],
            outline=primary,
            width=line_w,
        )
        draw.polygon(
            [right_anchor, (right_anchor[0] + wing_w, right_anchor[1] - wing_h), (right_anchor[0] + wing_w // 4, right_anchor[1] + wing_h // 5)],
            outline=primary,
            width=line_w,
        )

    if "tail" in features:
        side = random.choice([-1, 1])
        tail_len = random.randint(int(body_w * 0.14), int(body_w * 0.24))
        anchor_x, anchor_y = _body_side_anchor(body_geometry, "left" if side < 0 else "right", 0.22, inset=line_w + 1)
        mid_x = anchor_x + side * tail_len * 0.55
        mid_y = anchor_y + body_h * 0.10
        end_x = mid_x + side * tail_len * 0.45
        end_y = mid_y + body_h * 0.06
        draw.line([(anchor_x, anchor_y), (mid_x, mid_y)], fill=primary, width=line_w)
        draw.line([(mid_x, mid_y), (end_x, end_y)], fill=primary, width=line_w)

    if "spots" in features:
        for _ in range(random.randint(2, 4)):
            spot_x, spot_y = _sample_point_in_body(body_geometry, (-0.24, 0.24), (-0.15, 0.18))
            spot_r = random.randint(3, max(int(body_w * 0.04), 4))
            draw.ellipse([spot_x - spot_r, spot_y - spot_r, spot_x + spot_r, spot_y + spot_r], fill=primary)

    if "dots" in features:
        for _ in range(random.randint(3, 6)):
            dot_x, dot_y = _sample_point_in_body(body_geometry, (-0.28, 0.28), (-0.18, 0.20))
            dot_r = random.randint(2, max(int(body_w * 0.025), 3))
            draw.ellipse([dot_x - dot_r, dot_y - dot_r, dot_x + dot_r, dot_y + dot_r], fill=primary)


def _build_monster_spec(width, monster_zone_h):
    archetype = random.choice(ARCHETYPE_ORDER)
    config = ARCHETYPES[archetype]
    body_width_min, body_width_max = config["body_width"]
    body_height_min, body_height_max = config["body_height"]

    features = set(config["extras"])
    if archetype == "default":
        for feature in ("wings", "tail", "spots", "dots"):
            if random.random() < 0.35:
                features.add(feature)
    elif archetype not in {"dragon", "dinosaur", "spider", "octopus", "cthulhu"}:
        for feature in ("spots", "dots"):
            if random.random() < 0.25:
                features.add(feature)

    spec = {
        "archetype": archetype,
        "body_shape": random.choice(config["body_shapes"]),
        "body_w": random.randint(int(width * body_width_min), int(width * body_width_max)),
        "body_h": random.randint(int(monster_zone_h * body_height_min), int(monster_zone_h * body_height_max)),
        "eyes": random.choice(config["eyes"]),
        "mouth_style": random.choice(config["mouth_styles"]),
        "horns": random.choice(config["horns"]),
        "horn_shape": random.choice(HORN_SHAPES),
        "arm_style": random.choice(config["arm_styles"]),
        "features": features,
    }

    if archetype == "werewolf":
        spec["finger_style"] = "claw"
    elif archetype == "zombie":
        spec["finger_style"] = "rounded"
    else:
        spec["finger_style"] = random.choice(["rounded", "claw"])

    return spec


def _build_monster_spec_for_mode(archetype_mode, width, monster_zone_h):
    selected_mode = archetype_mode or "random"
    if selected_mode not in ARCHETYPES and selected_mode != "random":
        selected_mode = "random"

    if selected_mode == "random":
        return _build_monster_spec(width, monster_zone_h)

    config = ARCHETYPES[selected_mode]
    body_width_min, body_width_max = config["body_width"]
    body_height_min, body_height_max = config["body_height"]

    features = set(config["extras"])
    if selected_mode == "default":
        for feature in ("wings", "tail", "spots", "dots"):
            if random.random() < 0.35:
                features.add(feature)
    elif selected_mode not in {"dragon", "dinosaur", "spider", "octopus", "cthulhu"}:
        for feature in ("spots", "dots"):
            if random.random() < 0.25:
                features.add(feature)

    spec = {
        "archetype": selected_mode,
        "body_shape": random.choice(config["body_shapes"]),
        "body_w": random.randint(int(width * body_width_min), int(width * body_width_max)),
        "body_h": random.randint(int(monster_zone_h * body_height_min), int(monster_zone_h * body_height_max)),
        "eyes": random.choice(config["eyes"]),
        "mouth_style": random.choice(config["mouth_styles"]),
        "horns": random.choice(config["horns"]),
        "horn_shape": random.choice(HORN_SHAPES),
        "arm_style": random.choice(config["arm_styles"]),
        "features": features,
    }

    if selected_mode == "werewolf":
        spec["finger_style"] = "claw"
    elif selected_mode == "zombie":
        spec["finger_style"] = "rounded"
    else:
        spec["finger_style"] = random.choice(["rounded", "claw"])

    return spec


class TinyMonsters(BasePlugin):
    """Generate cute, readable monsters with archetype-guided structure."""

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
            draw.text((width // 2, title_zone_h // 2), "Tiny Monsters", font=title_font, fill=primary_color, anchor="mm")

        monster_name = generate_monster_name()
        spec = _build_monster_spec_for_mode(archetype_mode, width, monster_zone_h)
        archetype = spec["archetype"]
        body_geometry = _build_body_geometry(monster_cx, monster_cy, spec["body_w"], spec["body_h"], spec["body_shape"])

        _draw_extras(draw, body_geometry, primary_color, line_w, spec["features"])

        if archetype == "spider":
            _draw_spider_legs(draw, body_geometry, primary_color, line_w)
        elif archetype == "octopus":
            _draw_bottom_tentacles(draw, body_geometry, primary_color, line_w, total=random.randint(4, 5))
        elif archetype == "ghost":
            pass
        else:
            _draw_leg_columns(
                draw,
                body_geometry,
                primary_color,
                line_w,
                total_legs=4 if archetype == "dragon" and random.random() < 0.4 else None,
            )

        if archetype == "cthulhu":
            _draw_arms(draw, body_geometry, "normal", primary_color, line_w, small=True, finger_style="claw")
        elif spec["arm_style"] != "none":
            _draw_arms(
                draw,
                body_geometry,
                spec["arm_style"],
                primary_color,
                line_w,
                small=archetype == "dinosaur",
                finger_style=spec["finger_style"],
            )

        _draw_body(draw, body_geometry, secondary_color, primary_color, line_w)

        if archetype == "werewolf":
            _draw_ears(draw, body_geometry, primary_color, secondary_color, line_w)

        _draw_horns(draw, body_geometry, spec["horns"], spec["horn_shape"], primary_color, line_w)
        _draw_eyes(draw, monster_cx, monster_cy, spec["body_w"], spec["body_h"], spec["eyes"], primary_color, secondary_color, line_w, archetype)
        _draw_mouth(draw, monster_cx, monster_cy, spec["body_w"], spec["body_h"], spec["mouth_style"], primary_color, secondary_color, line_w, archetype)

        if archetype == "cthulhu":
            _draw_face_tentacles(draw, monster_cx, monster_cy, spec["body_w"], spec["body_h"], primary_color, line_w)

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
