# Side-scroller prototype - gothic edition

Run the game: `python main.py`   Run the level editor: `python level_editor.py [levels/level_01.py]`
(needs only Python 3 + pygame 2).

## Controls
Move Q/D or arrows - Jump Space - Crouch S - Dash Shift/K - Sword combo J/X (tap again during a swing, 3 hits)
Drop through one-way platforms/ramps: Space+S - F1 help - F2 hitboxes - Esc quit.
Holding a direction walks, then runs after ~0.3 s.

## Everything visual is a PNG (assets/)
| Folder | What | Format |
|---|---|---|
| `characters/vampire.png + .json` | the player's animation sheet | one row per animation, 96x96 frames. JSON: frame size, origin (feet), per animation `row, frames, fps, loop`; attacks also carry `hit_frames, hitbox, lunge, cost` |
| `skins/*.png (+ .json)` | textures for platforms, ramps, hazards, portals | 16px tiles, standard 48x64 layout: `tl tm tr / ml mm mr / bl bm br / sl sm sr` (the last row is used when an object is 1 tile tall). Animated skins: put frames side by side and set `frames`, `fps`, `frame_w` in the JSON |
| `tilesets/*.png` | tiles for painting decoration layers | any size, multiples of 16px |
| `props/*.png (+ .json)` | free-placed decoration, optionally animated | strip of `frames` frames |
| `backgrounds/<name>/background.json` | parallax backgrounds | layers with `parallax`, `anchor`, `tile_x`, `drift`; optional `sky` gradient |
| `ui/icons.png + .json` | HUD / ability icons | 16x16 cells |

Art is drawn on a 16px grid. 32px art can be imported (the editor's "16px art / 32px art" toggle scales it
down 2x on import so it lines up with the grid).

To use your own hand-drawn character: keep the same row order / frame counts (or edit `vampire.json`) and
replace `vampire.png`. Nothing in the code refers to frames.

## Levels (`levels/level_xx.py`)
Plain Python modules written by the editor: `PLATFORMS`, `SLOPES`, `PROPS`, `TILE_LAYERS`, `BACKGROUND`, ...
A platform can carry `{"skin": "stone_blood"}` and per-slot overrides `{"tiles": {"tm": ("iron_beam", 1, 3)}}`,
so two platforms of the same type can look different. Transition boxes: `{"target": "level_02", "spawn": (80, 496)}`.

## Level editor
* Objects layer: choose a type, **drag on the canvas to draw it**; click to select; drag the body to move;
  **drag the 8 edge/corner handles to resize on the grid**; moving platforms show draggable travel ends.
* Inspector: position/size, **texture (skin) picker**, the **tile-slot editor** (set first/middle/last tile,
  upper-left/upper-right... individually from any skin PNG), type settings, portal target picker, import PNG.
* Layers panel: add / delete / reorder / rename tile layers, back or front, depth dimming, visibility.
  Tile layers are decoration only (no collision). Pick tiles in the tileset picker (drag for a block), click or
  drag to paint, right-drag erases, Shift+drag fills a rectangle, Alt+click picks.
* Level box (bottom right): title, width, **background** picker/importer. **New** creates a blank level file.
* Ctrl+S / Ctrl+O / Ctrl+N, Ctrl+Z / Ctrl+Y undo/redo, Ctrl+D duplicate, G grid, F flip ramp, arrows nudge.

## Regenerating the placeholder art
`tools/` holds the scripts that drew every PNG (`build_vampire.py`, `make_skins.py`, `make_tiles.py`,
`make_props_bg.py`, `make_levels.py`). They need Pillow and are only needed if you want to redo the art.
