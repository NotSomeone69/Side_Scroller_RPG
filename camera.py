"""A horizontal camera that follows the player through long levels, with screen shake."""

import math
import random


class Camera:
    def __init__(self, screen_width: int):
        self.x = 0.0
        self.screen_width = screen_width
        self._shake_time = 0.0
        self._shake_total = 0.0
        self._shake_strength = 0.0
        self._rand = random.Random()

    def _desired(self, target_rect, level_width):
        # Keep the player around the center, with a little room to see ahead.
        desired_x = target_rect.centerx - self.screen_width * 0.42
        return max(0.0, min(desired_x, max(0, level_width - self.screen_width)))

    def update(self, target_rect, level_width: int, dt: float = 0.0) -> None:
        desired = self._desired(target_rect, level_width)
        if dt <= 0.0:
            self.x = desired
        else:
            self.x += (desired - self.x) * min(1.0, dt * 14.0)     # light smoothing
            if abs(desired - self.x) < 0.25:
                self.x = desired
        if self._shake_time > 0.0:
            self._shake_time = max(0.0, self._shake_time - dt)

    def snap(self, target_rect, level_width: int) -> None:
        """Jump straight to the target (level change / respawn)."""
        self.x = self._desired(target_rect, level_width)
        self._shake_time = 0.0

    def shake(self, strength: float, duration: float = 0.25) -> None:
        if strength >= self._shake_strength * (self._shake_time / self._shake_total if self._shake_total else 0.0):
            self._shake_strength = strength
            self._shake_time = self._shake_total = duration

    @property
    def shaking(self) -> bool:
        return self._shake_time > 0.0

    def shake_offset(self):
        if self._shake_time <= 0.0:
            return 0, 0
        amount = self._shake_strength * (self._shake_time / self._shake_total)
        return (round(self._rand.uniform(-amount, amount)), round(self._rand.uniform(-amount, amount)))

    def apply(self, rect):
        return rect.move(-round(self.x), 0)

    def world_to_screen_x(self, world_x: float) -> int:
        return round(world_x - self.x)
