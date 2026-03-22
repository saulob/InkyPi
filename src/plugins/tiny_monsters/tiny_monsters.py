import random
import math
import logging

from plugins.base_plugin.base_plugin import BasePlugin
from utils.app_utils import get_font
from PIL import Image, ImageColor, ImageDraw

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Name generation – short 1-3 syllable playful names
# ---------------------------------------------------------------------------
SYLLABLES = [
    "zo", "ki", "mu", "bo", "lu", "ga", "ri", "po", "ne", "da",
    "fi", "to", "bi", "go", "nu", "ka", "mi", "ro", "le", "su",
    "ba", "di", "fu", "ko", "na", "pi", "ta", "wo", "ze", "hu",
    "blo", "gri", "dro", "fli", "snu", "kra", "plu", "tri", "glo", "spi",
    "bru", "cho", "qui", "shi", "whi", "thu", "ska", "twi", "fra", "slo",
]


def generate_monster_name():
    """Generate a short playful monster name (1-3 syllables)."""
    count = random.choices([1, 2, 3], weights=[25, 50, 25])[0]
    parts = random.sample(SYLLABLES, count)
    name = "".join(parts).capitalize()
    return name


# ---------------------------------------------------------------------------
# Body shapes
# ---------------------------------------------------------------------------
BODY_SHAPES = ["round", "oval", "blob", "rounded_rect", "squared"]
MOUTH_STYLES = ["smile", "open", "small", "big", "teeth"]
HORN_SHAPES = ["triangle", "curved"]


def _smooth_blob_points(cx, cy, rx, ry, num_points=48):
    """Generate smooth blob outline with gentle deformation."""
    # Pre-generate deformation offsets and smooth them
    raw = [random.uniform(0.90, 1.10) for _ in range(num_points)]
    # Simple averaging pass for smoothness
    smoothed = [
        (raw[(i - 1) % num_points] + raw[i] + raw[(i + 1) % num_points]) / 3
        for i in range(num_points)
    ]
    points = []
    for i in range(num_points):
        angle = (2 * math.pi * i) / num_points
        r_x = rx * smoothed[i]
        r_y = ry * smoothed[i]
        points.append((cx + r_x * math.cos(angle), cy + r_y * math.sin(angle)))
    return points


def _draw_body(draw, cx, cy, body_w, body_h, shape, fill, outline, line_w):
    """Draw the monster body – always the central anchor."""
    hw, hh = body_w // 2, body_h // 2
    if shape == "round":
        r = min(hw, hh)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                     fill=fill, outline=outline, width=line_w)
    elif shape == "oval":
        draw.ellipse([cx - hw, cy - hh, cx + hw, cy + hh],
                     fill=fill, outline=outline, width=line_w)
    elif shape == "blob":
        pts = _smooth_blob_points(cx, cy, hw, hh)
        draw.polygon(pts, fill=fill, outline=outline, width=line_w)
    elif shape == "rounded_rect":
        corner_r = min(hw, hh) // 3
        draw.rounded_rectangle([cx - hw, cy - hh, cx + hw, cy + hh],
                               radius=corner_r, fill=fill, outline=outline, width=line_w)
    elif shape == "squared":
        corner_r = min(hw, hh) // 8
        draw.rounded_rectangle([cx - hw, cy - hh, cx + hw, cy + hh],
                               radius=corner_r, fill=fill, outline=outline, width=line_w)


# ---------------------------------------------------------------------------
# Eyes – always inside the body
# ---------------------------------------------------------------------------
def _draw_eyes(draw, cx, cy, body_w, body_h, num_eyes, primary, secondary, line_w):
    eye_zone_y = cy - int(body_h * 0.15)
    eye_zone_w = body_w * 0.55

    # Consistent base eye size for this monster
    base_r = int(min(body_w, body_h) * 0.10)
    base_r = max(base_r, 6)

    if num_eyes == 1:
        positions = [(cx, eye_zone_y)]
    else:
        spacing = eye_zone_w / max(num_eyes - 1, 1)
        start_x = cx - eye_zone_w / 2
        positions = [(start_x + i * spacing, eye_zone_y) for i in range(num_eyes)]

    for ex, ey in positions:
        er = random.randint(int(base_r * 0.8), int(base_r * 1.2))
        # Eye sclera
        draw.ellipse([ex - er, ey - er, ex + er, ey + er],
                     fill=secondary, outline=primary, width=line_w)
        # Pupil
        pr = max(er // 3, 2)
        px = ex + random.randint(-pr // 2, pr // 2)
        py = ey + random.randint(-pr // 2, pr // 2)
        draw.ellipse([px - pr, py - pr, px + pr, py + pr], fill=primary)


# ---------------------------------------------------------------------------
# Mouth – always centered on body
# ---------------------------------------------------------------------------
def _draw_mouth(draw, cx, cy, body_w, body_h, style, primary, secondary, line_w):
    mouth_y = cy + int(body_h * 0.18)
    mouth_w = random.randint(int(body_w * 0.10), int(body_w * 0.22))
    mouth_w = max(mouth_w, 6)

    if style == "smile":
        draw.arc([cx - mouth_w, mouth_y - mouth_w // 2,
                  cx + mouth_w, mouth_y + mouth_w // 2],
                 start=0, end=180, fill=primary, width=line_w)
    elif style == "open":
        ry = max(mouth_w * 2 // 3, 4)
        draw.ellipse([cx - mouth_w, mouth_y - ry, cx + mouth_w, mouth_y + ry],
                     fill=primary)
    elif style == "small":
        r = max(mouth_w // 3, 4)
        draw.ellipse([cx - r, mouth_y - r, cx + r, mouth_y + r], fill=primary)
    elif style == "big":
        draw.arc([cx - mouth_w, mouth_y - mouth_w,
                  cx + mouth_w, mouth_y + mouth_w],
                 start=0, end=180, fill=primary, width=line_w + 1)
    elif style == "teeth":
        draw.arc([cx - mouth_w, mouth_y - mouth_w // 2,
                  cx + mouth_w, mouth_y + mouth_w // 2],
                 start=0, end=180, fill=primary, width=line_w)
        tooth_w = max(mouth_w // 3, 4)
        tooth_h = max(mouth_w // 4, 3)
        num_teeth = random.randint(2, 4)
        total_tw = num_teeth * tooth_w + (num_teeth - 1) * 2
        sx = cx - total_tw // 2
        for i in range(num_teeth):
            tx = sx + i * (tooth_w + 2)
            draw.rectangle([tx, mouth_y - 1, tx + tooth_w, mouth_y + tooth_h],
                           fill=secondary, outline=primary, width=max(line_w - 1, 1))


# ---------------------------------------------------------------------------
# Horns – attached to top of body
# ---------------------------------------------------------------------------
def _draw_horns(draw, cx, cy, body_w, body_h, num_horns, shape, primary, line_w):
    if num_horns == 0:
        return
    top_y = cy - body_h // 2
    horn_h = random.randint(int(body_h * 0.18), int(body_h * 0.30))

    # Evenly spread across top
    spread = body_w * 0.45
    if num_horns == 1:
        positions = [cx]
    else:
        spacing = spread / max(num_horns - 1, 1)
        positions = [cx - spread / 2 + i * spacing for i in range(num_horns)]

    hw = random.randint(int(body_w * 0.04), int(body_w * 0.07))
    hw = max(hw, 4)

    for hx in positions:
        if shape == "triangle":
            draw.polygon([(hx, top_y - horn_h),
                          (hx - hw, top_y + line_w),
                          (hx + hw, top_y + line_w)],
                         fill=primary)
        elif shape == "curved":
            direction = random.choice([-1, 1])
            draw.polygon([(hx + direction * hw, top_y - horn_h),
                          (hx - hw, top_y + line_w),
                          (hx + hw, top_y + line_w)],
                         fill=primary)


# ---------------------------------------------------------------------------
# Fingers / claws helper
# ---------------------------------------------------------------------------
def _draw_fingers(draw, hx, hy, angle, num_fingers, finger_len, style, primary, line_w):
    """Draw fingers or claws radiating from hand position."""
    spread = math.pi * 0.5  # total angular spread
    start_angle = angle - spread / 2
    for i in range(num_fingers):
        a = start_angle + (spread / max(num_fingers - 1, 1)) * i if num_fingers > 1 else angle
        fx = hx + finger_len * math.cos(a)
        fy = hy + finger_len * math.sin(a)
        draw.line([(hx, hy), (fx, fy)], fill=primary, width=line_w)
        if style == "rounded":
            r = max(line_w, 2)
            draw.ellipse([fx - r, fy - r, fx + r, fy + r], fill=primary)


# ---------------------------------------------------------------------------
# Arms – attached to body sides, consistent thickness
# ---------------------------------------------------------------------------
def _draw_arms(draw, cx, cy, body_w, body_h, arm_style, primary, secondary, line_w):
    if arm_style == "none":
        return

    left_x = cx - body_w // 2
    right_x = cx + body_w // 2
    arm_len = random.randint(int(body_w * 0.15), int(body_w * 0.28))
    arm_w = line_w + 2

    num_fingers = random.randint(2, 4)
    finger_len = max(arm_len // 4, 6)
    finger_style = random.choice(["rounded", "claw"])

    if arm_style == "short":
        ends = [(left_x - arm_len, cy, math.pi),
                (right_x + arm_len, cy, 0)]
        draw.line([(left_x, cy), (left_x - arm_len, cy)], fill=primary, width=arm_w)
        draw.line([(right_x, cy), (right_x + arm_len, cy)], fill=primary, width=arm_w)
    elif arm_style == "raised":
        dy = arm_len * 0.7
        ends = [(left_x - arm_len, cy - dy, math.pi + 0.5),
                (right_x + arm_len, cy - dy, -0.5)]
        draw.line([(left_x, cy), (left_x - arm_len, cy - dy)], fill=primary, width=arm_w)
        draw.line([(right_x, cy), (right_x + arm_len, cy - dy)], fill=primary, width=arm_w)
    elif arm_style == "normal":
        dy = arm_len * 0.35
        ends = [(left_x - arm_len, cy + dy, math.pi - 0.3),
                (right_x + arm_len, cy + dy, 0.3)]
        draw.line([(left_x, cy), (left_x - arm_len, cy + dy)], fill=primary, width=arm_w)
        draw.line([(right_x, cy), (right_x + arm_len, cy + dy)], fill=primary, width=arm_w)
    else:
        return

    for hx, hy, angle in ends:
        _draw_fingers(draw, hx, hy, angle, num_fingers, finger_len, finger_style, primary, line_w)


# ---------------------------------------------------------------------------
# Tentacles – optional octopus-style limbs
# ---------------------------------------------------------------------------
def _draw_tentacles(draw, cx, cy, body_w, body_h, primary, line_w):
    num = random.randint(2, 5)
    bottom_y = cy + body_h // 2
    spread = body_w * 0.7
    spacing = spread / max(num - 1, 1)
    start_x = cx - spread / 2
    tent_w = line_w + 2

    for i in range(num):
        tx = start_x + i * spacing
        length = random.randint(int(body_h * 0.25), int(body_h * 0.40))
        # Smooth S-curve via 3 segments
        sway = random.uniform(-body_w * 0.08, body_w * 0.08)
        mid1_y = bottom_y + length * 0.33
        mid2_y = bottom_y + length * 0.66
        end_y = bottom_y + length
        points = [(tx, bottom_y),
                  (tx + sway, mid1_y),
                  (tx - sway * 0.5, mid2_y),
                  (tx + sway * 0.3, end_y)]
        for j in range(len(points) - 1):
            draw.line([points[j], points[j + 1]], fill=primary, width=tent_w)
        # Rounded end
        ex, ey = points[-1]
        r = max(tent_w, 3)
        draw.ellipse([ex - r, ey - r, ex + r, ey + r], fill=primary)


# ---------------------------------------------------------------------------
# Legs – thicker, with feet
# ---------------------------------------------------------------------------
def _draw_legs(draw, cx, cy, body_w, body_h, primary, line_w):
    bottom_y = cy + body_h // 2
    leg_h = random.randint(int(body_h * 0.18), int(body_h * 0.28))
    num_legs = random.choices([2, 3, 4], weights=[60, 20, 20])[0]
    leg_w = line_w + 3
    foot_r = max(leg_w + 1, 5)
    spread = body_w * 0.5

    if num_legs <= 2:
        positions = [cx - spread / 2, cx + spread / 2]
    elif num_legs == 3:
        positions = [cx - spread / 2, cx, cx + spread / 2]
    else:
        step = spread / (num_legs - 1)
        positions = [cx - spread / 2 + i * step for i in range(num_legs)]

    for lx in positions:
        draw.line([(lx, bottom_y), (lx, bottom_y + leg_h)],
                  fill=primary, width=leg_w)
        # Rounded foot
        draw.ellipse([lx - foot_r, bottom_y + leg_h - foot_r // 2,
                      lx + foot_r, bottom_y + leg_h + foot_r],
                     fill=primary)


# ---------------------------------------------------------------------------
# Extras – always close to body
# ---------------------------------------------------------------------------
def _draw_extras(draw, cx, cy, body_w, body_h, primary, line_w):
    features = random.sample(
        ["wings", "tail", "spots", "dots"],
        k=random.randint(0, 2)
    )

    if "wings" in features:
        wing_w = random.randint(int(body_w * 0.14), int(body_w * 0.22))
        wing_h = random.randint(int(body_h * 0.20), int(body_h * 0.30))
        wing_y = cy - int(body_h * 0.10)
        lx = cx - body_w // 2
        rx = cx + body_w // 2
        # Left wing
        draw.polygon([(lx, wing_y),
                      (lx - wing_w, wing_y - wing_h),
                      (lx - wing_w // 3, wing_y + wing_h // 4)],
                     outline=primary, width=line_w)
        # Right wing (mirrored)
        draw.polygon([(rx, wing_y),
                      (rx + wing_w, wing_y - wing_h),
                      (rx + wing_w // 3, wing_y + wing_h // 4)],
                     outline=primary, width=line_w)

    if "tail" in features:
        side = random.choice([-1, 1])
        tail_len = random.randint(int(body_w * 0.12), int(body_w * 0.22))
        tail_y = cy + int(body_h * 0.25)
        sx = cx + side * body_w // 2
        if side < 0:
            x0, x1 = sx - tail_len, sx
        else:
            x0, x1 = sx, sx + tail_len
        draw.arc([x0, tail_y - tail_len // 2, x1, tail_y + tail_len // 2],
                 start=180 if side < 0 else 0, end=360 if side < 0 else 180,
                 fill=primary, width=line_w)

    if "spots" in features:
        for _ in range(random.randint(2, 4)):
            sx = cx + random.randint(-int(body_w * 0.25), int(body_w * 0.25))
            sy = cy + random.randint(-int(body_h * 0.15), int(body_h * 0.20))
            sr = random.randint(3, max(int(body_w * 0.04), 4))
            draw.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=primary)

    if "dots" in features:
        for _ in range(random.randint(3, 6)):
            dx = cx + random.randint(-int(body_w * 0.28), int(body_w * 0.28))
            dy = cy + random.randint(-int(body_h * 0.20), int(body_h * 0.22))
            dr = random.randint(2, max(int(body_w * 0.025), 3))
            draw.ellipse([dx - dr, dy - dr, dx + dr, dy + dr], fill=primary)


# ===================================================================
# Plugin class
# ===================================================================
class TinyMonsters(BasePlugin):
    """Plugin that generates a random cute monster illustration on each refresh."""

    def generate_image(self, settings, device_config):
        primary_color = ImageColor.getcolor(
            settings.get("primaryColor") or "#000000", "RGB"
        )
        secondary_color = ImageColor.getcolor(
            settings.get("secondaryColor") or "#ffffff", "RGB"
        )

        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]

        w, h = dimensions
        image = Image.new("RGB", (w, h), secondary_color)
        draw = ImageDraw.Draw(image)

        # Thicker base stroke for e-ink visibility
        line_w = max(int(min(w, h) * 0.008), 3)

        # --- Layout zones ---
        title_zone_h = int(h * 0.10)
        name_zone_h = int(h * 0.10)
        monster_zone_h = h - title_zone_h - name_zone_h

        # --- Title ---
        title_font_size = max(int(h * 0.05), 16)
        title_font = get_font("Jost", title_font_size, "bold")
        if title_font:
            draw.text(
                (w // 2, title_zone_h // 2),
                "Tiny Monsters",
                font=title_font,
                fill=primary_color,
                anchor="mm",
            )

        # --- Monster parameters (controlled randomness) ---
        monster_name = generate_monster_name()
        body_shape = random.choice(BODY_SHAPES)

        # Eyes: 1-3 common, 4-5 rare
        num_eyes = random.choices([1, 2, 3, 4, 5], weights=[20, 40, 25, 10, 5])[0]
        mouth_style = random.choice(MOUTH_STYLES)

        # Horns: 0-2 common, 3-4 rare
        num_horns = random.choices([0, 1, 2, 3, 4], weights=[30, 30, 25, 10, 5])[0]
        horn_shape = random.choice(HORN_SHAPES)

        # Limb style: arms or tentacles
        use_tentacles = random.random() < 0.15
        arm_style = "none" if use_tentacles else random.choice(["short", "raised", "normal"])

        # --- Body sizing: 60-70% of monster zone ---
        body_w = random.randint(int(w * 0.38), int(w * 0.50))
        body_h = random.randint(int(monster_zone_h * 0.52), int(monster_zone_h * 0.65))

        # Center of monster zone
        monster_cx = w // 2
        monster_cy = title_zone_h + monster_zone_h // 2

        # --- Draw order: back → front ---
        # 1. Extras behind body (wings, tail)
        _draw_extras(draw, monster_cx, monster_cy, body_w, body_h,
                     primary_color, line_w)

        # 2. Arms behind body
        _draw_arms(draw, monster_cx, monster_cy, body_w, body_h,
                   arm_style, primary_color, secondary_color, line_w)

        # 3. Legs or tentacles
        if use_tentacles:
            _draw_tentacles(draw, monster_cx, monster_cy, body_w, body_h,
                            primary_color, line_w)
        else:
            _draw_legs(draw, monster_cx, monster_cy, body_w, body_h,
                       primary_color, line_w)

        # 4. Body (central anchor, drawn on top of limbs)
        _draw_body(draw, monster_cx, monster_cy, body_w, body_h,
                   body_shape, secondary_color, primary_color, line_w)

        # 5. Horns on top of body
        _draw_horns(draw, monster_cx, monster_cy, body_w, body_h,
                    num_horns, horn_shape, primary_color, line_w)

        # 6. Eyes inside body
        _draw_eyes(draw, monster_cx, monster_cy, body_w, body_h,
                   num_eyes, primary_color, secondary_color, line_w)

        # 7. Mouth centered on body
        _draw_mouth(draw, monster_cx, monster_cy, body_w, body_h,
                    mouth_style, primary_color, secondary_color, line_w)

        # --- Monster name ---
        name_font_size = max(int(h * 0.045), 14)
        name_font = get_font("Jost", name_font_size)
        if name_font:
            name_y = h - name_zone_h // 2
            draw.text(
                (w // 2, name_y),
                monster_name,
                font=name_font,
                fill=primary_color,
                anchor="mm",
            )

        return image
