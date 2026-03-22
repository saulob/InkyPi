import random
import math
import logging

from plugins.base_plugin.base_plugin import BasePlugin
from utils.app_utils import get_font
from PIL import Image, ImageColor, ImageDraw

logger = logging.getLogger(__name__)

# Name generation components
NAME_PREFIXES = [
    "Bl", "Gr", "Zr", "Kr", "Fl", "Sp", "Dr", "Tr", "Gl", "Sn",
    "Pl", "Br", "Cl", "Fr", "Sk", "Sl", "Sw", "Tw", "Wr", "Pr",
    "Qu", "Sh", "Ch", "Th", "Wh", "Scr", "Str", "Spl",
]

NAME_MIDDLES = [
    "o", "i", "u", "a", "e", "oo", "ee", "ip", "op", "ub",
    "ig", "og", "un", "ur", "an", "in", "or", "ar", "up", "um",
]

NAME_SUFFIXES = [
    "g", "p", "k", "n", "x", "z", "pp", "rk", "nk", "bs",
    "rg", "lp", "mp", "ff", "tt", "zz", "lo", "bo", "go", "ko",
    "ni", "po", "ro", "mo", "ki", "bi", "li", "zi", "do", "no",
]

BODY_SHAPES = ["round", "oval", "blob", "squared"]

MOUTH_STYLES = ["smile", "open", "small", "big", "teeth"]

HORN_SHAPES = ["triangle", "curved"]


def generate_monster_name():
    """Generate a random playful monster name."""
    prefix = random.choice(NAME_PREFIXES)
    middle = random.choice(NAME_MIDDLES)
    suffix = random.choice(NAME_SUFFIXES)
    return prefix + middle + suffix


def _draw_blob_body(draw, cx, cy, radius, fill, outline, width):
    """Draw a slightly irregular blob body using a deformed circle."""
    points = []
    num_points = 36
    for i in range(num_points):
        angle = (2 * math.pi * i) / num_points
        # Random variation for organic feel
        r = radius * random.uniform(0.85, 1.15)
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        points.append((x, y))
    draw.polygon(points, fill=fill, outline=outline, width=width)


def _draw_body(draw, cx, cy, body_w, body_h, shape, fill, outline, line_w):
    """Draw the monster body based on the chosen shape."""
    if shape == "round":
        r = min(body_w, body_h) // 2
        draw.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            fill=fill, outline=outline, width=line_w
        )
    elif shape == "oval":
        draw.ellipse(
            [cx - body_w // 2, cy - body_h // 2,
             cx + body_w // 2, cy + body_h // 2],
            fill=fill, outline=outline, width=line_w
        )
    elif shape == "blob":
        avg_r = (body_w + body_h) // 4
        _draw_blob_body(draw, cx, cy, avg_r, fill, outline, line_w)
    elif shape == "squared":
        corner_r = min(body_w, body_h) // 8
        draw.rounded_rectangle(
            [cx - body_w // 2, cy - body_h // 2,
             cx + body_w // 2, cy + body_h // 2],
            radius=corner_r, fill=fill, outline=outline, width=line_w
        )


def _draw_eyes(draw, cx, cy, body_w, body_h, num_eyes, primary, secondary, line_w):
    """Draw eyes on the monster."""
    eye_zone_top = cy - body_h // 4
    eye_zone_w = body_w * 0.6

    if num_eyes == 1:
        positions = [(cx, eye_zone_top)]
    else:
        spacing = eye_zone_w / (num_eyes - 1) if num_eyes > 1 else 0
        start_x = cx - eye_zone_w / 2
        positions = [(start_x + i * spacing, eye_zone_top) for i in range(num_eyes)]

    max_eye_r = int(min(body_w, body_h) * 0.12)
    min_eye_r = max(max_eye_r // 2, 4)

    for ex, ey in positions:
        er = random.randint(min_eye_r, max_eye_r)
        # Eye white
        draw.ellipse([ex - er, ey - er, ex + er, ey + er],
                     fill=secondary, outline=primary, width=line_w)
        # Pupil
        pr = max(er // 3, 2)
        # Slight random offset for pupil
        px = ex + random.randint(-pr, pr)
        py = ey + random.randint(-pr // 2, pr // 2)
        draw.ellipse([px - pr, py - pr, px + pr, py + pr], fill=primary)


def _draw_mouth(draw, cx, cy, body_h, style, primary, secondary, line_w):
    """Draw a mouth on the monster."""
    mouth_y = cy + body_h // 6
    mouth_w = random.randint(body_h // 8, body_h // 4)

    if style == "smile":
        draw.arc(
            [cx - mouth_w, mouth_y - mouth_w // 2,
             cx + mouth_w, mouth_y + mouth_w // 2],
            start=0, end=180, fill=primary, width=line_w
        )
    elif style == "open":
        r = mouth_w // 2
        draw.ellipse(
            [cx - r, mouth_y - r, cx + r, mouth_y + r],
            fill=primary
        )
    elif style == "small":
        r = max(mouth_w // 4, 3)
        draw.ellipse(
            [cx - r, mouth_y - r, cx + r, mouth_y + r],
            fill=primary
        )
    elif style == "big":
        draw.arc(
            [cx - mouth_w, mouth_y - mouth_w,
             cx + mouth_w, mouth_y + mouth_w],
            start=0, end=180, fill=primary, width=line_w + 1
        )
    elif style == "teeth":
        # Mouth outline
        draw.arc(
            [cx - mouth_w, mouth_y - mouth_w // 2,
             cx + mouth_w, mouth_y + mouth_w // 2],
            start=0, end=180, fill=primary, width=line_w
        )
        # Teeth as small rectangles
        tooth_w = max(mouth_w // 4, 3)
        tooth_h = max(mouth_w // 5, 2)
        num_teeth = random.randint(2, 4)
        teeth_total_w = num_teeth * tooth_w + (num_teeth - 1) * 2
        start_x = cx - teeth_total_w // 2
        for i in range(num_teeth):
            tx = start_x + i * (tooth_w + 2)
            draw.rectangle(
                [tx, mouth_y - 1, tx + tooth_w, mouth_y + tooth_h],
                fill=secondary, outline=primary, width=max(line_w - 1, 1)
            )


def _draw_horns(draw, cx, cy, body_w, body_h, num_horns, shape, primary, line_w):
    """Draw horns on top of the monster."""
    if num_horns == 0:
        return

    top_y = cy - body_h // 2
    horn_h = random.randint(body_h // 5, body_h // 3)

    if num_horns == 1:
        positions = [cx]
    else:
        spread = body_w * 0.5
        spacing = spread / (num_horns - 1) if num_horns > 1 else 0
        start_x = cx - spread / 2
        positions = [start_x + i * spacing for i in range(num_horns)]

    for hx in positions:
        hw = random.randint(body_w // 16, body_w // 8)
        if shape == "triangle":
            draw.polygon(
                [(hx, top_y - horn_h),
                 (hx - hw, top_y + 4),
                 (hx + hw, top_y + 4)],
                fill=primary
            )
        elif shape == "curved":
            # Curved horn using arc approximation
            curve_offset = random.choice([-1, 1]) * hw
            draw.polygon(
                [(hx + curve_offset, top_y - horn_h),
                 (hx - hw, top_y + 4),
                 (hx + hw, top_y + 4)],
                fill=primary
            )


def _draw_arms(draw, cx, cy, body_w, body_h, arm_style, primary, line_w):
    """Draw arms on the monster."""
    if arm_style == "none":
        return

    left_x = cx - body_w // 2
    right_x = cx + body_w // 2
    arm_len = random.randint(body_w // 6, body_w // 3)

    if arm_style == "short":
        # Short horizontal stubs
        draw.line([(left_x, cy), (left_x - arm_len, cy)],
                  fill=primary, width=line_w + 1)
        draw.line([(right_x, cy), (right_x + arm_len, cy)],
                  fill=primary, width=line_w + 1)
    elif arm_style == "raised":
        draw.line([(left_x, cy), (left_x - arm_len, cy - arm_len)],
                  fill=primary, width=line_w + 1)
        draw.line([(right_x, cy), (right_x + arm_len, cy - arm_len)],
                  fill=primary, width=line_w + 1)
    elif arm_style == "low":
        draw.line([(left_x, cy), (left_x - arm_len, cy + arm_len)],
                  fill=primary, width=line_w + 1)
        draw.line([(right_x, cy), (right_x + arm_len, cy + arm_len)],
                  fill=primary, width=line_w + 1)

    # Small circles at arm ends for hands
    hand_r = max(line_w + 1, 4)
    if arm_style == "short":
        for hx in [left_x - arm_len, right_x + arm_len]:
            draw.ellipse([hx - hand_r, cy - hand_r, hx + hand_r, cy + hand_r],
                         fill=primary)
    elif arm_style == "raised":
        for hx, hy in [(left_x - arm_len, cy - arm_len),
                        (right_x + arm_len, cy - arm_len)]:
            draw.ellipse([hx - hand_r, hy - hand_r, hx + hand_r, hy + hand_r],
                         fill=primary)
    elif arm_style == "low":
        for hx, hy in [(left_x - arm_len, cy + arm_len),
                        (right_x + arm_len, cy + arm_len)]:
            draw.ellipse([hx - hand_r, hy - hand_r, hx + hand_r, hy + hand_r],
                         fill=primary)


def _draw_legs(draw, cx, cy, body_w, body_h, primary, line_w):
    """Draw simple legs under the monster body."""
    bottom_y = cy + body_h // 2
    leg_h = random.randint(body_h // 6, body_h // 4)
    num_legs = random.choice([2, 2, 2, 3])
    spread = body_w * 0.4

    if num_legs == 2:
        positions = [cx - spread / 2, cx + spread / 2]
    else:
        positions = [cx - spread / 2, cx, cx + spread / 2]

    foot_r = max(line_w + 1, 4)
    for lx in positions:
        draw.line([(lx, bottom_y), (lx, bottom_y + leg_h)],
                  fill=primary, width=line_w + 1)
        draw.ellipse(
            [lx - foot_r, bottom_y + leg_h - foot_r,
             lx + foot_r, bottom_y + leg_h + foot_r],
            fill=primary
        )


def _draw_extras(draw, cx, cy, body_w, body_h, primary, line_w):
    """Draw optional extra features: wings, tail, spots, dots."""
    features = random.sample(
        ["wings", "tail", "spots", "dots"],
        k=random.randint(0, 2)
    )

    if "wings" in features:
        wing_w = random.randint(body_w // 5, body_w // 3)
        wing_h = random.randint(body_h // 4, body_h // 3)
        wing_y = cy - body_h // 6
        # Left wing
        left_x = cx - body_w // 2
        draw.polygon(
            [(left_x, wing_y),
             (left_x - wing_w, wing_y - wing_h),
             (left_x - wing_w // 2, wing_y + wing_h // 3)],
            outline=primary, width=line_w
        )
        # Right wing
        right_x = cx + body_w // 2
        draw.polygon(
            [(right_x, wing_y),
             (right_x + wing_w, wing_y - wing_h),
             (right_x + wing_w // 2, wing_y + wing_h // 3)],
            outline=primary, width=line_w
        )

    if "tail" in features:
        tail_side = random.choice(["left", "right"])
        tail_len = random.randint(body_w // 4, body_w // 2)
        tail_y = cy + body_h // 4
        if tail_side == "left":
            sx = cx - body_w // 2
            draw.arc(
                [sx - tail_len, tail_y - tail_len // 2,
                 sx, tail_y + tail_len // 2],
                start=180, end=360, fill=primary, width=line_w
            )
        else:
            sx = cx + body_w // 2
            draw.arc(
                [sx, tail_y - tail_len // 2,
                 sx + tail_len, tail_y + tail_len // 2],
                start=180, end=360, fill=primary, width=line_w
            )

    if "spots" in features:
        num_spots = random.randint(2, 5)
        for _ in range(num_spots):
            sx = cx + random.randint(-body_w // 4, body_w // 4)
            sy = cy + random.randint(-body_h // 6, body_h // 4)
            sr = random.randint(3, max(body_w // 16, 4))
            draw.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=primary)

    if "dots" in features:
        num_dots = random.randint(3, 8)
        for _ in range(num_dots):
            dx = cx + random.randint(-body_w // 3, body_w // 3)
            dy = cy + random.randint(-body_h // 4, body_h // 3)
            dr = random.randint(2, max(body_w // 24, 3))
            draw.ellipse([dx - dr, dy - dr, dx + dr, dy + dr], fill=primary)


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

        # Line width scales with display size
        line_w = max(int(min(w, h) * 0.006), 2)

        # --- Layout zones ---
        title_zone_h = int(h * 0.12)
        name_zone_h = int(h * 0.12)
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

        # --- Monster generation parameters ---
        monster_name = generate_monster_name()
        body_shape = random.choice(BODY_SHAPES)
        num_eyes = random.randint(1, 5)
        mouth_style = random.choice(MOUTH_STYLES)
        num_horns = random.randint(0, 5)
        horn_shape = random.choice(HORN_SHAPES)
        arm_style = random.choice(["none", "short", "raised", "low"])

        # --- Monster sizing ---
        max_body_w = int(w * 0.45)
        max_body_h = int(monster_zone_h * 0.55)
        body_w = random.randint(int(max_body_w * 0.7), max_body_w)
        body_h = random.randint(int(max_body_h * 0.7), max_body_h)

        # Center of monster zone
        monster_cx = w // 2
        monster_cy = title_zone_h + monster_zone_h // 2

        # --- Draw monster parts (back to front) ---
        _draw_extras(draw, monster_cx, monster_cy, body_w, body_h,
                     primary_color, line_w)
        _draw_arms(draw, monster_cx, monster_cy, body_w, body_h,
                   arm_style, primary_color, line_w)
        _draw_legs(draw, monster_cx, monster_cy, body_w, body_h,
                   primary_color, line_w)
        _draw_body(draw, monster_cx, monster_cy, body_w, body_h,
                   body_shape, secondary_color, primary_color, line_w)
        _draw_horns(draw, monster_cx, monster_cy, body_w, body_h,
                    num_horns, horn_shape, primary_color, line_w)
        _draw_eyes(draw, monster_cx, monster_cy, body_w, body_h,
                   num_eyes, primary_color, secondary_color, line_w)
        _draw_mouth(draw, monster_cx, monster_cy + body_h // 8, body_h,
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
