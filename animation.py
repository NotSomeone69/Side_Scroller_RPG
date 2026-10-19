"""Sprite-sheet animation. A sheet is a PNG + JSON (see assets/characters/vampire.json):

    {"image": "vampire.png", "frame_size": [96, 96], "origin": [48, 93],
     "animations": {"idle": {"row": 0, "frames": 8, "fps": 6, "loop": true}, ...}}

Each animation is one row of the PNG. Extra keys (hit_frames, hitbox, ...) are gameplay data
that travels with the animation and is read by abilities.
"""
import os
import pygame
import assets


class SpriteSheet:
    def __init__(self, json_file):
        self.dir = os.path.dirname(json_file)
        self.meta = assets.load_json(json_file, {})
        self.image = assets.load_image(os.path.join(self.dir, self.meta["image"]))
        self.fw, self.fh = self.meta["frame_size"]
        self.origin = tuple(self.meta.get("origin", (self.fw // 2, self.fh)))
        self.anims = self.meta["animations"]
        self._frames = {}
        self._ghosts = {}

    def info(self, name):
        return self.anims[name]

    def count(self, name):
        return self.anims[name]["frames"]

    def frame(self, name, index, facing=1):
        key = (name, index, facing)
        surf = self._frames.get(key)
        if surf is None:
            if facing == 1:
                a = self.anims[name]
                rect = pygame.Rect(index * self.fw, a["row"] * self.fh, self.fw, self.fh)
                surf = self.image.subsurface(rect).copy()
            else:
                surf = pygame.transform.flip(self.frame(name, index, 1), True, False)
            self._frames[key] = surf
        return surf

    def ghost(self, key, color):
        """Single-colour silhouette of a frame ('key' is (name, index, facing))."""
        cache_key = (key, color)
        ghost = self._ghosts.get(cache_key)
        if ghost is None:
            mask = pygame.mask.from_surface(self.frame(*key))
            rgba = color if len(color) == 4 else tuple(color) + (255,)
            ghost = mask.to_surface(setcolor=rgba, unsetcolor=(0, 0, 0, 0))
            self._ghosts[cache_key] = ghost
        return ghost


class Animator:
    """Plays one animation of a sheet at a time."""

    def __init__(self, sheet, name="idle"):
        self.sheet = sheet
        self.name = None
        self.time = 0.0
        self.index = 0
        self.finished = False
        self.play(name)

    def play(self, name, restart=False):
        if name != self.name or restart:
            self.name = name
            self.time = 0.0
            self.index = 0
            self.finished = False

    def update(self, dt):
        a = self.sheet.anims[self.name]
        self.time += dt
        pos = int(self.time * a["fps"])
        if a.get("loop", True):
            self.index = pos % a["frames"]
        elif pos >= a["frames"]:
            self.index = a["frames"] - 1
            self.finished = True
        else:
            self.index = pos

    @property
    def key(self):
        return self.name, self.index, 1

    def surface(self, facing=1):
        return self.sheet.frame(self.name, self.index, facing)

    def duration(self, name=None):
        a = self.sheet.anims[name or self.name]
        return a["frames"] / a["fps"]
