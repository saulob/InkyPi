import random
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from plugins.tiny_monsters.tiny_monsters import (  # noqa: E402
    _body_side_anchor,
    _body_vertical_anchor,
    _build_body_geometry,
    _point_in_polygon,
)


def _build_geometry(shape):
    random.seed(1234)
    return _build_body_geometry(200, 180, 180, 160, shape)


def test_body_side_anchors_stay_inside_outline():
    for shape in ["round", "oval", "blob", "rounded_rect", "squared", "ghost"]:
        geometry = _build_geometry(shape)
        for side, expected_direction in (("left", -1), ("right", 1)):
            for y_ratio in (-0.20, -0.02, 0.22):
                anchor = _body_side_anchor(geometry, side, y_ratio, inset=6)
                assert _point_in_polygon(anchor, geometry["points"])
                assert (anchor[0] - geometry["cx"]) * expected_direction > 0


def test_body_vertical_anchors_stay_inside_outline():
    for shape in ["round", "oval", "blob", "rounded_rect", "squared", "ghost"]:
        geometry = _build_geometry(shape)
        for edge, expected_direction in (("top", -1), ("bottom", 1)):
            for x_ratio in (-0.24, 0.0, 0.24):
                anchor = _body_vertical_anchor(geometry, edge, x_ratio, inset=6)
                assert _point_in_polygon(anchor, geometry["points"])
                assert (anchor[1] - geometry["cy"]) * expected_direction > 0