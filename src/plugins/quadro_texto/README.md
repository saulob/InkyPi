# Texto — InkyPi Plugin

Displays a two-part reminder card drawn entirely with Pillow. No external APIs, no HTML rendering.

## Install

No extra dependencies. The plugin uses only Pillow, which is already part of InkyPi.

Copy the `quadro_texto/` folder into `src/plugins/` and restart the service:

```bash
sudo systemctl restart inkypi.service
```

## Settings

| Field | Default | Description |
|---|---|---|
| `top_text` | `Para contar` | Small label in the top section |
| `main_text` | `2h extras` | Large bold text in the top section |
| `bottom_text` | `Você sai às` | Small label in the bottom section |
| `time_text` | `19h` | Large bold text in the bottom section |
| `theme` | `random` | `random` / `black_white` / `blue_green` / `purple_orange` |
| `layout` | `random` | `random` / `split` / `poster` / `minimal` |
| `show_border` | `true` | Rounded border around the canvas |
| `show_icons` | `true` | Clock icon (top) and door-exit icon (bottom) |

## Layouts

- **split** — Canvas cut in half horizontally; icon + label + value in each half.
- **poster** — Everything centred vertically; clock at top, door decoration at bottom-right.
- **minimal** — Text only, centred, with a thin divider line.
- **random** — Picks a layout (and theme, if also set to random) on every refresh.

## Example settings

```json
{
  "top_text": "Para contar",
  "main_text": "2h extras",
  "bottom_text": "Você sai às",
  "time_text": "19h",
  "theme": "black_white",
  "layout": "split",
  "show_border": "true",
  "show_icons": "true"
}
```
