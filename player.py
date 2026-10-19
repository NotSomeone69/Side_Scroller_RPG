"""Player input, movement, collision resolution, ramps, drop-through, stats and abilities."""
import math
import pygame
from settings import (
    GRAVITY, MAX_FALL_SPEED, MOVE_SPEED, WALK_SPEED, RUN_DELAY, CROUCH_SPEED, HURT_STUN, JUMP_SPEED, MAX_STEP_SIZE, MAX_STEP_UP, MAX_STEP_DOWN,
    SLIDE_ACCEL, MAX_SLIDE_SPEED, DROP_THROUGH_TIME, PLAYER_WIDTH, PLAYER_HEIGHT,
    SOLID_TYPES, TOP_ONLY_TYPES, SLOPE_ONE_WAY, SLOPE_SOLID, STEEP_ANGLE, SLOPE_EPS,
    KILL, DAMAGE_INVINCIBILITY, RESPAWN_INVINCIBILITY, HURT_HOP_SPEED, VOID_MARGIN,
)
from stats import Stats
from abilities import Dash, SwordCombo
from animation import SpriteSheet, Animator
from effects import Particles
import assets

_sheet = None


def vampire_sheet():
    """The main character's animation sheet (assets/characters/vampire.png + .json), loaded once."""
    global _sheet
    if _sheet is None:
        _sheet = SpriteSheet(assets.path("characters", "vampire.json"))
    return _sheet


class Player:
    def __init__(self, x, y, fx=None):
        self.x = float(x)
        self.y = float(y)
        self.rect = pygame.Rect(round(x), round(y), PLAYER_WIDTH, PLAYER_HEIGHT)
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground = False
        self.ground_object = None
        self.slide_speed = 0.0
        self.drop_timer = 0.0
        self.space_s_was_held = False

        # --- state shared with abilities -------------------------------------
        self.facing = 1                 # +1 right, -1 left
        self.vx_override = None         # an ability may take over horizontal velocity
        self.gravity_scale = 1.0        # an ability may reduce/disable gravity
        self.pose = None                # animation state forced by an ability ("dash")
        self.dead = False
        self.events = []                # ("damage", n) / ("death", cause) / ("dash", dir) -> read by Game
        self.fx = fx if fx is not None else Particles()

        self.stats = Stats()
        self.abilities = []
        self._ability_keys = {}
        self.add_ability(Dash())
        self.add_ability(SwordCombo())

        self.sprites = vampire_sheet()
        self.anim = Animator(self.sprites, "idle")
        self.anim_time = 0.0
        self._dust_timer = 0.0
        self._input_x = 0
        self.run_timer = 0.0
        self._last_dir = 0
        self.crouching = False
        self.hurt_timer = 0.0
        self.attack_hitbox = None       # set by the sword combo while a strike is active

    # ------------------------------------------------------------------ API
    def add_ability(self, ability):
        self.abilities.append(ability)
        for key in ability.keys:
            self._ability_keys[key] = ability
        return ability

    def get_ability(self, name):
        return next((a for a in self.abilities if a.name == name), None)

    def pop_events(self):
        events, self.events = self.events, []
        return events

    @property
    def frame_key(self):
        return (self.anim.name, self.anim.index, self.facing)

    @property
    def death_time_left(self):
        """Seconds until the death animation (bats flying away) has finished."""
        return max(0.0, self.anim.duration("death") - self.anim.time) if self.dead else 0.0

    @property
    def is_invulnerable(self):
        return self.stats.invincible or any(a.active and a.invulnerable for a in self.abilities)

    def sync_rect(self):
        self.rect.x = round(self.x)
        self.rect.y = round(self.y)

    def teleport(self, x, y):
        """Place the player somewhere (level change / respawn) and clear all motion state."""
        self.x, self.y = float(x), float(y)
        self.vx = self.vy = 0.0
        self.on_ground = False
        self.ground_object = None
        self.slide_speed = 0.0
        self.drop_timer = 0.0
        self.vx_override = None
        self.gravity_scale = 1.0
        self.pose = None
        self.hurt_timer = 0.0
        self.attack_hitbox = None
        for ability in self.abilities:
            ability.interrupt(self, None)
        self.sync_rect()

    def respawn(self, x, y):
        self.teleport(x, y)
        self.dead = False
        self.anim.play("idle", restart=True)
        self.stats.revive(RESPAWN_INVINCIBILITY)
        for ability in self.abilities:
            ability.reset(self)
        self.fx.burst(self.x + 16, self.y + 24, 14, ((128, 0, 0), (226, 200, 196)),
                      speed=(60, 260), life=(0.25, 0.55), size=(2, 4), gravity=-100.0)

    def take_damage(self, amount, invincibility=DAMAGE_INVINCIBILITY, hop=False):
        """Returns True if the hit landed. Invincible players ignore it."""
        if self.dead or self.is_invulnerable:
            return False
        if not self.stats.take_damage(amount, invincibility):
            return False
        self.events.append(("damage", amount))
        self.fx.burst(self.rect.centerx, self.rect.centery, 12, ((192, 0, 0), (128, 0, 0), (226, 200, 196)),
                      speed=(80, 280), life=(0.2, 0.5), size=(2, 4), gravity=520.0)
        if self.stats.is_dead:
            self.kill("damage")
            return True
        for ability in self.abilities:
            ability.interrupt(self, None)          # being hit cancels dashes and sword swings
        self.hurt_timer = HURT_STUN
        self.anim.play("hurt", restart=True)
        if hop:
            self.vy = -HURT_HOP_SPEED
            self.on_ground = False
            self.ground_object = None
        return True

    def kill(self, cause="unknown"):
        """Instant death (kill platform, void, 0 health). The Game respawns the player."""
        if self.dead:
            return
        self.dead = True
        self.stats.health.lose(self.stats.health.value)
        for ability in self.abilities:
            ability.reset(self)
        self.vx = self.vy = 0.0
        self.vx_override = None
        self.gravity_scale = 1.0
        self.pose = None
        self.attack_hitbox = None
        self.anim.play("death", restart=True)
        palette = ((255, 214, 96), (255, 120, 40), (255, 240, 190)) if cause == KILL \
            else ((86, 130, 214), (242, 204, 160), (222, 72, 82))
        self.fx.burst(self.rect.centerx, self.rect.centery, 12, ((128, 0, 0), (74, 0, 0), (192, 0, 0)),
                      speed=(40, 220), life=(0.4, 0.9), size=(2, 4), gravity=700.0)
        self.events.append(("death", cause))

    # ----------------------------------------------------------- collisions
    def _rect_at(self, x=None, y=None):
        return pygame.Rect(round(self.x if x is None else x), round(self.y if y is None else y),
                           PLAYER_WIDTH, PLAYER_HEIGHT)

    @staticmethod
    def _overlap_x(left, right, rect):
        return right > rect.left and left < rect.right

    def _overlaps_solid(self, level):
        rect = self._rect_at()
        for platform in level.solid_platforms:
            if platform.active and rect.colliderect(platform.rect):
                return True
        return False

    def _slope_surface(self, slope):
        left = max(self.x, slope.x)
        right = min(self.x + PLAYER_WIDTH, slope.right)
        if right <= left:
            return None
        return slope.surface_y(right if slope.up_right else left)

    @staticmethod
    def _slope_overlap(slope, x, y):
        """Returns (overlap, pen) for a player whose top-left is (x, y).

        overlap: thickness (px) of the ramp body inside the player's column at the highest ramp
                 point the player touches (<= 0 means no contact).
        pen:     how far the feet are below the ramp surface there (what it takes to lift the
                 player onto the surface).
        """
        left = x if x > slope.x else slope.x
        right = x + PLAYER_WIDTH
        if right > slope.right:
            right = slope.right
        if right <= left or y >= slope.base:
            return 0.0, 0.0                              # no horizontal overlap / player is below the ramp
        progress = ((right if slope.up_right else left) - slope.x) / slope.width
        surface = slope.y + slope.height * ((1.0 - progress) if slope.up_right else progress)
        feet = y + PLAYER_HEIGHT
        top = surface if surface > y else y
        bottom = feet if feet < slope.base else slope.base
        return bottom - top, feet - surface

    def _resolve_horizontal(self, target_x, step_dx, support, level):
        test = self._rect_at(target_x, self.y)
        for platform in level.solid_platforms:
            if not platform.active:
                continue
            wall = platform.rect
            if not test.colliderect(wall):
                continue
            feet_y = self.y + PLAYER_HEIGHT
            can_step_up = (
                support is not None and getattr(support, "kind", None) in (SLOPE_ONE_WAY, SLOPE_SOLID)
                and self.y < wall.top and -1 <= feet_y - wall.top <= MAX_STEP_UP
            )
            if can_step_up:
                return target_x, float(wall.top - PLAYER_HEIGHT), False
            return (float(wall.left - PLAYER_WIDTH) if step_dx > 0 else float(wall.right)), self.y, True

        # Solid ramp end faces: block entry from the steep/high end's vertical side.
        for slope in level.solid_slopes:
            if not (self.y < slope.base and self.y + PLAYER_HEIGHT > slope.y + 0.01):
                continue
            if slope.up_right and step_dx < 0:
                if self.x >= slope.right - .001 and target_x < slope.right:
                    return slope.right, self.y, True
            elif not slope.up_right and step_dx > 0:
                if self.x + PLAYER_WIDTH <= slope.x + .001 and target_x + PLAYER_WIDTH > slope.x:
                    return slope.x - PLAYER_WIDTH, self.y, True
        return target_x, self.y, False

    def _follow_slope(self, support, level, step_dx):
        if support is None:
            return
        feet = self.y + PLAYER_HEIGHT
        support_rect = getattr(support, "rect", None)       # a flat platform we are stepping off
        best = None
        for slope in level.slopes:
            surface = self._slope_surface(slope)
            if surface is None:
                continue
            # Steep ramps are slippery: you can't walk *onto* them from the side, only stay on one
            # you are already standing on (the side entry is handled by _resolve_slope_entry).
            if slope.steep:
                if support is not slope:
                    continue
                # A dash must not "climb" a steep ramp (it would rocket up it): treat it as a wall.
                if self.vx_override is not None and step_dx and (step_dx > 0) == slope.up_right:
                    continue
            # Do not sink through the side/top of a flat platform while stepping off it.
            if (support_rect is not None and getattr(support, "kind", None) in SOLID_TYPES
                    and self._overlap_x(self.x, self.x + PLAYER_WIDTH, support_rect)
                    and abs(feet - support_rect.top) <= 2 and surface > support_rect.top):
                continue
            difference = surface - feet
            step_gap = slope.gradient * abs(step_dx) + 3.5
            if -max(step_gap, MAX_STEP_UP) <= difference <= max(step_gap, MAX_STEP_DOWN) or support is slope:
                if best is None or abs(difference) < best[0]:
                    best = (abs(difference), slope, surface)
        if best is not None:
            new_y, ground = best[2] - PLAYER_HEIGHT, best[1]
            # A ramp may dip below a floor it overlaps (level_01's ramp at x=1100): never follow the
            # surface down into a solid platform, stand on the platform instead.
            for platform in level.solid_platforms:
                r = platform.rect
                if (platform.active and self.x + PLAYER_WIDTH > r.left and self.x < r.right
                        and new_y + PLAYER_HEIGHT > r.top + 0.01 and new_y < r.bottom and feet <= r.top + 1.0):
                    new_y, ground = float(r.top - PLAYER_HEIGHT), platform
            self.y = new_y
            self.ground_object = ground

    def _resolve_slope_entry(self, level, old_x, old_y, step_dx):
        """Stop the player from sinking into a ramp's body through its sloped face.

        Called after every 3px horizontal sub-step. Shallow ramps lift the feet onto the
        surface (walking up); steep ramps and ramp corners act as a wall from the side. Works in
        the air too, which is what makes dashing into a ramp safe. Returns True if the move was
        cancelled.
        """
        ignore_one_way = self.drop_timer > 0.0
        for slope in level.slopes:
            one_way = slope.kind == SLOPE_ONE_WAY
            if ignore_one_way and one_way:
                continue
            overlap, pen = self._slope_overlap(slope, self.x, self.y)
            if overlap <= SLOPE_EPS:
                continue
            old_overlap = self._slope_overlap(slope, old_x, old_y)[0]
            # Only a small *increase* in overlap is a hit on the sloped face / tip. A big jump means
            # we came in through the vertical end face or from below (allowed for one-way ramps).
            if overlap - max(old_overlap, 0.0) > slope.gradient * abs(step_dx) + 2.0:
                continue
            if one_way and pen > MAX_STEP_UP:
                continue                                   # feet well below the surface: passing through
            if one_way:
                entering = old_overlap <= SLOPE_EPS
            else:
                entering = overlap > old_overlap + SLOPE_EPS
            if not entering:
                continue
            if not slope.steep and pen <= MAX_STEP_UP:
                self.y -= pen                              # lift the feet exactly onto the surface
                if not self._overlaps_solid(level):
                    continue
            self.x, self.y = old_x, old_y                  # steep ramp / corner / no headroom: wall
            return True
        return False

    def _step_horizontal(self, step_dx, support, was_grounded, level):
        """One horizontal sub-step. Returns True when the player was blocked."""
        old_x, old_y = self.x, self.y
        target_x, target_y, hit = self._resolve_horizontal(self.x + step_dx, step_dx, support, level)
        self.x, self.y = target_x, target_y
        if was_grounded and not hit:
            self._follow_slope(support, level, step_dx)
        # Ramps are checked even after a wall clamp: the clamped spot can sit inside a ramp corner.
        if self._resolve_slope_entry(level, old_x, old_y, step_dx):
            return True
        return hit

    def probe_blocked(self, dx, level):
        """Would moving ``dx`` px horizontally be blocked right now? (no side effects)"""
        x, y, ground = self.x, self.y, self.ground_object
        blocked = self._step_horizontal(dx, ground if self.on_ground else None, self.on_ground, level)
        self.x, self.y, self.ground_object = x, y, ground
        return blocked

    def _carry_with_moving_platform(self, platform, dx, dy, level):
        # Platform moves independently. Resolve the rider's carry against walls;
        # if blocked, the platform continues beneath them and they eventually fall.
        if abs(dx) > 0:
            target, _, hit = self._resolve_horizontal(self.x + dx, dx, platform, level)
            self.x = target
            if hit:
                self.vx = 0
        if abs(dy) > 0:
            old_y = self.y
            target_y = self.y + dy
            rect = self._rect_at(self.x, target_y)
            blocked = False
            for p in level.solid_platforms:
                if p.active and rect.colliderect(p.rect):
                    blocked = True
                    break
            if not blocked:
                self.y = target_y
            elif dy < 0:
                self.y = old_y
        self.sync_rect()
        still_over = self.x + PLAYER_WIDTH > platform.rect.left and self.x < platform.rect.right
        feet_close = abs(self.y + PLAYER_HEIGHT - platform.rect.top) <= 3
        if not (still_over and feet_close):
            self.on_ground = False
            self.ground_object = None

    # --------------------------------------------------------------- update
    def update(self, dt, keys, pressed, level):
        """``pressed`` is the set of keys that went down this frame (jump + ability triggers)."""
        self.anim_time += dt
        if self.dead:
            self.anim.update(dt)
            return
        self.stats.update(dt)
        if self.hurt_timer > 0.0:
            self.hurt_timer = max(0.0, self.hurt_timer - dt)

        previous_support = self.ground_object if self.on_ground else None
        # Moving platforms advance independently, then carry their rider if possible.
        level.update_moving_platforms(dt)
        if previous_support is not None and getattr(previous_support, "is_moving", False):
            self._carry_with_moving_platform(previous_support, previous_support.delta_x,
                                             previous_support.delta_y, level)

        # Abilities: tick timers, then start any whose key was pressed.
        for ability in self.abilities:
            ability.update(dt, self, level)
        for key in pressed:
            ability = self._ability_keys.get(key)
            if ability is not None:
                ability.try_use(self, level)

        jump_pressed = pygame.K_SPACE in pressed
        combo = keys[pygame.K_SPACE] and keys[pygame.K_s]
        just_dropped = False
        if combo and not self.space_s_was_held and self.on_ground:
            support = self.ground_object
            kind = getattr(support, "kind", None)
            if kind in TOP_ONLY_TYPES or kind == SLOPE_ONE_WAY:
                self.drop_timer = DROP_THROUGH_TIME
                self.vy = 90.0
                self.on_ground = False
                self.ground_object = None
                self.slide_speed = 0.0
                just_dropped = True
        if not just_dropped and jump_pressed and self.on_ground:
            for ability in self.abilities:
                if ability.active and ability.cancel_on_jump:
                    ability.interrupt(self, level)
            self.vy = -JUMP_SPEED
            self.on_ground = False
            self.ground_object = None
            self.slide_speed = 0.0
        self.space_s_was_held = combo
        self.drop_timer = max(0.0, self.drop_timer - dt)

        was_grounded = self.on_ground
        support = self.ground_object if was_grounded else None
        self._move_horizontal(dt, keys, support, was_grounded, level)
        impact = self.vy
        self._move_vertical(dt, level)
        if self.on_ground and not was_grounded and impact > 420.0:
            self.fx.dust(self.x + 16, self.y + PLAYER_HEIGHT, 0, count=6)

        # If a moving platform slid out from under the rider, gravity takes over.
        self.sync_rect()
        level.update_platform_timers(dt, self)
        self.sync_rect()
        self._check_world_contacts(level)
        self._update_animation(dt)

    def _move_horizontal(self, dt, keys, support, was_grounded, level):
        input_x = int(keys[pygame.K_d] or keys[pygame.K_RIGHT]) - int(keys[pygame.K_q] or keys[pygame.K_LEFT])
        if self.hurt_timer > 0.0:
            input_x = 0                                    # stunned
        self._input_x = input_x
        if input_x and input_x == self._last_dir:
            self.run_timer += dt                           # holding a direction: walk turns into run
        else:
            self.run_timer = 0.0
        self._last_dir = input_x
        down = keys[pygame.K_s] or keys[pygame.K_DOWN]
        steep = getattr(support, "steep", False)
        self.crouching = bool(down and was_grounded and not steep and self.vx_override is None
                              and self.hurt_timer <= 0.0)
        if self.vx_override is not None:                   # e.g. dashing / mid sword swing
            self.vx = self.vx_override
            self.slide_speed = 0.0
        else:
            if input_x:
                self.facing = input_x
            speed = MOVE_SPEED
            if was_grounded:
                speed = MOVE_SPEED if self.run_timer >= RUN_DELAY else WALK_SPEED
                if self.crouching:
                    speed = CROUCH_SPEED
            self.vx = input_x * speed
            if was_grounded and support is not None and steep:
                self.slide_speed = min(MAX_SLIDE_SPEED, self.slide_speed + SLIDE_ACCEL * dt)
                self.vx += support.downhill_direction() * self.slide_speed
            else:
                self.slide_speed = 0.0

        dx = self.vx * dt
        steps = max(1, math.ceil(abs(dx) / MAX_STEP_SIZE))
        step_dx = dx / steps
        for _ in range(steps):
            if self._step_horizontal(step_dx, support, was_grounded, level):
                self.vx = 0.0
                for ability in self.abilities:
                    if ability.active:
                        ability.on_blocked(self, level)
                break

    def _move_vertical(self, dt, level):
        # Gravity and vertical collisions, split into small steps to prevent tunneling.
        self.vy = min(self.vy + GRAVITY * dt * self.gravity_scale, MAX_FALL_SPEED)
        dy = self.vy * dt
        steps = max(1, math.ceil(abs(dy) / MAX_STEP_SIZE))
        step_dy = dy / steps
        self.on_ground = False
        self.ground_object = None
        solids = level.solid_platforms
        top_only = level.top_only_platforms
        slopes = level.slopes
        solid_slopes = level.solid_slopes
        for _ in range(steps):
            old_y = self.y
            old_top, old_bottom = old_y, old_y + PLAYER_HEIGHT
            self.y += step_dy
            landed = False

            for platform in solids:
                if not platform.active:
                    continue
                wall = platform.rect
                # Float geometry on purpose: testing the *rounded* rect made resting contact
                # flicker (Python rounds 502.5 down), so on_ground toggled and jumps could be missed.
                new_bottom = self.y + PLAYER_HEIGHT
                if new_bottom < wall.top or self.y > wall.bottom:
                    continue
                if not self._overlap_x(self.x, self.x + PLAYER_WIDTH, wall):
                    continue
                if step_dy >= 0 and old_bottom <= wall.top + 1 and new_bottom >= wall.top:
                    self.y = float(wall.top - PLAYER_HEIGHT)
                    self.vy = 0
                    self.on_ground, self.ground_object, landed = True, platform, True
                    break
                if step_dy < 0 and old_top >= wall.bottom - 1 and self.y <= wall.bottom:
                    self.y = float(wall.bottom)
                    self.vy = 0
                    landed = True
                    break
            if landed:
                continue

            # Solid ramp underside blocks jumps from below.
            if step_dy < 0:
                for slope in solid_slopes:
                    overlap = self.x + PLAYER_WIDTH > slope.x and self.x < slope.right
                    if overlap and old_top >= slope.base - 1 and self.y <= slope.base:
                        self.y = float(slope.base)
                        self.vy = 0
                        landed = True
                        break
            if landed:
                continue

            # One-way platform tops.
            if step_dy >= 0 and self.drop_timer <= 0:
                for platform in top_only:
                    if not platform.active:
                        continue
                    rect_p = platform.rect
                    overlap = self.x + PLAYER_WIDTH > rect_p.left and self.x < rect_p.right
                    crossed = old_bottom <= rect_p.top + 1 and self.y + PLAYER_HEIGHT >= rect_p.top
                    if overlap and crossed:
                        self.y = float(rect_p.top - PLAYER_HEIGHT)
                        self.vy = 0
                        self.on_ground, self.ground_object, landed = True, platform, True
                        break
            if landed:
                continue

            # Ramp top surfaces. Only old brown ramps can be dropped through.
            if step_dy >= 0:
                for slope in slopes:
                    if slope.kind == SLOPE_ONE_WAY and self.drop_timer > 0:
                        continue
                    surface = self._slope_surface(slope)
                    if surface is None:
                        continue
                    if old_bottom <= surface + 1 and self.y + PLAYER_HEIGHT >= surface:
                        self.y = surface - PLAYER_HEIGHT
                        self.vy = 0
                        self.on_ground, self.ground_object, landed = True, slope, True
                        break

    # ------------------------------------------------------- world contacts
    def _check_world_contacts(self, level):
        if self.y > level.height + VOID_MARGIN:
            self.kill("void")
            return
        rect = self.rect
        for hazard in level.hazards:
            if rect.colliderect(hazard.hitbox):
                if hazard.kind == KILL:
                    self.kill(KILL)
                    return
                self.take_damage(hazard.damage, hop=rect.centery < hazard.rect.centery)

    # ------------------------------------------------------------ animation
    def _update_animation(self, dt):
        if self.pose:
            state = self.pose
        elif self.hurt_timer > 0.0:
            state = "hurt"
        elif not self.on_ground:
            state = "jump" if self.vy < 0 else "fall"
        elif self.crouching:
            state = "crouch"
        elif self._input_x and abs(self.vx) > 1.0:
            state = "run" if self.run_timer >= RUN_DELAY else "walk"
        else:
            state = "idle"
        self.anim.play(state)
        self.anim.update(dt)
        if state == "run":
            self._dust_timer -= dt
            if self._dust_timer <= 0.0:
                self._dust_timer = 0.16
                self.fx.dust(self.x + 16, self.y + PLAYER_HEIGHT, self.facing, count=1)

    def draw(self, surface, camera_x):
        for ability in self.abilities:
            ability.draw_behind(surface, camera_x, self)
        if self.dead and self.anim.finished:
            return                                          # the bats have flown away
        ox, oy = self.sprites.origin
        pos = (self.rect.centerx - ox - round(camera_x), self.rect.bottom - oy)
        stats = self.stats
        key = self.frame_key
        if not self.dead and stats.hit_flash > 0.0:        # white flash on the hit frame(s)
            ghost = self.sprites.ghost(key, (255, 255, 255))
            ghost.set_alpha(255)
            surface.blit(ghost, pos)
        elif not self.dead and stats.invincible_timer > 0.0 and int(self.anim_time * 16) % 2:
            ghost = self.sprites.ghost(key, (255, 255, 255))   # visible invincibility blink
            ghost.set_alpha(120)
            surface.blit(ghost, pos)
        else:
            surface.blit(self.anim.surface(self.facing), pos)
