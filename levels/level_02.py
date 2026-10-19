"""Level 2: spikes, a lava pit with stepping stones, a dash wall and a steep solid pyramid."""
from settings import SOLID, ONE_WAY, MOVING_HORIZONTAL, KILL, DAMAGE, TRANSITION, SLOPE_SOLID

NAME = "Level 2 - Ember Pit"
LEVEL_WIDTH = 2400
LEVEL_HEIGHT = 900
PLAYER_START = (80, 490)

PLATFORMS = [
    (SOLID, 0, 550, 700, 50, {}),
    (KILL, 700, 574, 300, 26, {}),                          # lava pit between 700 and 1000
    (SOLID, 740, 480, 80, 20, {}),                          # stepping stones
    (SOLID, 880, 470, 80, 20, {}),
    (SOLID, 1000, 550, 500, 50, {}),
    (DAMAGE, 1150, 526, 120, 24, {'damage': 20}),           # spikes (override damage per platform)
    (ONE_WAY, 1350, 470, 100, 15, {}),                      # stairs up to the side exit
    (ONE_WAY, 1250, 390, 100, 15, {}),
    (TRANSITION, 1280, 290, 40, 100, {'target': 'level_03', 'spawn': (80, 490)}),
    (SOLID, 1500, 550, 900, 50, {}),
    (SOLID, 1700, 450, 40, 100, {}),                        # a wall: dash into it, you stop
    (SOLID, 1970, 450, 90, 100, {}),                        # pyramid top
    (MOVING_HORIZONTAL, 2160, 400, 90, 16, {'min_x': 2150, 'max_x': 2260, 'speed': 60, 'direction': 1}),
    (TRANSITION, 2330, 450, 50, 100, {'target': 'level_01', 'spawn': (3000, 490)}),
]

SLOPES = [
    (SLOPE_SOLID, 1900, 450, 70, 100, 'up_right'),          # steep solid ramps (55 deg)
    (SLOPE_SOLID, 2060, 450, 70, 100, 'up_left'),
]
