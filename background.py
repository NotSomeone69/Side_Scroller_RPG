"""Parallax backgrounds defined by assets/backgrounds/<name>/background.json:

    {"name": "Blood Moon", "sky": [[0,0,0],[40,4,6]],                 # optional banded gradient
     "layers": [{"image": "far.png", "parallax": 0.1, "anchor": "bottom",
                 "tile_x": true, "y_offset": 0, "drift": 0}, ...]}        # drawn first -> last
"""
import pygame
import assets
from settings import SCREEN_WIDTH, SCREEN_HEIGHT

_cache = {}


def get_background(name):
    bg = _cache.get(name)
    if bg is None:
        bg = _cache[name] = Background(name)
    return bg


def forget():
    _cache.clear()


class Background:
    def __init__(self, name, size=(SCREEN_WIDTH, SCREEN_HEIGHT)):
        self.name = name
        self.size = size
        folder = assets.path("backgrounds", name)
        meta = assets.load_json(folder + "/background.json", None)
        if meta is None:
            meta = assets.load_json(assets.path("backgrounds", "blood_moon", "background.json"), {"layers": []})
            folder = assets.path("backgrounds", "blood_moon")
        self.title = meta.get("name", name)
        self.sky = self._make_sky(meta["sky"]) if "sky" in meta else None
        self.layers = []
        for spec in meta.get("layers", []):
            img = assets.load_image(f"{folder}/{spec['image']}")
            self.layers.append((img, float(spec.get("parallax", 0.0)), spec.get("anchor", "bottom"),
                                bool(spec.get("tile_x", False)), int(spec.get("y_offset", 0)), float(spec.get("drift", 0.0))))

    def _make_sky(self, colors):
        w, h = self.size
        top, bottom = colors
        surf = pygame.Surface((w, h))
        bands = 16
        for i in range(bands):                                   # hard bands read as pixel art
            t = i / (bands - 1)
            c = tuple(int(top[k] + (bottom[k] - top[k]) * t) for k in range(3))
            surf.fill(c, (0, i * h // bands, w, (i + 1) * h // bands - i * h // bands))
        return surf

    def draw(self, surface, camera_x, time=0.0):
        w, h = surface.get_size()
        if self.sky is not None:
            x = 0
            while x < w:                                         # (editor previews can be wider than the screen)
                surface.blit(self.sky, (x, 0))
                x += self.sky.get_width()
        else:
            surface.fill((0, 0, 0))
        for img, parallax, anchor, tile_x, y_offset, drift in self.layers:
            iw, ih = img.get_size()
            y = (y_offset if anchor == "top" else h - ih + y_offset)
            if tile_x:
                off = int(camera_x * parallax + drift * time) % iw
                x = -off
                while x < w:
                    surface.blit(img, (x, y))
                    x += iw
            else:
                surface.blit(img, (0, y))
