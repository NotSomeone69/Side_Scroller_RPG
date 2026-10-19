"""Tile-grid skins. A skin is a PNG (+ optional JSON) of 16px tiles that textures a platform.

Standard layout (48x64, 3 columns x 4 rows) - slot names:

        tl  tm  tr        top row / middle rows / bottom row, each with left / middle / right
        ml  mm  mr
        bl  bm  br
        sl  sm  sr        used when the object is only ONE tile tall (single row)

A platform that is W x H tiles picks, for every cell, the slot for its position, so you only
draw the corners/edges once. Single tile wide objects use the middle column. Any slot can be
re-assigned per object (options["tiles"]) or per skin (JSON "slots"). Skins can be animated:
lay the frames side by side and set "frames"/"fps" in the JSON.
"""
import math
import os
import pygame
import assets
from settings import GRID

T = GRID
SLOT_NAMES = ["tl", "tm", "tr", "ml", "mm", "mr", "bl", "bm", "br", "sl", "sm", "sr"]
STANDARD = {"tl": (0, 0), "tm": (1, 0), "tr": (2, 0), "ml": (0, 1), "mm": (1, 1), "mr": (2, 1),
            "bl": (0, 2), "bm": (1, 2), "br": (2, 2), "sl": (0, 3), "sm": (1, 3), "sr": (2, 3)}


def default_slots(cols, rows):
    """Best-effort slot mapping for any tile-sheet size (used for imported PNGs)."""
    if cols >= 3 and rows >= 4:
        return dict(STANDARD)
    if cols >= 3 and rows >= 3:
        m = dict(STANDARD)
        m.update(sl=(0, 0), sm=(1, 0), sr=(2, 0))
        return m
    if cols >= 3:                                  # a single strip: left / middle / right
        row = min(rows - 1, 0)
        return {k: (("l" == k[1]) * 0 + ("m" == k[1]) * 1 + ("r" == k[1]) * 2, row) for k in SLOT_NAMES}
    return {k: (0, 0) for k in SLOT_NAMES}


def slot_for(tx, ty, tw, th):
    """Which slot does tile (tx, ty) of a tw x th object use?"""
    col = "l" if (tx == 0 and tw > 1) else "r" if (tx == tw - 1 and tw > 1) else "m"
    if th == 1:
        return "s" + col
    return ("t" if ty == 0 else "b" if ty == th - 1 else "m") + col


_skins = {}


def get_skin(name):
    skin = _skins.get(name)
    if skin is None:
        if not os.path.exists(assets.path("skins", name + ".png")):
            name = "stone_dark"
            skin = _skins.get(name)
        if skin is None:
            skin = _skins[name] = Skin(name)
    return skin


def forget(name=None):
    if name is None:
        _skins.clear()
    else:
        _skins.pop(name, None)


class Skin:
    def __init__(self, name):
        self.name = name
        self.image = assets.load_image(assets.path("skins", name + ".png"))
        meta = assets.load_json(assets.path("skins", name + ".json"), {})
        self.frames = max(1, int(meta.get("frames", 1)))
        self.fps = float(meta.get("fps", 6))
        self.frame_w = int(meta.get("frame_w", self.image.get_width() // self.frames))
        cols, rows = self.frame_w // T, self.image.get_height() // T
        self.cols, self.rows = cols, rows
        custom = meta.get("slots")
        self.slots = {k: tuple(v) for k, v in custom.items()} if custom else default_slots(cols, rows)
        self._tiles = {}
        self._cache = {}

    @property
    def animated(self):
        return self.frames > 1

    def frame_index(self, t):
        return int(t * self.fps) % self.frames if self.animated else 0

    def tile_at(self, col, row, frame=0):
        key = (col, row, frame)
        surf = self._tiles.get(key)
        if surf is None:
            frame %= self.frames
            rect = pygame.Rect(frame * self.frame_w + col * T, row * T, T, T).clip(self.image.get_rect())
            surf = pygame.Surface((T, T), pygame.SRCALPHA)
            if rect.w > 0 and rect.h > 0:
                surf.blit(self.image, (0, 0), rect)
            self._tiles[key] = surf
        return surf

    def slot_tile(self, slot, frame=0, overrides=None):
        if overrides and slot in overrides:
            skin_name, col, row = overrides[slot]
            src = self if skin_name == self.name else get_skin(skin_name)
            return src.tile_at(col, row, frame)
        col, row = self.slots.get(slot, self.slots["mm"])
        return self.tile_at(col, row, frame)

    # ------------------------------------------------------------------ rendering
    def render(self, w, h, frame=0, overrides=None):
        """Surface of w x h px: the object's tiles laid out on the grid (cached)."""
        ov_key = tuple(sorted((k, tuple(v)) for k, v in overrides.items())) if overrides else ()
        key = (w, h, frame, ov_key)
        surf = self._cache.get(key)
        if surf is None:
            tw, th = max(1, math.ceil(w / T)), max(1, math.ceil(h / T))
            surf = pygame.Surface((tw * T, th * T), pygame.SRCALPHA)
            for ty in range(th):
                for tx in range(tw):
                    surf.blit(self.slot_tile(slot_for(tx, ty, tw, th), frame, overrides), (tx * T, ty * T))
            if (w, h) != surf.get_size():
                surf = surf.subsurface(pygame.Rect(0, 0, w, h)).copy()
            self._cache[key] = surf
        return surf

    def render_slope(self, w, h, up_right=True, one_way=False, frame=0, overrides=None):
        """A ramp textured with the skin's fill tile and its lit top edge."""
        key = ("slope", w, h, up_right, one_way, frame)
        surf = self._cache.get(key)
        if surf is None:
            fill = self.slot_tile("mm", frame, overrides)
            edge = self.slot_tile("tm", frame, overrides)
            pattern = pygame.Surface((w, h), pygame.SRCALPHA)
            for y in range(0, h, T):
                for x in range(0, w, T):
                    pattern.blit(fill, (x, y))
            surf = pygame.Surface((w, h), pygame.SRCALPHA)
            prev = None
            for x in range(w):
                u = (x + 0.5) / w
                top = int(round(h * (1 - u))) if up_right else int(round(h * u))
                top = min(h - 1, max(0, top))
                start = top if prev is None else min(top, prev)
                surf.blit(pattern, (x, start), (x, start, 1, h - start))
                surf.blit(edge, (x, start), (x % T, 0, 1, min(3 + abs(top - (prev if prev is not None else top)), h - start)))
                if one_way and (x // 3) % 2 == 0:                    # dashed crimson edge = pass-through ramp
                    surf.fill((150, 0, 0), (x, top, 1, 1))
                prev = top
            self._cache[key] = surf
        return surf


# ---------------------------------------------------------------------------
class TileSet:
    """A PNG of 16px tiles used for painting non-colliding decoration (tile layers)."""

    def __init__(self, name):
        self.name = name
        self.image = assets.load_image(assets.path("tilesets", name + ".png"))
        meta = assets.load_json(assets.path("tilesets", name + ".json"), {})
        self.names = meta.get("names", {})
        self.cols = self.image.get_width() // T
        self.rows = self.image.get_height() // T
        self._tiles = {}

    def tile(self, col, row):
        key = (col, row)
        surf = self._tiles.get(key)
        if surf is None:
            surf = pygame.Surface((T, T), pygame.SRCALPHA)
            surf.blit(self.image, (0, 0), pygame.Rect(col * T, row * T, T, T))
            self._tiles[key] = surf
        return surf


_tilesets = {}


def get_tileset(name):
    ts = _tilesets.get(name)
    if ts is None:
        ts = _tilesets[name] = TileSet(name)
    return ts


def forget_tilesets():
    _tilesets.clear()
