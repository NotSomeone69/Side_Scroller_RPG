"""Level construction, decoration layers and world-object updates."""
import pygame
from platforms import Platform, Slope
from settings import (
    START_LEVEL, SLOPE_SOLID, TRANSITION, TOP_ONLY_TYPES, CRUMBLE_TYPES, MOVING_TYPES,
    DEFAULT_BACKGROUND, GRID, SCREEN_HEIGHT,
)
from levels import load_definition
from skins import get_tileset
import assets


class Prop:
    """A free-placed decoration sprite (candelabra, banner...). Optionally animated."""

    def __init__(self, name, x, y, **options):
        self.name, self.x, self.y = name, x, y
        self.options = options
        self.layer = options.get("layer", "back")                 # "back" (behind) or "front" (over the player)
        self.image = assets.load_image(assets.path("props", name + ".png"))
        meta = assets.load_json(assets.path("props", name + ".json"), {})
        self.frames = max(1, int(options.get("frames", meta.get("frames", 1))))
        self.fps = float(options.get("fps", meta.get("fps", 8)))
        self.w = self.image.get_width() // self.frames
        self.h = self.image.get_height()
        self.rect = pygame.Rect(x, y, self.w, self.h)

    def draw(self, surface, camera_x, t):
        x = self.x - round(camera_x)
        if x + self.w < 0 or x > surface.get_width():
            return
        f = int(t * self.fps) % self.frames if self.frames > 1 else 0
        surface.blit(self.image, (x, self.y), (f * self.w, 0, self.w, self.h))


class TileLayer:
    """A grid of decoration tiles that the player can't touch. Pre-rendered once."""

    def __init__(self, spec, width, height):
        self.name = spec.get("name", "Layer")
        self.order = spec.get("order", "back")                    # "back" or "front"
        self.dim = float(spec.get("dim", 0.0))                    # 0..1 darkening (depth)
        self.tiles = list(spec.get("tiles", []))                  # (tx, ty, tileset, col, row)
        self.surface = None
        self.size = (width, height)

    def build(self):
        w, h = self.size
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        for tx, ty, tileset, col, row in self.tiles:
            surf.blit(get_tileset(tileset).tile(col, row), (tx * GRID, ty * GRID))
        if self.dim > 0:
            v = int(255 * (1 - self.dim))
            surf.fill((v, v, v, 255), special_flags=pygame.BLEND_RGB_MULT)
        self.surface = surf

    def draw(self, surface, camera_x):
        if self.surface is None:
            self.build()
        view_w, view_h = surface.get_size()
        x = max(0, min(round(camera_x), self.size[0] - 1))
        surface.blit(self.surface, (0, 0), (x, 0, min(view_w, self.size[0] - x), min(view_h, self.size[1])))


class Level:
    """Builds all world objects from a level module and keeps pre-filtered lists
    so the player's collision code never has to filter by type per frame."""

    def __init__(self, definition=START_LEVEL):
        if not hasattr(definition, "PLATFORMS"):          # a level *name* (or None -> LevelError)
            self.id = definition
            definition = load_definition(definition)
        else:
            self.id = definition.__name__.rsplit(".", 1)[-1]
        self.definition = definition
        self.name = getattr(definition, "NAME", str(self.id).replace("_", " ").title())
        self.width = definition.LEVEL_WIDTH
        self.height = definition.LEVEL_HEIGHT
        self.player_start = definition.PLAYER_START
        self.background_name = getattr(definition, "BACKGROUND", DEFAULT_BACKGROUND)
        self.time = 0.0                                    # drives animated tiles

        self.platforms = [Platform(*entry[:5], **(entry[5] if len(entry) > 5 else {}))
                          for entry in definition.PLATFORMS]
        self.slopes = [Slope(*entry[:6], **(entry[6] if len(entry) > 6 else {}))
                       for entry in definition.SLOPES]
        self.props = [Prop(e[0], e[1], e[2], **(e[3] if len(e) > 3 else {})) for e in getattr(definition, "PROPS", [])]
        layers = [TileLayer(spec, self.width, self.height) for spec in getattr(definition, "TILE_LAYERS", [])]
        self.back_layers = [l for l in layers if l.order != "front"]
        self.front_layers = [l for l in layers if l.order == "front"]
        self.back_props = [p for p in self.props if p.layer != "front"]
        self.front_props = [p for p in self.props if p.layer == "front"]

        self.solid_platforms = [p for p in self.platforms if p.is_solid]
        self.top_only_platforms = [p for p in self.platforms if p.kind in TOP_ONLY_TYPES]
        self.moving_platforms = [p for p in self.platforms if p.kind in MOVING_TYPES]
        self.crumble_platforms = [p for p in self.platforms if p.kind in CRUMBLE_TYPES]
        self.hazards = [p for p in self.platforms if p.is_hazard]
        self.transitions = [p for p in self.platforms if p.kind == TRANSITION]
        self.solid_slopes = [s for s in self.slopes if s.kind == SLOPE_SOLID]
        # Portals are drawn first so the player walks in front of them.
        self._draw_order = self.transitions + [p for p in self.platforms if p.kind != TRANSITION]

    # -- simulation -----------------------------------------------------------
    def update_moving_platforms(self, dt):
        solids = self.solid_platforms
        for platform in self.moving_platforms:
            platform.update_movement(dt, solids)

    def update_platform_timers(self, dt, player):
        for platform in self.crumble_platforms:
            standing_here = player.on_ground and player.ground_object is platform
            was_active = platform.active
            platform.update_crumble(dt, standing_here)
            if was_active and not platform.active and player.ground_object is platform:
                player.on_ground = False
                player.ground_object = None

    def touching_transition(self, rect):
        for box in self.transitions:
            if rect.colliderect(box.trigger_rect):
                return box
        return None

    # -- drawing (back -> world -> [player] -> front) ---------------------------------
    def draw_back(self, surface, camera):
        for layer in self.back_layers:
            layer.draw(surface, camera.x)
        for prop in self.back_props:
            prop.draw(surface, camera.x, self.time)

    def draw(self, surface, camera, font):
        for platform in self._draw_order:
            platform.draw(surface, camera.x, font, self.time)
        for slope in self.slopes:
            slope.draw(surface, camera.x, font, self.time)

    def draw_front(self, surface, camera):
        for prop in self.front_props:
            prop.draw(surface, camera.x, self.time)
        for layer in self.front_layers:
            layer.draw(surface, camera.x)
