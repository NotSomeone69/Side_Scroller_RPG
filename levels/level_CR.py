
"""Level created with level_editor.py. Coordinates are world coordinates."""
from settings import (
    SOLID, ONE_WAY, MOVING_VERTICAL, MOVING_HORIZONTAL,
    CRUMBLE_RESET, CRUMBLE_PERSISTENT,
    SLOPE_ONE_WAY, SLOPE_SOLID, KILL, DAMAGE, TRANSITION
)

NAME = 'Level 2 - The Sunken Citadel'
LEVEL_WIDTH = 3600
LEVEL_HEIGHT = 900
PLAYER_START = (80, 490)

PLATFORMS = [
    # --------------------------------------------------
    # SECTION 1: THE BROKEN COURTYARD
    # Safe introduction, gentle elevation, optional route.
    # --------------------------------------------------
    (SOLID, 0, 550, 620, 50, {}),
    (SOLID, 180, 445, 125, 20, {}),
    (SOLID, 390, 370, 130, 20, {}),
    (ONE_WAY, 65, 405, 95, 15, {}),
    (ONE_WAY, 300, 325, 100, 15, {}),
    (SOLID, 520, 455, 100, 20, {}),

    # First moving-platform crossing
    (MOVING_HORIZONTAL, 640, 455, 100, 16,
     {'min_x': 635, 'max_x': 790, 'speed': 75, 'direction': 1}),
    (MOVING_VERTICAL, 760, 370, 95, 16,
     {'min_y': 330, 'max_y': 445, 'speed': 55, 'direction': -1}),

    # --------------------------------------------------
    # SECTION 2: THE FLOODED ARCHES
    # Wider gaps, alternating heights, route choices.
    # --------------------------------------------------
    (SOLID, 850, 550, 400, 50, {}),
    (SOLID, 950, 445, 120, 20, {}),
    (SOLID, 1120, 355, 115, 20, {}),
    (ONE_WAY, 875, 380, 100, 15, {}),
    (ONE_WAY, 1030, 300, 105, 15, {}),
    (CRUMBLE_RESET, 1190, 405, 85, 15,
     {'break_after': 2.0, 'respawn_after': 1.5}),

    # Midair stepping stones
    (MOVING_VERTICAL, 1280, 405, 100, 16,
     {'min_y': 330, 'max_y': 460, 'speed': 70, 'direction': 1}),
    (MOVING_HORIZONTAL, 1400, 445, 105, 16,
     {'min_x': 1370, 'max_x': 1535, 'speed': 90, 'direction': -1}),

    # Second island
    (SOLID, 1550, 510, 350, 40, {}),
    (SOLID, 1610, 405, 120, 20, {}),
    (SOLID, 1780, 330, 110, 20, {}),
    (ONE_WAY, 1510, 365, 95, 15, {}),
    (ONE_WAY, 1690, 285, 90, 15, {}),
    (CRUMBLE_PERSISTENT, 1830, 400, 75, 15,
     {'break_after': 1.8, 'respawn_after': 1.5}),

    # --------------------------------------------------
    # SECTION 3: THE COLLAPSING SANCTUM
    # A faster sequence with no permanent resting point
    # across the central gap.
    # --------------------------------------------------
    (MOVING_VERTICAL, 1915, 390, 95, 16,
     {'min_y': 310, 'max_y': 450, 'speed': 80, 'direction': -1}),
    (CRUMBLE_RESET, 2040, 355, 90, 15,
     {'break_after': 1.8, 'respawn_after': 1.2}),
    (MOVING_HORIZONTAL, 2150, 410, 100, 16,
     {'min_x': 2120, 'max_x': 2330, 'speed': 105, 'direction': 1}),
    (CRUMBLE_PERSISTENT, 2290, 330, 90, 15,
     {'break_after': 1.6, 'respawn_after': 1.5}),

    # Sanctuary checkpoint-like resting island
    (SOLID, 2390, 500, 350, 50, {}),
    (SOLID, 2440, 395, 120, 20, {}),
    (ONE_WAY, 2600, 345, 100, 15, {}),
    (SOLID, 2670, 420, 70, 20, {}),

    # --------------------------------------------------
    # SECTION 4: THE SPIKEWORKS
    # Ground hazards force short, deliberate jumps.
    # --------------------------------------------------
    (SOLID, 2790, 550, 310, 50, {}),
    (SOLID, 2840, 445, 110, 20, {}),
    (SOLID, 3000, 365, 100, 20, {}),
    (ONE_WAY, 2760, 365, 95, 15, {}),
    (MOVING_HORIZONTAL, 2870, 475, 90, 16,
     {'min_x': 2830, 'max_x': 2990, 'speed': 95, 'direction': 1}),
    (CRUMBLE_RESET, 3040, 430, 85, 15,
     {'break_after': 2.0, 'respawn_after': 1.3}),

    # Final traversal
    (MOVING_VERTICAL, 3130, 405, 100, 16,
     {'min_y': 330, 'max_y': 455, 'speed': 75, 'direction': 1}),
    (ONE_WAY, 3240, 340, 100, 15, {}),
    (SOLID, 3300, 455, 300, 45, {}),
    (SOLID, 3360, 365, 100, 20, {}),
    (ONE_WAY, 3420, 300, 95, 15, {}),

    # Environmental hazards
    (DAMAGE, 545, 526, 65, 24, {}),
    (DAMAGE, 1050, 526, 90, 24, {}),
    (DAMAGE, 1640, 486, 70, 24, {}),
    (DAMAGE, 1730, 486, 65, 24, {}),
    (DAMAGE, 2450, 476, 75, 24, {}),
    (DAMAGE, 2580, 476, 60, 24, {}),
    (DAMAGE, 2810, 526, 65, 24, {}),
    (DAMAGE, 2950, 526, 55, 24, {}),
    (DAMAGE, 3060, 526, 35, 24, {}),

    # Kill zones below major gaps
    (KILL, 620, 640, 230, 40, {}),
    (KILL, 1250, 640, 300, 40, {}),
    (KILL, 1900, 640, 490, 40, {}),
    (KILL, 2740, 640, 50, 40, {}),
    (KILL, 3100, 640, 200, 40, {}),

    # Exit to the next stage
    (TRANSITION, 3510, 365, 55, 90,
     {'target': 'level_03', 'spawn': (80, 490)}),
]

SLOPES = [
    # Courtyard ramps
    (SLOPE_ONE_WAY, 80, 450, 180, 100, 'up_right'),
    (SLOPE_SOLID, 305, 400, 100, 80, 'up_right'),
    (SLOPE_ONE_WAY, 430, 470, 100, 80, 'up_right'),

    # Flooded arches
    (SLOPE_SOLID, 870, 450, 130, 100, 'up_right'),
    (SLOPE_ONE_WAY, 1080, 420, 120, 65, 'up_right'),
    (SLOPE_SOLID, 1560, 420, 140, 90, 'up_right'),
    (SLOPE_ONE_WAY, 1730, 370, 100, 70, 'up_right'),

    # Sanctum descent and ascent
    (SLOPE_SOLID, 1940, 455, 130, 80, 'up_right'),
    (SLOPE_ONE_WAY, 2200, 400, 110, 70, 'up_left'),
    (SLOPE_SOLID, 2400, 420, 140, 80, 'up_right'),

    # Final approach
    (SLOPE_SOLID, 2760, 450, 120, 100, 'up_right'),
    (SLOPE_ONE_WAY, 2900, 405, 100, 80, 'up_right'),
    (SLOPE_SOLID, 3130, 455, 120, 75, 'up_right'),
    (SLOPE_ONE_WAY, 3320, 400, 100, 65, 'up_right'),
]
