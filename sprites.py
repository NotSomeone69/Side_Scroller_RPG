"""Procedural pixel art: the hero frames and small HUD icons, defined as text.

Every character in a pattern is a palette key, '.' is transparent. Frames are
16x24 "art pixels" drawn at scale 2 so they match the 32x48 player hitbox.
"""

import pygame

SCALE = 2

PALETTE = {
    "K": (26, 22, 38),      # outline
    "B": (62, 100, 176),    # cloak
    "b": (42, 70, 128),     # cloak shadow
    "L": (112, 156, 224),   # cloak light
    "S": (246, 208, 168),   # skin
    "s": (210, 162, 130),   # skin shadow
    "W": (255, 255, 255),
    "E": (30, 24, 44),      # eye
    "R": (222, 72, 82),     # scarf
    "r": (150, 40, 62),     # scarf shadow
    "G": (242, 202, 98),    # belt buckle
    "T": (104, 70, 56),     # boots
    "t": (146, 104, 80),
    "P": (76, 66, 100),     # trousers
    "p": (54, 48, 78),
}

# Head + torso (rows 0-15), facing right.
UPPER = (
    "................",
    ".....KKKKKK.....",
    "...KKBBBBBBKK...",
    "..KBBBLLLBBBBK..",
    "..KBBBBLLBBBBBK.",
    ".KBBBBBBBBBKKKKK",
    ".KBBBBBBBBKSSSSK",
    ".KRRBBBBBBKSWEsK",
    "KRrRBBBBBBKSSSSK",
    "KrRRRRRRRRRRRRKK",
    ".KrrRRRRRRRRRKK.",
    "..KBBBBBBBBBBK..",
    "..KBBLBBBBBBbK..",
    "..KBBBBBGGBBbK..",
    "..KbBBBBGGBBbK..",
    "..KKbbbbbbbbKK..",
)

# Legs (rows 16-23).
LEGS = {
    "stand": (
        "...KPPPKKPPPK...",
        "...KPPPKKpPPK...",
        "...KPPPK.KpPK...",
        "...KPPPK.KpPK...",
        "...KTTTK.KTTK...",
        "..KTTTTK.KTTTK..",
        "..KttTTKK.KTTTK.",
        "..KKKKKK..KKKKK.",
    ),
    "run1": (
        "..KPPPKKKPPPK...",
        ".KPPPK...KpPPK..",
        ".KPPK.....KpPK..",
        "KTTTK......KPPK.",
        "KTTTTK.....KTTK.",
        "KttTTK....KTTTTK",
        ".KKKK.....KttTTK",
        "...........KKKK.",
    ),
    "run2": (
        "...KPPPKKPPPK...",
        "..KPPPK..KpPPK..",
        "..KPPK....KpPK..",
        "..KPPK....KPPK..",
        "..KTTK....KTTK..",
        ".KTTTK....KTTTK.",
        ".KttTK....KttTK.",
        ".KKKK......KKKK.",
    ),
    "jump": (
        "...KPPPKKPPPK...",
        "..KPPPK..KpPPK..",
        "..KPPK....KPPK..",
        ".KTTTK....KpPK..",
        ".KTTTTK...KTTK..",
        ".KttTK...KTTTTK.",
        ".KKKK....KKKKKK.",
        "................",
    ),
    "fall": (
        "..KPPPKKKPPPK...",
        "..KPPPK..KpPPK..",
        ".KPPPK....KpPK..",
        ".KPPK.....KPPK..",
        ".KTTK.....KTTK..",
        ".KTTK.....KTTK..",
        "KttTTK...KttTTK.",
        "KKKKKK...KKKKKK.",
    ),
    "dash": (
        "....KPPPPPPPK...",
        "..KPPPPKKKpPPK..",
        ".KPPPK.....KPPK.",
        "KTTTTK......KTTK",
        "KttTTK.....KTTTK",
        ".KKKK......KKKK.",
        "................",
        "................",
    ),
}

# Scarf tail that streams behind the player (drawn on the left, since frames face right).
TAILS = {
    "idle": ((0, 8, "RR"), (0, 9, "r")),
    "run": ((0, 8, "RRR"), (0, 9, "rR"), (0, 10, "r")),
    "air": ((0, 7, "RR"), (0, 8, "R")),
    "dash": ((0, 8, "RRR"), (0, 9, "RrR")),
}

# --- HUD icons ----------------------------------------------------------------
ICON_PALETTE = {
    "K": (20, 16, 28), "R": (224, 70, 84), "W": (255, 255, 255),
    "B": (86, 150, 240), "Y": (250, 214, 90), "C": (170, 238, 255), "c": (78, 170, 232),
    "G": (118, 220, 140), "g": (56, 150, 96),
}

HEART = (
    ".KKK.KKK.",
    "KRRRKRRRK",
    "KRWRRRRRK",
    "KRRRRRRRK",
    ".KRRRRRK.",
    "..KRRRK..",
    "...KRK...",
    "....K....",
)
DROP = (
    "...K...",
    "..KBK..",
    "..KBK..",
    ".KBBBK.",
    "KBWBBBK",
    "KBWBBBK",
    "KBBBBBK",
    ".KBBBK.",
    "..KKK..",
)
BOLT = (
    "...KKK.",
    "..KYYK.",
    ".KYYK..",
    "KYYYYYK",
    ".KKYYK.",
    "...KYK.",
    "..KYK..",
    "..KK...",
)
DASH_ICON = (
    "............",
    ".cc..CC.....",
    "..cc..CC....",
    "...cc..CC...",
    "....cc..CC..",
    "...cc..CC...",
    "..cc..CC....",
    ".cc..CC.....",
    "............",
)


def surface_from_rows(rows, palette, scale=SCALE):
    width = max(len(r) for r in rows)
    surf = pygame.Surface((width * scale, len(rows) * scale), pygame.SRCALPHA)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            color = palette.get(ch)
            if color is not None:
                surf.fill(color, (x * scale, y * scale, scale, scale))
    return surf


def hero_rows(legs, tail):
    """Compose a full 24-row frame (list of lists of chars) facing right."""
    rows = [list(r) for r in UPPER] + [list(r) for r in LEGS[legs]]
    for x, y, text in TAILS[tail]:
        for i, ch in enumerate(text):
            if rows[y][x + i] == ".":
                rows[y][x + i] = ch
    return ["".join(r) for r in rows]


# Animation table: state -> list of (legs, tail) frames.
FRAMES = {
    "idle": [("stand", "idle")],
    "run": [("run1", "run"), ("stand", "run"), ("run2", "run"), ("stand", "run")],
    "jump": [("jump", "air")],
    "fall": [("fall", "air")],
    "dash": [("dash", "dash")],
}


class HeroSprites:
    """Builds and caches every hero frame (both facings) plus tinted ghost copies."""

    def __init__(self):
        self.frames = {}
        self._ghosts = {}
        for state, frames in FRAMES.items():
            for index, (legs, tail) in enumerate(frames):
                right = surface_from_rows(hero_rows(legs, tail), PALETTE)
                self.frames[(state, index, 1)] = right
                self.frames[(state, index, -1)] = pygame.transform.flip(right, True, False)

    def frame(self, key):
        return self.frames[key]

    def count(self, state):
        return len(FRAMES[state])

    def ghost(self, key, color):
        """Single-color silhouette of a frame (used for dash afterimages and hit flashes)."""
        cache_key = (key, color)
        ghost = self._ghosts.get(cache_key)
        if ghost is None:
            mask = pygame.mask.from_surface(self.frames[key])
            ghost = mask.to_surface(setcolor=color + (255,) if len(color) == 3 else color,
                                    unsetcolor=(0, 0, 0, 0))
            self._ghosts[cache_key] = ghost
        return ghost


_hero_sprites = None


def get_hero_sprites():
    global _hero_sprites
    if _hero_sprites is None:
        _hero_sprites = HeroSprites()
    return _hero_sprites


_icon_cache = {}


def icon(rows, scale=2, palette=ICON_PALETTE):
    key = (id(rows), scale)
    surf = _icon_cache.get(key)
    if surf is None:
        surf = _icon_cache[key] = surface_from_rows(rows, palette, scale)
    return surf
