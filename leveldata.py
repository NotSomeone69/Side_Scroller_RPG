"""Pure-Python level model used by the level editor (no pygame): load/save level files and the
geometry helpers for dragging, snapping and resizing. Level files are ordinary Python modules
(levels/level_xx.py) so the game imports them directly."""
import copy
import importlib.util
import os
import re

import settings as S

HERE = os.path.dirname(os.path.abspath(__file__))
LEVELS_DIR = os.path.join(HERE, "levels")
GRID = S.GRID

KIND_CONSTS = {
    "SOLID": S.SOLID, "ONE_WAY": S.ONE_WAY, "MOVING_VERTICAL": S.MOVING_VERTICAL, "MOVING_HORIZONTAL": S.MOVING_HORIZONTAL,
    "CRUMBLE_RESET": S.CRUMBLE_RESET, "CRUMBLE_PERSISTENT": S.CRUMBLE_PERSISTENT, "KILL": S.KILL, "DAMAGE": S.DAMAGE,
    "TRANSITION": S.TRANSITION, "SLOPE_ONE_WAY": S.SLOPE_ONE_WAY, "SLOPE_SOLID": S.SLOPE_SOLID,
}
CONST_OF = {v: k for k, v in KIND_CONSTS.items()}
IMPORT_LINE = "from settings import " + ", ".join(
    ["SOLID", "ONE_WAY", "MOVING_VERTICAL", "MOVING_HORIZONTAL", "CRUMBLE_RESET", "CRUMBLE_PERSISTENT",
     "SLOPE_ONE_WAY", "SLOPE_SOLID", "KILL", "DAMAGE", "TRANSITION"])


def snap(value, grid=GRID):
    return int(round(value / grid)) * grid if grid else int(round(value))


class LevelData:
    def __init__(self):
        self.name = "New Level"
        self.width = 3200
        self.height = S.SCREEN_HEIGHT
        self.start = [80, 496]
        self.background = S.DEFAULT_BACKGROUND
        self.platforms = []      # {"kind","x","y","w","h","options"}
        self.slopes = []         # {"kind","x","y","w","h","direction","options"}
        self.props = []          # {"name","x","y","options"}
        self.layers = []         # {"name","order","dim","tiles":{(tx,ty):(tileset,col,row)},"visible"}

    # ------------------------------------------------------------------ factories
    @staticmethod
    def blank(name="New Level", width=3200):
        d = LevelData()
        d.name, d.width = name, width
        d.platforms.append(make_platform(S.SOLID, 0, 544, 896, 64))
        d.layers.append(make_layer("Background tiles", "back", 0.6))
        return d

    def snapshot(self):
        return copy.deepcopy(self.__dict__)

    def restore(self, snap):
        self.__dict__.update(copy.deepcopy(snap))

    # -------------------------------------------------------------------- load
    @staticmethod
    def load(path):
        spec = importlib.util.spec_from_file_location("_edited_level_" + re.sub(r"\W", "_", os.path.basename(path)), path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        d = LevelData()
        d.name = str(getattr(module, "NAME", os.path.splitext(os.path.basename(path))[0]))
        d.width = int(getattr(module, "LEVEL_WIDTH", 3200))
        d.height = int(getattr(module, "LEVEL_HEIGHT", S.SCREEN_HEIGHT))
        d.start = list(getattr(module, "PLAYER_START", (80, 496)))
        d.background = getattr(module, "BACKGROUND", S.DEFAULT_BACKGROUND)
        for e in getattr(module, "PLATFORMS", []):
            d.platforms.append(make_platform(e[0], e[1], e[2], e[3], e[4], dict(e[5]) if len(e) > 5 else {}))
        for e in getattr(module, "SLOPES", []):
            d.slopes.append(make_slope(e[0], e[1], e[2], e[3], e[4], e[5] if len(e) > 5 else "up_right", dict(e[6]) if len(e) > 6 else {}))
        for e in getattr(module, "PROPS", []):
            d.props.append({"name": e[0], "x": int(e[1]), "y": int(e[2]), "options": dict(e[3]) if len(e) > 3 else {}})
        for spec_ in getattr(module, "TILE_LAYERS", []):
            layer = make_layer(spec_.get("name", "Layer"), spec_.get("order", "back"), float(spec_.get("dim", 0.0)))
            for tx, ty, tileset, col, row in spec_.get("tiles", []):
                layer["tiles"][(tx, ty)] = (tileset, col, row)
            d.layers.append(layer)
        return d

    # -------------------------------------------------------------------- save
    def to_source(self):
        out = ['"""Level created with level_editor.py. Coordinates are world pixels on a 16px grid."""',
               IMPORT_LINE, "",
               f"NAME = {self.name!r}", f"GRID = {GRID}", f"LEVEL_WIDTH = {int(self.width)}", f"LEVEL_HEIGHT = {int(self.height)}",
               f"PLAYER_START = ({int(self.start[0])}, {int(self.start[1])})", f"BACKGROUND = {self.background!r}", "", "PLATFORMS = ["]
        for p in self.platforms:
            out.append(f"    ({CONST_OF[p['kind']]}, {p['x']}, {p['y']}, {p['w']}, {p['h']}, {_opts(p['options'])!r}),")
        out += ["]", "", "SLOPES = ["]
        for s in self.slopes:
            opts = _opts(s["options"])
            out.append(f"    ({CONST_OF[s['kind']]}, {s['x']}, {s['y']}, {s['w']}, {s['h']}, {s['direction']!r}" + (f", {opts!r}" if opts else "") + "),")
        out += ["]", "", "PROPS = ["]
        for pr in self.props:
            out.append(f"    ({pr['name']!r}, {pr['x']}, {pr['y']}, {_opts(pr['options'])!r}),")
        out += ["]", "", "TILE_LAYERS = ["]
        for layer in self.layers:
            tiles = sorted(((ty, tx, ts, c, r) for (tx, ty), (ts, c, r) in layer["tiles"].items()))
            out += ["    {", f"        'name': {layer['name']!r}, 'order': {layer['order']!r}, 'dim': {round(layer['dim'], 2)},", "        'tiles': ["]
            for i in range(0, len(tiles), 5):
                out.append("            " + ", ".join(repr((tx, ty, ts, c, r)) for ty, tx, ts, c, r in tiles[i:i + 5]) + ",")
            out += ["        ],", "    },"]
        out.append("]")
        return "\n".join(out) + "\n"

    def save(self, path):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self.to_source())


def _opts(options):
    """Options as written to the file: drop empty values, keep tuples (spawn) as tuples."""
    clean = {}
    for k, v in options.items():
        if v in (None, "", {}, []):
            continue
        clean[k] = tuple(v) if k == "spawn" else v
    return clean


def make_layer(name, order="back", dim=0.0):
    return {"name": name, "order": order, "dim": dim, "tiles": {}, "visible": True}


DEFAULT_SIZES = {S.KILL: (160, 32), S.DAMAGE: (96, 16), S.TRANSITION: (48, 96), S.ONE_WAY: (96, 16),
                 S.MOVING_VERTICAL: (96, 16), S.MOVING_HORIZONTAL: (96, 16), S.CRUMBLE_RESET: (96, 16),
                 S.CRUMBLE_PERSISTENT: (96, 16), S.SOLID: (96, 32)}


def make_platform(kind, x, y, w, h, options=None):
    p = {"kind": kind, "x": int(x), "y": int(y), "w": int(w), "h": int(h), "options": dict(options or {})}
    o = p["options"]
    if kind == S.MOVING_VERTICAL:
        o.setdefault("min_y", int(y - 48)); o.setdefault("max_y", int(y + 64)); o.setdefault("speed", 65); o.setdefault("direction", 1)
    elif kind == S.MOVING_HORIZONTAL:
        o.setdefault("min_x", int(x - 48)); o.setdefault("max_x", int(x + 96)); o.setdefault("speed", 85); o.setdefault("direction", 1)
    elif kind in (S.CRUMBLE_RESET, S.CRUMBLE_PERSISTENT):
        o.setdefault("break_after", 3.0); o.setdefault("respawn_after", 1.5)
    elif kind == S.TRANSITION:
        o.setdefault("target", "level_02")
    return p


def make_slope(kind, x, y, w, h, direction="up_right", options=None):
    return {"kind": kind, "x": int(x), "y": int(y), "w": int(w), "h": int(h), "direction": direction, "options": dict(options or {})}


# ---------------------------------------------------------------------------------------------
# Geometry helpers (pure functions, unit-tested)
# ---------------------------------------------------------------------------------------------
HANDLES = ("nw", "n", "ne", "e", "se", "s", "sw", "w")


def handle_points(x, y, w, h):
    """Centre point of each of the 8 resize handles for a rectangle."""
    cx, cy = x + w / 2, y + h / 2
    return {"nw": (x, y), "n": (cx, y), "ne": (x + w, y), "e": (x + w, cy), "se": (x + w, y + h),
            "s": (cx, y + h), "sw": (x, y + h), "w": (x, cy)}


def resize_rect(orig, handle, mx, my, grid=GRID, min_w=GRID, min_h=GRID):
    """New (x, y, w, h) when `handle` of rect `orig` is dragged to world position (mx, my).
    Edges snap to `grid`; the opposite edges stay fixed; the size never drops below the minimum."""
    x, y, w, h = orig
    left, right, top, bottom = x, x + w, y, y + h
    if "w" in handle:
        left = min(snap(mx, grid), right - min_w)
    if "e" in handle:
        right = max(snap(mx, grid), left + min_w)
    if "n" in handle:
        top = min(snap(my, grid), bottom - min_h)
    if "s" in handle:
        bottom = max(snap(my, grid), top + min_h)
    return left, top, right - left, bottom - top


def translate_item(item, dx, dy):
    """Move a platform/slope/prop; moving platforms keep their travel range relative to the move."""
    item["x"] += dx
    item["y"] += dy
    o = item.get("options", {})
    if item.get("kind") == S.MOVING_HORIZONTAL:
        if "min_x" in o: o["min_x"] += dx
        if "max_x" in o: o["max_x"] += dx
    if item.get("kind") == S.MOVING_VERTICAL:
        if "min_y" in o: o["min_y"] += dy
        if "max_y" in o: o["max_y"] += dy


def available_levels():
    if not os.path.isdir(LEVELS_DIR):
        return []
    return sorted(f[:-3] for f in os.listdir(LEVELS_DIR) if f.endswith(".py") and not f.startswith("_"))


def next_level_name():
    n = 1
    names = set(available_levels())
    while f"level_{n:02d}" in names:
        n += 1
    return f"level_{n:02d}"
