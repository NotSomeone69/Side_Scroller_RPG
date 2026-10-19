"""Application loop, level switching, death/respawn flow and rendering."""
import pygame
from settings import SCREEN_WIDTH, SCREEN_HEIGHT, FPS, TITLE, MAX_FRAME_TIME, START_LEVEL
from camera import Camera
from level import Level
from levels import LevelError
from player import Player
from effects import Particles, ScreenFade
from background import get_background
from hud import HUD


class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption(TITLE)
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 22)
        self.small_font = pygame.font.Font(None, 18)
        self.canvas = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT)).convert()   # only used while shaking

        self.fx = Particles()
        self.level = Level(START_LEVEL)
        self.player = Player(*self.level.player_start, fx=self.fx)
        self.camera = Camera(SCREEN_WIDTH)
        self.camera.snap(self.player.rect, self.level.width)
        self.background = get_background(self.level.background_name)
        self.hud = HUD((SCREEN_WIDTH, SCREEN_HEIGHT), self.font, self.small_font)
        self.fade = ScreenFade((SCREEN_WIDTH, SCREEN_HEIGHT))

        self.time = 0.0
        self.show_help = True
        self.show_hitboxes = False
        self.portal_armed = True        # a portal only fires after the player has left all portals
        self.running = True
        self._caption_timer = 0.0

    # ------------------------------------------------------------------ loop
    def run(self):
        while self.running:
            dt = min(self.clock.tick(FPS) / 1000.0, MAX_FRAME_TIME)
            pressed = self._poll_events()
            self.update(dt, pressed)
            self.draw()
        pygame.quit()

    def _poll_events(self):
        pressed = set()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_F1:
                    self.show_help = not self.show_help
                elif event.key == pygame.K_F2:
                    self.show_hitboxes = not self.show_hitboxes
                else:
                    pressed.add(event.key)       # jump + ability triggers are resolved by the player
        return pressed

    # ---------------------------------------------------------------- update
    def update(self, dt, pressed):
        self.time += dt
        self.level.time += dt
        self.fade.update(dt)
        self.hud.update(dt)
        if not self.fade.blocking:
            keys = pygame.key.get_pressed()
            self.player.update(dt, keys, pressed, self.level)
            self._handle_player_events()
            if self.player.dead:
                # Let the death burst play, then fade out and respawn at the level start.
                self.fade.start(self._respawn, delay=max(0.5, self.player.death_time_left))
            else:
                self._check_portals()
        self.fx.update(dt)
        self.camera.update(self.player.rect, self.level.width, dt)

        self._caption_timer -= dt
        if self._caption_timer <= 0.0:
            self._caption_timer = 0.5
            pygame.display.set_caption(f"{TITLE}  -  {self.clock.get_fps():.0f} FPS")

    def _handle_player_events(self):
        for event, *data in self.player.pop_events():
            if event == "damage":
                self.camera.shake(6.0, 0.28)
                self.hud.flash_screen(0.3)
            elif event == "death":
                self.camera.shake(9.0, 0.4)
                self.hud.flash_screen(0.45)
            elif event == "dash":
                self.camera.shake(2.0, 0.12)
            elif event == "attack":
                self.camera.shake(1.5 + 0.8 * data[0], 0.1)

    def _check_portals(self):
        box = self.level.touching_transition(self.player.rect)
        if box is None:
            self.portal_armed = True
            return
        if not self.portal_armed or self.fade.active:
            return
        self.portal_armed = False
        try:
            destination = Level(box.target)                       # validates the target up front
        except LevelError as error:
            self.hud.toast(str(error))
            return
        spawn = box.spawn or destination.player_start
        self.fx.burst(box.rect.centerx, box.rect.centery, 26, ((120, 236, 255), (230, 130, 255), (255, 255, 255)),
                      speed=(60, 300), life=(0.3, 0.7), size=(2, 6), gravity=-60.0)
        self.fade.start(lambda: self._enter_level(destination, spawn))

    def _enter_level(self, level, spawn):
        self.level = level
        self.background = get_background(level.background_name)
        self.player.teleport(*spawn)
        self.camera.snap(self.player.rect, level.width)
        self.fx.items.clear()
        self.portal_armed = False                                  # don't bounce back through a portal at the spawn
        self.hud.toast(level.name)

    def _respawn(self):
        self.level = Level(self.level.id)                          # fresh level: crumble/movers reset
        self.background = get_background(self.level.background_name)
        self.player.respawn(*self.level.player_start)
        self.camera.snap(self.player.rect, self.level.width)
        self.fx.items.clear()
        self.portal_armed = False

    # ------------------------------------------------------------------ draw
    def draw(self):
        shaking = self.camera.shaking
        target = self.canvas if shaking else self.screen
        self.background.draw(target, self.camera.x, self.time)
        self.level.draw_back(target, self.camera)
        self.level.draw(target, self.camera, self.small_font)
        self.player.draw(target, self.camera.x)
        self.fx.draw(target, self.camera.x)
        self.level.draw_front(target, self.camera)
        if self.show_hitboxes:
            self._draw_debug(target)
        if shaking:
            self.screen.fill((0, 0, 0))
            self.screen.blit(target, self.camera.shake_offset())
        self.hud.draw(self.screen, self.player, self.level, self.show_help, self.clock.get_fps())
        self.fade.draw(self.screen)
        pygame.display.flip()

    def _draw_debug(self, target):
        cam = round(self.camera.x)
        pygame.draw.rect(target, (0, 200, 0), self.player.rect.move(-cam, 0), 1)
        if self.player.attack_hitbox is not None:
            pygame.draw.rect(target, (255, 40, 40), self.player.attack_hitbox.move(-cam, 0), 2)
        for hazard in self.level.hazards:
            pygame.draw.rect(target, (255, 120, 0), hazard.hitbox.move(-cam, 0), 1)
