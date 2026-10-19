"""Lightweight visual effects: square "pixel" particles and the screen fade."""

import math
import random

# Particle list layout (plain lists are faster than objects for hundreds of items):
#   0 x, 1 y, 2 vx, 3 vy, 4 life left, 5 life total, 6 size, 7 color, 8 gravity, 9 drag
_X, _Y, _VX, _VY, _LIFE, _TOTAL, _SIZE, _COLOR, _GRAV, _DRAG = range(10)


class Particles:
    MAX = 450

    def __init__(self):
        self.items = []
        self._rand = random.Random()

    def emit(self, x, y, vx, vy, life, size, color, gravity=0.0, drag=0.0):
        if len(self.items) < self.MAX:
            self.items.append([x, y, vx, vy, life, life, size, color, gravity, drag])

    def burst(self, x, y, count, colors, speed=(40, 220), angle=(0.0, math.tau),
              life=(0.25, 0.6), size=(2, 6), gravity=500.0, drag=2.0):
        """Spray ``count`` pixels from (x, y). ``colors`` is one color or a tuple of colors."""
        rnd = self._rand
        if isinstance(colors[0], int):
            colors = (colors,)
        for _ in range(count):
            a = rnd.uniform(*angle)
            s = rnd.uniform(*speed)
            self.emit(x, y, math.cos(a) * s, math.sin(a) * s, rnd.uniform(*life),
                      rnd.choice((size[0], size[1])) if size[0] != size[1] else size[0],
                      rnd.choice(colors), gravity, drag)

    def dust(self, x, y, direction=0, count=5, color=(190, 180, 170)):
        """Small puff at the player's feet. ``direction`` biases the puff backwards."""
        rnd = self._rand
        for _ in range(count):
            self.emit(x + rnd.uniform(-8, 8), y + rnd.uniform(-2, 0),
                      -direction * rnd.uniform(20, 90) + rnd.uniform(-30, 30), rnd.uniform(-70, -15),
                      rnd.uniform(0.2, 0.42), rnd.choice((2, 4)), color, 120.0, 3.0)

    def update(self, dt):
        items = self.items
        if not items:
            return
        write = 0
        for p in items:
            p[_LIFE] -= dt
            if p[_LIFE] <= 0.0:
                continue
            p[_VY] += p[_GRAV] * dt
            if p[_DRAG]:
                p[_VX] *= max(0.0, 1.0 - p[_DRAG] * dt)
            p[_X] += p[_VX] * dt
            p[_Y] += p[_VY] * dt
            items[write] = p
            write += 1
        del items[write:]

    def draw(self, surface, camera_x):
        if not self.items:
            return
        cam = round(camera_x)
        width = surface.get_width()
        fill = surface.fill
        for p in self.items:
            x = int(p[_X]) - cam
            if x < -8 or x > width:
                continue
            size = p[_SIZE]
            # Particles shrink in 2px steps over their life to keep the pixel look.
            size = max(2, int(size * (p[_LIFE] / p[_TOTAL]) + 0.5) // 2 * 2) if size > 2 else 2
            fill(p[_COLOR], (x, int(p[_Y]), size, size))


class ScreenFade:
    """Pixel-iris transition. ``start(callback)`` closes the screen, runs the
    callback while it is fully black (swap level, respawn...) and reopens it."""

    CELL = 40
    COLOR = (10, 8, 16)

    def __init__(self, screen_size, duration=0.38):
        width, height = screen_size
        self.cols = math.ceil(width / self.CELL)
        self.rows = math.ceil(height / self.CELL)
        self.duration = duration
        rnd = random.Random(11)
        raw = [c / max(1, self.cols - 1) * 0.45 + r / max(1, self.rows - 1) * 0.25 + rnd.random() * 0.2
               for r in range(self.rows) for c in range(self.cols)]
        top = max(raw)
        self.thresholds = [v / top * 0.7 for v in raw]
        self.state = None          # None | "wait" | "out" | "in"
        self.t = 0.0
        self.delay = 0.0
        self.callback = None

    @property
    def active(self):
        return self.state is not None

    @property
    def blocking(self):
        """True while the screen is closing (gameplay should be frozen)."""
        return self.state == "out"

    def start(self, callback=None, delay=0.0):
        if self.state is not None:
            return False
        self.callback = callback
        self.t = 0.0
        self.delay = delay
        self.state = "wait" if delay > 0 else "out"
        return True

    def update(self, dt):
        if self.state is None:
            return
        if self.state == "wait":
            self.delay -= dt
            if self.delay <= 0.0:
                self.state, self.t = "out", 0.0
            return
        self.t += dt
        if self.t < self.duration:
            return
        if self.state == "out":
            if self.callback:
                self.callback()
                self.callback = None
            self.state, self.t = "in", 0.0
        else:
            self.state = None

    @property
    def coverage(self):
        if self.state == "out":
            return min(1.0, self.t / self.duration)
        if self.state == "in":
            return max(0.0, 1.0 - self.t / self.duration)
        return 0.0

    def draw(self, surface):
        p = self.coverage
        if p <= 0.0:
            return
        if p >= 1.0:
            surface.fill(self.COLOR)
            return
        cell = self.CELL
        fill = surface.fill
        color = self.COLOR
        i = 0
        for r in range(self.rows):
            for c in range(self.cols):
                s = (p - self.thresholds[i]) / 0.3
                i += 1
                if s <= 0.0:
                    continue
                size = cell if s >= 1.0 else max(4, round(cell * s / 4) * 4)
                off = (cell - size) // 2
                fill(color, (c * cell + off, r * cell + off, size, size))
