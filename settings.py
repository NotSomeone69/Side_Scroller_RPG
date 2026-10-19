"""Shared settings and platform type names."""

SCREEN_WIDTH = 960
SCREEN_HEIGHT = 608               # 38 tiles of 16px
GRID = 16                         # the whole world is built on a 16px tile grid
FPS = 60
TITLE = "Side-Scroller RPG Prototype"
START_LEVEL = "level_01"          # module name inside the levels/ package

# --- Physics -----------------------------------------------------------------
GRAVITY = 1800.0
MAX_FALL_SPEED = 1100.0
MOVE_SPEED = 260.0                # run speed (also the speed used in the air)
WALK_SPEED = 150.0                # first moments of a ground move
RUN_DELAY = 0.28                  # seconds of holding a direction before walking turns into running
CROUCH_SPEED = 70.0
JUMP_SPEED = 650.0
MAX_FRAME_TIME = 1 / 30
MAX_STEP_SIZE = 3.0
MAX_STEP_UP = 14.0
MAX_STEP_DOWN = 18.0
SLIDE_ACCEL = 1300.0
MAX_SLIDE_SPEED = 520.0
DROP_THROUGH_TIME = 0.22
STEEP_ANGLE = 45.0                # ramps steeper than this are slippery and cannot be walked up
SLOPE_EPS = 0.05                  # tolerance (px) used by ramp collision tests

PLAYER_WIDTH = 32
PLAYER_HEIGHT = 48
PLAYER_START = (80.0, 496.0)
HURT_STUN = 0.28                  # seconds of lost control after being hit

# --- Player stats ------------------------------------------------------------
PLAYER_MAX_HEALTH = 100
PLAYER_MAX_MANA = 100
PLAYER_MAX_STAMINA = 100
MANA_REGEN = 6.0                  # per second
MANA_REGEN_DELAY = 1.0            # seconds after spending before regen resumes
STAMINA_REGEN = 30.0
STAMINA_REGEN_DELAY = 0.45

# --- Hazards -----------------------------------------------------------------
DAMAGE_PLATFORM_DAMAGE = 20       # can be overridden per platform with {"damage": N}
DAMAGE_INVINCIBILITY = 1.5        # seconds of (visible) invincibility after being hurt
RESPAWN_INVINCIBILITY = 1.0
HURT_HOP_SPEED = 340.0            # small bounce when a damage platform hurts you
VOID_MARGIN = 160                 # falling this far below the level kills the player

# --- Dash ability ------------------------------------------------------------
DASH_SPEED = 820.0
DASH_DURATION = 0.17              # ~140 px of travel
DASH_COOLDOWN = 0.55
DASH_COST = 30                    # stamina

# --- Platform types ----------------------------------------------------------
SOLID = "solid"
ONE_WAY = "one_way"
MOVING_VERTICAL = "moving_vertical"
MOVING_HORIZONTAL = "moving_horizontal"
CRUMBLE_RESET = "crumble_reset"
CRUMBLE_PERSISTENT = "crumble_persistent"
KILL = "kill_platform"            # touching it kills the player (respawn at level start)
DAMAGE = "damage_platform"        # touching it hurts the player
TRANSITION = "transition_box"     # touching it loads another level

SLOPE_ONE_WAY = "slope_one_way"   # brown/red ramps: Space+S drops through
SLOPE_SOLID = "slope_solid"       # solid ramps with a solid underside

MOVING_TYPES = (MOVING_VERTICAL, MOVING_HORIZONTAL)
CRUMBLE_TYPES = (CRUMBLE_RESET, CRUMBLE_PERSISTENT)
HAZARD_TYPES = (KILL, DAMAGE)
SOLID_TYPES = (SOLID, KILL, DAMAGE)          # block the player like walls/floors
TOP_ONLY_TYPES = (ONE_WAY, MOVING_VERTICAL, MOVING_HORIZONTAL, *CRUMBLE_TYPES)
SLOPE_TYPES = (SLOPE_ONE_WAY, SLOPE_SOLID)

# Default texture ("skin" in assets/skins/) for every type. A platform can override it with
# {"skin": "name"} in its options, so two platforms of one type can look different.
DEFAULT_SKINS = {
    SOLID: "stone_dark", ONE_WAY: "iron_beam", MOVING_VERTICAL: "rune_iron", MOVING_HORIZONTAL: "rune_iron",
    CRUMBLE_RESET: "crumble_stone", CRUMBLE_PERSISTENT: "crumble_ash", KILL: "blood_pool", DAMAGE: "spikes",
    TRANSITION: "portal_arch", SLOPE_SOLID: "stone_dark", SLOPE_ONE_WAY: "stone_blood",
}
DEFAULT_BACKGROUND = "blood_moon"

# --- Palette (style layer) -------------------------------------------------------
BLACK = (0, 0, 0)
NEAR_BLACK = (10, 5, 5)
DRIED_BLOOD = (74, 0, 0)
CRIMSON = (128, 0, 0)
BLOOD_RED = (192, 0, 0)           # tiny, selective highlights only
BONE = (176, 164, 150)
ASH = (110, 98, 104)
