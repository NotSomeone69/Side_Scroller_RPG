"""Level 3: dash challenge. The gaps are too wide to jump, so you have to dash in mid-air."""
from settings import SOLID, KILL, DAMAGE, TRANSITION

NAME = "Level 3 - Dash Gauntlet"
LEVEL_WIDTH = 2100
LEVEL_HEIGHT = 900
PLAYER_START = (80, 490)

PLATFORMS = [
    (SOLID, 0, 550, 400, 50, {}),
    (KILL, 400, 570, 1500, 30, {}),                         # lava under all the gaps
    (SOLID, 620, 550, 160, 50, {}),
    (DAMAGE, 700, 526, 60, 24, {}),
    (SOLID, 1000, 530, 160, 70, {}),
    (SOLID, 1380, 550, 160, 50, {}),
    (SOLID, 1760, 550, 340, 50, {}),
    (TRANSITION, 2000, 450, 50, 100, {'target': 'level_01'}),   # no spawn -> level_01's PLAYER_START
]

SLOPES = []
