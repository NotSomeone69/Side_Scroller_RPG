"""Platform and slope entities. Their data is defined by the level files; their look comes from skins."""

import math
import pygame
from settings import (
    SOLID, ONE_WAY, MOVING_VERTICAL, MOVING_HORIZONTAL,
    CRUMBLE_RESET, CRUMBLE_PERSISTENT, SLOPE_ONE_WAY, SLOPE_SOLID,
    KILL, DAMAGE, TRANSITION, DEFAULT_SKINS,
    MOVING_TYPES, CRUMBLE_TYPES, HAZARD_TYPES, SOLID_TYPES, STEEP_ANGLE,
    DAMAGE_PLATFORM_DAMAGE,
)
from skins import get_skin


class Platform:
    def __init__(self, kind, x, y, width, height, **options):
        self.kind = kind
        self.rect = pygame.Rect(round(x), round(y), width, height)
        self.active = True
        self.options = options
        self.direction = options.get("direction", 1)
        self.speed = float(options.get("speed", 0.0))
        self.min_x = float(options.get("min_x", x))
        self.max_x = float(options.get("max_x", x))
        self.min_y = float(options.get("min_y", y))
        self.max_y = float(options.get("max_y", y))
        self.x_float = float(x)
        self.y_float = float(y)
        self.delta_x = 0.0
        self.delta_y = 0.0
        self.break_after = float(options.get("break_after", 3.0))
        self.respawn_after = float(options.get("respawn_after", 1.5))
        self.stand_timer = 0.0
        self.triggered = False
        self.timer = 0.0
        self.respawn_timer = 0.0

        # Hazards: slightly inflated hitbox so resting on top still counts as touching.
        self.damage = options.get("damage", DAMAGE_PLATFORM_DAMAGE)
        self.hitbox = self.rect.inflate(4, 4) if kind in HAZARD_TYPES else self.rect
        # Transition boxes: where they lead. ``spawn`` is the player's top-left in the target level.
        self.target = options.get("target")
        spawn = options.get("spawn")
        self.spawn = (float(spawn[0]), float(spawn[1])) if spawn else None
        self.trigger_rect = self.rect.inflate(2, 2) if kind == TRANSITION else self.rect

        # Texture: any platform can pick its own skin / per-slot tile overrides.
        self.skin_name = options.get("skin") or DEFAULT_SKINS[kind]
        self.tile_overrides = options.get("tiles") or None
        self._label = None

    # -- classification ----------------------------------------------------
    @property
    def is_moving(self):
        return self.kind in MOVING_TYPES

    @property
    def is_crumbling(self):
        return self.kind in CRUMBLE_TYPES

    @property
    def is_solid(self):
        return self.kind in SOLID_TYPES

    @property
    def is_hazard(self):
        return self.kind in HAZARD_TYPES

    # -- behaviour ---------------------------------------------------------
    def update_crumble(self, dt, player_standing_here):
        if not self.is_crumbling:
            return
        if not self.active:
            self.respawn_timer -= dt
            if self.respawn_timer <= 0:
                self.active = True
                self.respawn_timer = 0.0
                self.stand_timer = 0.0
                self.triggered = False
                self.timer = 0.0
            return

        if self.kind == CRUMBLE_RESET:
            if player_standing_here:
                self.stand_timer += dt
                if self.stand_timer >= self.break_after:
                    self.break_now()
            else:
                self.stand_timer = 0.0
        else:
            if player_standing_here:
                self.triggered = True
            if self.triggered:
                self.timer += dt
                if self.timer >= self.break_after:
                    self.break_now()

    def break_now(self):
        self.active = False
        self.respawn_timer = self.respawn_after
        self.stand_timer = 0.0
        self.timer = 0.0
        self.triggered = False

    def update_movement(self, dt, solids):
        """Move along a line. A mover collides with static solid rectangles."""
        self.delta_x = self.delta_y = 0.0
        if not self.is_moving or not self.active:
            return

        horizontal = self.kind == MOVING_HORIZONTAL
        old = self.x_float if horizontal else self.y_float
        low = self.min_x if horizontal else self.min_y
        high = self.max_x if horizontal else self.max_y
        wanted = old + self.speed * self.direction * dt
        if wanted < low:
            wanted = low
            self.direction = 1
        elif wanted > high:
            wanted = high
            self.direction = -1
        delta = wanted - old
        test = self.rect.copy()
        allowed = delta

        for solid in solids:           # ``solids`` only holds solid-type platforms
            if not solid.active:
                continue
            obstacle = solid.rect
            if horizontal:
                if test.bottom <= obstacle.top or test.top >= obstacle.bottom:
                    continue
                if delta > 0 and test.right <= obstacle.left and test.right + allowed > obstacle.left:
                    allowed = min(allowed, obstacle.left - test.right)
                elif delta < 0 and test.left >= obstacle.right and test.left + allowed < obstacle.right:
                    allowed = max(allowed, obstacle.right - test.left)
            else:
                if test.right <= obstacle.left or test.left >= obstacle.right:
                    continue
                if delta > 0 and test.bottom <= obstacle.top and test.bottom + allowed > obstacle.top:
                    allowed = min(allowed, obstacle.top - test.bottom)
                elif delta < 0 and test.top >= obstacle.bottom and test.top + allowed < obstacle.bottom:
                    allowed = max(allowed, obstacle.bottom - test.top)

        if abs(allowed - delta) > 0.001 and abs(delta) > 0.001:
            self.direction *= -1
        if horizontal:
            self.x_float += allowed
            self.rect.x = round(self.x_float)
            self.delta_x = allowed
        else:
            self.y_float += allowed
            self.rect.y = round(self.y_float)
            self.delta_y = allowed

    # -- drawing -----------------------------------------------------------
    def draw(self, surface, camera_x, font, t=0.0):
        if not self.active:
            return
        rect = self.rect.move(-round(camera_x), 0)
        if rect.right < -8 or rect.left > surface.get_width() + 8:
            return
        skin = get_skin(self.skin_name)
        surface.blit(skin.render(rect.width, rect.height, skin.frame_index(t), self.tile_overrides), rect.topleft)
        if self.kind in CRUMBLE_TYPES:
            self._draw_crumble_overlay(surface, rect)
        elif self.kind == TRANSITION and self.target:
            if self._label is None:
                self._label = font.render(f">  {self.target}", True, (150, 120, 120))
            surface.blit(self._label, (rect.centerx - self._label.get_width() // 2,
                                       rect.top - 16 - int(2 * math.sin(t * 3 + self.rect.x))))

    def _draw_crumble_overlay(self, surface, rect):
        show = (self.kind == CRUMBLE_RESET and self.stand_timer > 0.15) or (
            self.kind == CRUMBLE_PERSISTENT and self.triggered)
        if not show:
            return
        if self.kind == CRUMBLE_RESET:
            progress = min(1.0, self.stand_timer / self.break_after)
            crack, bar = (10, 5, 5), (192, 0, 0)
        else:
            progress = min(1.0, self.timer / self.break_after)
            crack, bar = (10, 5, 5), (128, 0, 0)
        pygame.draw.line(surface, crack, (rect.left + rect.width * .35, rect.top + 2),
                         (rect.left + rect.width * .48, rect.bottom - 2), 2)
        pygame.draw.line(surface, crack, (rect.left + rect.width * .48, rect.bottom - 2),
                         (rect.left + rect.width * .62, rect.top + 2), 2)
        surface.fill((20, 4, 6), (rect.left, rect.top - 6, rect.width, 4))
        surface.fill(bar, (rect.left, rect.top - 6, int(rect.width * progress), 4))


# ---------------------------------------------------------------------------
class Slope:
    def __init__(self, kind, x, y, width, height, direction="up_right", **options):
        self.kind = kind
        self.x = float(x)
        self.y = float(y)
        self.width = float(width)
        self.height = float(height)
        self.direction = direction
        self.options = options
        # Pre-computed once; the player's collision code reads these every sub-step.
        self.angle = math.degrees(math.atan(self.height / self.width))
        self.gradient = self.height / self.width
        self.base = self.y + self.height
        self.right = self.x + self.width
        self.steep = self.angle > STEEP_ANGLE
        self.up_right = direction == "up_right"
        self.skin_name = options.get("skin") or DEFAULT_SKINS[kind]
        self.tile_overrides = options.get("tiles") or None

    def surface_y(self, world_x):
        if world_x < self.x or world_x > self.x + self.width:
            return None
        progress = (world_x - self.x) / self.width
        if self.direction == "up_right":
            return self.y + self.height * (1 - progress)
        return self.y + self.height * progress

    def player_surface_y(self, player_x, player_width):
        left = max(float(player_x), self.x)
        right = min(float(player_x + player_width), self.x + self.width)
        if right <= left:
            return None
        sample = right if self.direction == "up_right" else left
        return self.surface_y(sample)

    def downhill_direction(self):
        return -1 if self.direction == "up_right" else 1

    def draw(self, surface, camera_x, font, t=0.0):
        x = round(self.x - camera_x)
        w, h = round(self.width), round(self.height)
        if x + w < 0 or x > surface.get_width():
            return
        skin = get_skin(self.skin_name)
        surface.blit(skin.render_slope(w, h, self.up_right, self.kind == SLOPE_ONE_WAY,
                                       skin.frame_index(t), self.tile_overrides), (x, round(self.y)))
