
"""Level created with level_editor.py. Coordinates are world coordinates."""
from settings import (
    SOLID, ONE_WAY, MOVING_VERTICAL, MOVING_HORIZONTAL,
    CRUMBLE_RESET, CRUMBLE_PERSISTENT,
    SLOPE_ONE_WAY, SLOPE_SOLID, KILL, DAMAGE, TRANSITION
)

NAME = 'Level 3 - The Cathedral of the Damned'
LEVEL_WIDTH = 3600
LEVEL_HEIGHT = 1200
PLAYER_START = (80, 490)

PLATFORMS = [
    # ==================================================
    # 1. THE RUINED ENTRANCE
    # Wide stone floors, broken pews, introductory jumps.
    # ==================================================
    (SOLID, 0, 550, 430, 50, {}),
    (SOLID, 100, 450, 110, 20, {}),
    (SOLID, 270, 380, 100, 20, {}),
    (ONE_WAY, 40, 400, 85, 15, {}),
    (ONE_WAY, 215, 320, 90, 15, {}),

    # Broken columns
    (SOLID, 390, 465, 65, 85, {}),
    (SOLID, 480, 405, 85, 20, {}),
    (CRUMBLE_RESET, 590, 360, 85, 15,
     {'break_after': 2.0, 'respawn_after': 1.5}),

    # First ascent lift
    (MOVING_VERTICAL, 690, 390, 95, 16,
     {'min_y': 300, 'max_y': 465, 'speed': 65, 'direction': -1}),

    # ==================================================
    # 2. THE NAVE
    # Tall arches, broken balconies and chandeliers.
    # ==================================================
    (SOLID, 820, 510, 250, 40, {}),
    (SOLID, 850, 405, 105, 20, {}),
    (ONE_WAY, 960, 330, 100, 15, {}),
    (SOLID, 1080, 425, 100, 20, {}),
    (CRUMBLE_PERSISTENT, 1195, 365, 80, 15,
     {'break_after': 1.7, 'respawn_after': 1.5}),

    # Moving chandelier platforms
    (MOVING_HORIZONTAL, 1285, 310, 100, 16,
     {'min_x': 1260, 'max_x': 1450, 'speed': 85, 'direction': 1}),
    (MOVING_VERTICAL, 1450, 350, 95, 16,
     {'min_y': 265, 'max_y': 430, 'speed': 70, 'direction': 1}),

    # West balcony
    (SOLID, 1580, 460, 230, 35, {}),
    (SOLID, 1610, 370, 100, 20, {}),
    (ONE_WAY, 1740, 300, 95, 15, {}),
    (CRUMBLE_RESET, 1835, 340, 80, 15,
     {'break_after': 1.8, 'respawn_after': 1.2}),

    # ==================================================
    # 3. THE GARGOYLE GALLERY
    # Harder traversal over a deep abyss.
    # ==================================================
    (MOVING_VERTICAL, 1930, 360, 95, 16,
     {'min_y': 255, 'max_y': 430, 'speed': 85, 'direction': -1}),
    (CRUMBLE_PERSISTENT, 2050, 300, 85, 15,
     {'break_after': 1.5, 'respawn_after': 1.5}),
    (MOVING_HORIZONTAL, 2155, 365, 100, 16,
     {'min_x': 2120, 'max_x': 2320, 'speed': 105, 'direction': 1}),
    (ONE_WAY, 2290, 285, 90, 15, {}),
    (CRUMBLE_RESET, 2390, 325, 85, 15,
     {'break_after': 1.5, 'respawn_after': 1.2}),

    # Safe balcony after the gallery
    (SOLID, 2500, 455, 260, 40, {}),
    (SOLID, 2530, 355, 110, 20, {}),
    (ONE_WAY, 2660, 290, 90, 15, {}),

    # ==================================================
    # 4. THE BELL TOWER
    # Long vertical climb using alternating lifts.
    # ==================================================
    (SOLID, 2760, 510, 180, 40, {}),
    (SOLID, 2790, 420, 90, 20, {}),
    (MOVING_VERTICAL, 2900, 365, 95, 16,
     {'min_y': 230, 'max_y': 405, 'speed': 75, 'direction': -1}),
    (ONE_WAY, 3010, 300, 90, 15, {}),
    (MOVING_HORIZONTAL, 3110, 255, 100, 16,
     {'min_x': 3080, 'max_x': 3260, 'speed': 95, 'direction': 1}),
    (CRUMBLE_RESET, 3270, 300, 85, 15,
     {'break_after': 1.6, 'respawn_after': 1.2}),

    # Final tower balcony
    (SOLID, 3380, 390, 220, 40, {}),
    (SOLID, 3410, 305, 100, 20, {}),
    (ONE_WAY, 3500, 240, 90, 15, {}),

    # ==================================================
    # 5. CATHEDRAL HAZARDS
    # Floor spikes, cursed stone and broken walkways.
    # ==================================================
    (DAMAGE, 400, 526, 55, 24, {}),
    (DAMAGE, 850, 486, 65, 24, {}),
    (DAMAGE, 1000, 486, 55, 24, {}),
    (DAMAGE, 1600, 436, 55, 24, {}),
    (DAMAGE, 1770, 436, 40, 24, {}),
    (DAMAGE, 2520, 431, 60, 24, {}),
    (DAMAGE, 2610, 431, 45, 24, {}),
    (DAMAGE, 2780, 486, 45, 24, {}),
    (DAMAGE, 3390, 366, 40, 24, {}),

    # Abyss beneath the major traversal gaps
    (KILL, 430, 700, 390, 40, {}),
    (KILL, 1070, 700, 510, 40, {}),
    (KILL, 1810, 700, 690, 40, {}),
    (KILL, 2760, 700, 620, 40, {}),

    # ==================================================
    # EXIT: THE SANCTUM
    # ==================================================
    (TRANSITION, 3540, 295, 50, 90,
     {'target': 'level_04', 'spawn': (80, 490)}),
]

SLOPES = [
    # Entrance rubble
    (SLOPE_SOLID, 30, 465, 120, 85, 'up_right'),
    (SLOPE_ONE_WAY, 205, 425, 100, 70, 'up_right'),
    (SLOPE_SOLID, 340, 480, 90, 70, 'up_right'),

    # Nave: collapsed masonry
    (SLOPE_SOLID, 820, 440, 100, 70, 'up_right'),
    (SLOPE_ONE_WAY, 1040, 455, 100, 65, 'up_right'),
    (SLOPE_SOLID, 1560, 410, 120, 80, 'up_right'),

    # Gargoyle gallery
    (SLOPE_ONE_WAY, 1850, 390, 100, 65, 'up_right'),
    (SLOPE_SOLID, 2070, 390, 110, 75, 'up_right'),
    (SLOPE_ONE_WAY, 2320, 375, 100, 65, 'up_left'),
    (SLOPE_SOLID, 2500, 410, 110, 70, 'up_right'),

    # Bell tower approach
    (SLOPE_SOLID, 2760, 445, 100, 65, 'up_right'),
    (SLOPE_ONE_WAY, 2960, 365, 100, 65, 'up_right'),
    (SLOPE_SOLID, 3260, 345, 110, 65, 'up_right'),
    (SLOPE_ONE_WAY, 3380, 420, 100, 60, 'up_right'),
]
