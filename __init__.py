"""Level registry.

Every module in this package is a level (``levels/level_02.py`` -> "level_02").
Transition boxes refer to levels by that module name:

    (TRANSITION, 3130, 450, 60, 100, {"target": "level_02", "spawn": (80, 490)}),

``spawn`` is optional (player's top-left in the target level); without it the
player appears at the target level's PLAYER_START.
"""

import importlib


class LevelError(Exception):
    """Raised when a level can't be loaded (typo in a transition target, etc.)."""


def load_definition(name):
    if not name or not isinstance(name, str):
        raise LevelError("Transition box has no target level")
    qualified = f"{__name__}.{name}"
    try:
        return importlib.import_module(qualified)
    except ModuleNotFoundError as exc:
        if exc.name == qualified:
            raise LevelError(f"Level '{name}' not found") from exc
        raise
