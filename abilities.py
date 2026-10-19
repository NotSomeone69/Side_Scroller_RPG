"""Ability system.

An ability is a small class that declares *data* (key, cost, cooldown, duration)
and overrides only the hooks it cares about. The Player owns a list of them and
the HUD draws a slot for each one automatically.

Adding a new ability
--------------------
    class Heal(Ability):
        name = "Heal"
        keys = (pygame.K_h,)
        costs = {"mana": 30}
        cooldown = 4.0
        color = (120, 230, 150)
        icon = "heart"                   # a name from assets/ui/icons.json

        def on_start(self, player, level):
            player.stats.health.gain(25)

    # then, once:  player.add_ability(Heal())

Lifecycle: try_use() -> on_start() -> on_update() every frame while ``duration``
lasts -> on_end(). Instant abilities leave ``duration = 0`` and only use on_start().
"""

import pygame

from settings import DASH_SPEED, DASH_DURATION, DASH_COOLDOWN, DASH_COST


class Ability:
    name = "Ability"
    keys = ()                 # pygame key codes that trigger it
    costs = {}                # {"stamina": 30, "mana": 10}; names of Stats resources
    cooldown = 0.0            # seconds
    duration = 0.0            # seconds the ability stays active (0 = instant)
    cancel_on_jump = False    # jumping while it is active interrupts it
    cancel_on_dash = False    # starting a dash interrupts it
    invulnerable = False      # True = no damage while active
    color = (255, 255, 255)   # HUD accent color
    icon = None               # icon name in assets/ui/icons.json

    def __init__(self):
        self.cooldown_left = 0.0
        self.time_left = 0.0
        self.active = False

    # -- state helpers -----------------------------------------------------
    @property
    def cooldown_fraction(self):
        """1.0 right after use, falling to 0.0 when ready again."""
        return self.cooldown_left / self.cooldown if self.cooldown > 0 else 0.0

    def can_use(self, player, level):
        return (not player.dead and not self.active and self.cooldown_left <= 0.0
                and player.stats.can_afford(self.costs))

    def try_use(self, player, level):
        if not self.can_use(player, level):
            return False
        player.stats.spend(self.costs)
        self.cooldown_left = self.cooldown
        self.time_left = self.duration
        self.active = self.duration > 0.0
        self.on_start(player, level)
        return True

    def update(self, dt, player, level):
        self.update_fx(dt, player)
        if self.cooldown_left > 0.0:
            self.cooldown_left = max(0.0, self.cooldown_left - dt)
        if self.active:
            self.time_left -= dt
            self.on_update(dt, player, level)
            if self.active and self.time_left <= 0.0:
                self.stop(player, level)

    def stop(self, player, level, interrupted=False):
        if self.active:
            self.active = False
            self.time_left = 0.0
            self.on_end(player, level, interrupted)

    def interrupt(self, player, level):
        self.stop(player, level, interrupted=True)

    def reset(self, player, level=None):
        """Cancel everything (used on respawn / level change)."""
        self.stop(player, level, interrupted=True)
        self.cooldown_left = 0.0

    # -- hooks to override -------------------------------------------------
    def on_start(self, player, level): pass
    def on_update(self, dt, player, level): pass
    def on_end(self, player, level, interrupted): pass
    def on_blocked(self, player, level): pass      # player ran into a wall/ramp this frame
    def update_fx(self, dt, player): pass          # runs every frame, even when inactive
    def draw_behind(self, surface, camera_x, player): pass


class Dash(Ability):
    """Fast straight dash in the facing direction.

    Safety: the dash is not a teleport. The player keeps moving through the
    normal 3px collision sub-steps, so walls, solid ramps and steep ramps stop
    it exactly like walking would; hitting something ends the dash.
    """

    name = "Dash"
    keys = (pygame.K_LSHIFT, pygame.K_RSHIFT, pygame.K_k)
    costs = {"stamina": DASH_COST}
    cooldown = DASH_COOLDOWN
    duration = DASH_DURATION
    cancel_on_jump = True
    color = (160, 24, 36)
    icon = "dash"

    speed = DASH_SPEED
    GHOST_COLOR = (150, 18, 30)
    TRAIL_LIFE = 0.22
    TRAIL_EVERY = 0.022

    def __init__(self):
        super().__init__()
        self.direction = 1
        self.trail = []            # [x, y, frame_key, age]
        self._trail_timer = 0.0

    def can_use(self, player, level):
        # Don't burn stamina when pressed right up against a wall.
        return super().can_use(player, level) and not player.probe_blocked(player.facing * 3.0, level)

    def on_start(self, player, level):
        for other in player.abilities:
            if other is not self and other.active and other.cancel_on_dash:
                other.interrupt(player, level)
        self.direction = player.facing
        self._apply(player)
        player.pose = "dash"
        player.slide_speed = 0.0
        self._trail_timer = 0.0
        player.fx.dust(player.x + 16, player.y + 48, self.direction, count=8)
        player.events.append(("dash", self.direction))

    def on_update(self, dt, player, level):
        self._apply(player)
        self._trail_timer -= dt
        if self._trail_timer <= 0.0:
            self._trail_timer = self.TRAIL_EVERY
            self.trail.append([player.x, player.y, player.frame_key, 0.0])
            if player.on_ground:
                player.fx.dust(player.x + 16, player.y + 48, self.direction, count=1)

    def on_end(self, player, level, interrupted):
        player.vx_override = None
        player.gravity_scale = 1.0
        player.pose = None
        player.vy = 0.0 if player.vy < 0 else player.vy

    def on_blocked(self, player, level):
        if self.active:
            # Little spark burst where we hit the wall.
            x = player.x + (32 if self.direction > 0 else 0)
            player.fx.burst(x, player.y + 26, 7, ((226, 200, 190), self.GHOST_COLOR),
                            speed=(60, 200), angle=(-1.2, 1.2) if self.direction < 0 else (2.0, 4.3),
                            life=(0.15, 0.35), size=(2, 4), gravity=300.0)
            self.interrupt(player, level)

    def _apply(self, player):
        player.vx_override = self.direction * self.speed
        player.vy = 0.0
        player.gravity_scale = 0.0

    def update_fx(self, dt, player):
        trail = self.trail
        if not trail:
            return
        write = 0
        for entry in trail:
            entry[3] += dt
            if entry[3] < self.TRAIL_LIFE:
                trail[write] = entry
                write += 1
        del trail[write:]

    def draw_behind(self, surface, camera_x, player):
        if not self.trail:
            return
        cam = round(camera_x)
        sprites = player.sprites
        for x, y, key, age in self.trail:
            ghost = sprites.ghost(key, self.GHOST_COLOR)
            ghost.set_alpha(int(150 * (1.0 - age / self.TRAIL_LIFE)))
            surface.blit(ghost, (round(x) - cam, round(y)))


class SwordCombo(Ability):
    """Three-hit sword combo (attack1 -> attack2 -> attack3).

    Everything about the swings lives in the animation sheet JSON (assets/characters/vampire.json):
    frame count / fps decide the timing, and per attack: ``hit_frames`` (frames where the blade is
    dangerous), ``hitbox`` ([x_forward, y_up, w, h] relative to the player's feet centre),
    ``lunge`` ([frame, speed]) and ``cost`` (stamina). Press the key again while a swing is in
    its hit frames (or later) to chain into the next swing.

    While a strike is active ``player.attack_hitbox`` holds the world-space rectangle; enemies
    should test against it.
    """

    name = "Sword"
    keys = (pygame.K_j, pygame.K_x)
    costs = {"stamina": 8}
    cooldown = 0.0
    cancel_on_dash = True
    color = (176, 164, 170)
    icon = "sword"
    MAX_STAGE = 3

    def __init__(self):
        super().__init__()
        self.stage = 0
        self.elapsed = 0.0
        self.queued = False
        self.stage_time = 0.0
        self._info = None
        self._hit = (2, 3)
        self._queue_from = 0.0

    def can_use(self, player, level):
        return (not player.dead and player.hurt_timer <= 0.0 and self.cooldown_left <= 0.0
                and (self.active or player.stats.can_afford(self.costs)))

    def try_use(self, player, level):
        if self.active:                                   # buffer the next swing of the combo
            if self.stage < self.MAX_STAGE and self.elapsed >= self._queue_from:
                self.queued = True
            return False
        if not self.can_use(player, level):
            return False
        return self._start_stage(player, 1)

    def _start_stage(self, player, stage):
        name = f"attack{stage}"
        info = player.sprites.info(name)
        if not player.stats.stamina.spend(info.get("cost", 8)):
            return False
        self.stage, self.active, self.queued, self.elapsed = stage, True, False, 0.0
        self._info = info
        self.stage_time = info["frames"] / info["fps"]
        self.time_left = 1e9                              # ends through on_update, not the base timer
        self._hit = tuple(info.get("hit_frames", (2, 3)))
        self._queue_from = self._hit[0] / info["fps"]
        player.pose = name
        player.anim.play(name, restart=True)
        player.events.append(("attack", stage))
        return True

    def on_update(self, dt, player, level):
        self.elapsed += dt
        info = self._info
        frame = min(info["frames"] - 1, int(self.elapsed * info["fps"]))
        lunge_frame, lunge_speed = info.get("lunge", (-1, 0))
        if player.on_ground:                              # planted, except for the lunge of the strike
            player.vx_override = player.facing * lunge_speed if lunge_frame <= frame < lunge_frame + 2 else 0.0
        else:
            player.vx_override = None
        if self._hit[0] <= frame <= self._hit[-1]:
            x, y, w, h = info["hitbox"]
            cx = player.rect.centerx
            left = cx + x if player.facing > 0 else cx - x - w
            player.attack_hitbox = pygame.Rect(left, player.rect.bottom + y, w, h)
        else:
            player.attack_hitbox = None
        if self.elapsed >= self.stage_time:
            if self.queued and self.stage < self.MAX_STAGE and self._start_stage(player, self.stage + 1):
                return
            self.stop(player, level)

    def on_end(self, player, level, interrupted):
        player.pose = None
        player.vx_override = None
        player.attack_hitbox = None
        self.cooldown_left = 0.0 if interrupted else (0.25 if self.stage >= self.MAX_STAGE else 0.08)
        self.stage = 0
        self.queued = False
