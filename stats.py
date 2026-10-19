"""Player stats: resource pools (health, mana, stamina), damage and invincibility.

Adding a new stat is one line:

    stats.add_resource("rage", Resource(100, regen=0))

Abilities can then charge it through their ``costs`` dict ({"rage": 25}).
"""

from settings import (
    PLAYER_MAX_HEALTH, PLAYER_MAX_MANA, PLAYER_MAX_STAMINA,
    MANA_REGEN, MANA_REGEN_DELAY, STAMINA_REGEN, STAMINA_REGEN_DELAY,
)


class Resource:
    """A bounded value (health, mana...) with optional delayed regeneration.

    ``ghost`` trails behind ``value`` when it drops so the HUD can show the
    classic "recent damage" bar.
    """

    __slots__ = ("maximum", "value", "regen", "regen_delay", "ghost", "_delay", "_ghost_hold")

    def __init__(self, maximum, regen=0.0, regen_delay=0.0, start=None):
        self.maximum = float(maximum)
        self.value = self.maximum if start is None else float(start)
        self.regen = float(regen)
        self.regen_delay = float(regen_delay)
        self.ghost = self.value
        self._delay = 0.0
        self._ghost_hold = 0.0

    @property
    def fraction(self):
        return self.value / self.maximum if self.maximum else 0.0

    @property
    def ghost_fraction(self):
        return self.ghost / self.maximum if self.maximum else 0.0

    @property
    def empty(self):
        return self.value <= 0.0

    def can_afford(self, amount):
        return self.value + 1e-6 >= amount

    def spend(self, amount):
        """Pay ``amount`` if possible. Returns True when it was paid."""
        if not self.can_afford(amount):
            return False
        self._drain(amount)
        return True

    def lose(self, amount):
        self._drain(amount)

    def gain(self, amount):
        self.value = min(self.maximum, self.value + amount)

    def fill(self):
        self.value = self.ghost = self.maximum
        self._delay = self._ghost_hold = 0.0

    def set_maximum(self, maximum, refill=False):
        self.maximum = float(maximum)
        self.value = self.maximum if refill else min(self.value, self.maximum)
        self.ghost = min(self.ghost, self.maximum)

    def _drain(self, amount):
        self.value = max(0.0, self.value - amount)
        self._delay = self.regen_delay
        self._ghost_hold = 0.45

    def update(self, dt):
        if self._delay > 0.0:
            self._delay -= dt
        elif self.regen and self.value < self.maximum:
            self.value = min(self.maximum, self.value + self.regen * dt)
        if self.ghost < self.value:
            self.ghost = self.value
        elif self.ghost > self.value:
            if self._ghost_hold > 0.0:
                self._ghost_hold -= dt
            else:
                self.ghost = max(self.value, self.ghost - self.maximum * 0.7 * dt)


class Stats:
    def __init__(self):
        self.resources = {}
        self.health = self.add_resource("health", Resource(PLAYER_MAX_HEALTH))
        self.mana = self.add_resource("mana", Resource(PLAYER_MAX_MANA, MANA_REGEN, MANA_REGEN_DELAY))
        self.stamina = self.add_resource("stamina", Resource(PLAYER_MAX_STAMINA, STAMINA_REGEN, STAMINA_REGEN_DELAY))
        self.invincible_timer = 0.0
        self.invincible_total = 0.0
        self.hit_flash = 0.0           # short white flash right after taking a hit

    # -- resources ---------------------------------------------------------
    def add_resource(self, name, resource):
        self.resources[name] = resource
        setattr(self, name, resource)
        return resource

    def can_afford(self, costs):
        resources = self.resources
        return all(resources[name].can_afford(amount) for name, amount in costs.items())

    def spend(self, costs):
        """Atomically pay every cost in ``costs``. Returns True on success."""
        if not self.can_afford(costs):
            return False
        for name, amount in costs.items():
            self.resources[name].spend(amount)
        return True

    # -- damage / invincibility -------------------------------------------
    @property
    def is_dead(self):
        return self.health.empty

    @property
    def invincible(self):
        return self.invincible_timer > 0.0

    def grant_invincibility(self, seconds):
        if seconds > self.invincible_timer:
            self.invincible_timer = self.invincible_total = seconds

    def take_damage(self, amount, invincibility=0.0):
        """Returns True if the hit landed (False while invincible or already dead)."""
        if self.invincible or self.is_dead:
            return False
        self.health.lose(amount)
        self.hit_flash = 0.16
        self.grant_invincibility(invincibility)
        return True

    def revive(self, invincibility=0.0):
        for resource in self.resources.values():
            resource.fill()
        self.invincible_timer = self.invincible_total = 0.0
        self.hit_flash = 0.0
        self.grant_invincibility(invincibility)

    def update(self, dt):
        if self.invincible_timer > 0.0:
            self.invincible_timer = max(0.0, self.invincible_timer - dt)
        if self.hit_flash > 0.0:
            self.hit_flash = max(0.0, self.hit_flash - dt)
        for resource in self.resources.values():
            resource.update(dt)
