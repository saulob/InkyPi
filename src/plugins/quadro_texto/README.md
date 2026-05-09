# Texto — InkyPi Plugin

Displays visual reminder cards drawn entirely with Pillow. No external APIs, no HTML rendering. Supports 10 layouts × 9 colour themes × 7 font packs with optional hand-drawn / doodle illustration styles.

## Dependencies

### Required

| Library | Purpose |
|---------|---------|
| **Pillow** | Core image rendering — all layouts work with Pillow alone |

Pillow is already installed as part of InkyPi. No action needed for a basic install.

### Optional — recommended

| Library | What it enables | Without it |
|---------|----------------|------------|
| **aggdraw** | Anti-aliased curves and smoother hand-drawn paths in doodle style | Doodle uses Pillow line segments (slightly less smooth) |
| **cairosvg** | Load and composite local SVG icon files | Icons are drawn programmatically with Pillow |
| **drawsvg** | Programmatic SVG generation from Python | SVG export disabled; PNG only |

### Optional — advanced

| Library | What it enables | Without it |
|---------|----------------|------------|
| **sketchify** | Advanced pencil / sketch image-processing effects | `sketch` illustration_style falls back to `doodle` |

## Installation

### Quickstart (plugin only)

```bash
cd ~/InkyPi
source .venv/bin/activate
pip install -r src/plugins/quadro_texto/requirements.txt
sudo systemctl restart inkypi.service
```

### Manual install (pick what you need)

```bash
# Required (already present in InkyPi)
pip install Pillow

# Recommended extras
pip install aggdraw cairosvg drawsvg

# Advanced (optional)
# pip install sketchify  # install from its repo if desired
```

### Checking what is active

The plugin logs its dependency status at startup:

```
INFO  quadro_texto: optional dependencies not installed: aggdraw, cairosvg.
      Features requiring them will use Pillow fallbacks.
```

or, when everything is present:

```
INFO  quadro_texto: all optional dependencies available.
```

## Settings

| Field | Default | Description |
|---|---|---|
| `top_text` | `Para contar` | Small label — top section |
| `main_text` | `2h extras` | Large bold text — top section |
| `bottom_text` | `Você sai às` | Small label — bottom section |
| `time_text` | `19h` | Large bold text — bottom section |
| `layout` | `random` | See **Layouts** below |
| `theme` | `random` | See **Themes** below |
| `font_pack` | `random` | See **Font packs** below |
| `border_style` | `random` | `rounded` / `double` / `blueprint` / `none` |
| `illustration_style` | `random` | See **Illustration styles** below |
| `icon_style` | `random` | `clean` / `doodle` (legacy, overridden by `illustration_style`) |
| `show_icons` | `true` | Show clock / door icons |
| `show_divider` | `true` | Show divider line between sections |
| `prevent_repeat_last` | `true` | Anti-repetition shuffle when all values are `random` |

## Layouts

| Value | Description |
|-------|-------------|
| `split` | Canvas cut in half horizontally; icon + label + value in each half |
| `poster` | Everything centred vertically; clock top, door bottom-right |
| `minimal` | Text only, centred, with a thin divider |
| `badge` | Large bold text inside an accent pill/badge shape |
| `dashboard` | Left icon panel + right text panel |
| `blueprint` | Technical style — grid lines, corner brackets, stamp label |
| `doodle` | Sketchy hand-drawn feel with doodle circles and underline accent |
| `framed` | Inner mat frame border around the content |
| `sticker` | Bold text on solid-colour block with top/bottom accent stripes |
| `lateral` | Coloured left stripe with dot pattern; text on right |
| `random` | Picks a layout on every refresh (anti-repeat when combined with other randoms) |

## Themes

`black_white` · `ink_high_contrast` · `grayscale` · `blue_green` · `ocean` · `purple_orange` · `warm_corporate` · `sunset` · `pastel` · `forest` · `random`

## Font packs

`bold_clean` (Jost) · `geometric` · `rounded` · `condensed` · `editorial` (Napoli serif) · `technical` (DS-Digital) · `pixel` (Dogica) · `random`

## Illustration styles

| Value | Description | Requires |
|-------|-------------|---------|
| `clean` | Geometric Pillow shapes | — |
| `doodle` | Wobbly lines, imperfect circles | — (better with aggdraw) |
| `sketch` | Heavier pencil feel | sketchify (falls back to `doodle`) |
| `sticker` | Thick marker strokes, speech bubbles | — |
| `mixed` | Picks randomly per render | — |
| `random` | Anti-repeat random across sessions | — |

## Example settings

```json
{
  "top_text": "Para contar",
  "main_text": "2h extras",
  "bottom_text": "Você sai às",
  "time_text": "19h",
  "theme": "black_white",
  "layout": "split",
  "font_pack": "bold_clean",
  "border_style": "rounded",
  "illustration_style": "doodle",
  "show_icons": "true",
  "show_divider": "true",
  "prevent_repeat_last": "true"
}
```

## Troubleshooting

### Missing aggdraw

**Symptom:** Doodle lines look slightly jagged instead of smooth.  
**Fix:**
```bash
pip install aggdraw
sudo systemctl restart inkypi.service
```
The plugin works without it — doodle style uses Pillow segments as fallback.

---

### Missing cairosvg / SVG icons not loading

**Symptom:** `load_svg_icon()` always returns `None`; log shows:
```
Optional dependency 'cairosvg' is not installed. SVG icons will use Pillow-drawn fallback.
```
**Fix:**
```bash
pip install cairosvg
sudo systemctl restart inkypi.service
```
Without cairosvg the plugin draws all icons with Pillow — fully functional.

---

### `sketch` style falling back to `doodle`

**Symptom:** Log shows:
```
illustration_style 'sketch' requires 'sketchify' which is not installed. Falling back to 'doodle'.
```
**Fix:** Install sketchify from its repository if you want the advanced pencil effect, or simply choose `doodle` or `sticker` as your illustration_style.

---

### `doodle` style falling back to `clean`

**Symptom:** Log shows:
```
illustration_style 'doodle' requires 'aggdraw' which is not installed. Falling back to 'clean'.
```
**Fix:** `pip install aggdraw` or select `clean` / `sticker` as the illustration_style.

---

### General: check which features are active

```python
import sys; sys.path.insert(0, 'src/plugins/quadro_texto')
from dependencies import get_dependency_status, get_missing_optional_dependencies
print(get_dependency_status())
print("Missing:", get_missing_optional_dependencies())
```
