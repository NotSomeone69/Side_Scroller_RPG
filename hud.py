"""Gothic HUD: iron-framed stat bars, ability slots, hints, toast messages and screen flashes."""

import pygame

import assets

BAR_W = 190
ICON_FOR = {"health": "heart", "mana": "drop", "stamina": "bolt"}
IRON0, IRON1, IRON2, IRON3 = (10, 8, 12), (28, 24, 32), (50, 44, 56), (84, 76, 92)
BONE = (196, 184, 176)
BAR_STYLES = {                       # fill, light edge, dark edge, "recent loss" trail
    "health": ((128, 0, 0), (192, 0, 0), (74, 0, 0), (214, 170, 160)),
    "mana": ((62, 46, 120), (110, 92, 176), (34, 24, 72), (170, 160, 210)),
    "stamina": ((140, 124, 98), (190, 174, 144), (84, 72, 56), (214, 204, 186)),
}
HELP_LINES = (
    "Move  Q/D or arrows        Jump  Space",
    "Crouch  S                  Dash  Shift / K",
    "Sword combo  J / X  (tap again mid-swing)",
    "Drop through  Space + S",
    "F1 help   F2 hitboxes   Esc quit",
)


class HUD:
    def __init__(self, screen_size, font, small_font):
        self.size = screen_size
        self.font = font
        self.small = small_font
        self.toast_text = ""
        self.toast_time = 0.0
        self.flash_time = 0.0
        self.flash_total = 0.01
        self.clock = 0.0
        self._text_cache = {}
        self._key_labels = {}
        w, h = screen_size
        self._flash = pygame.Surface(screen_size)
        self._flash.fill((128, 0, 0))
        self._vignette = self._make_vignette(w, h)
        self._panel = self._make_panel(256, 88)
        self._slot_shade = pygame.Surface((36, 36), pygame.SRCALPHA)
        self._slot_shade.fill((4, 2, 4, 200))

    # ------------------------------------------------------------------ setup
    @staticmethod
    def _make_vignette(w, h):
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        for i in range(10):
            pygame.draw.rect(surf, (128, 0, 0, 120 - i * 12), (i * 6, i * 6, w - i * 12, h - i * 12), 6)
        return surf

    @staticmethod
    def _make_panel(w, h):
        """Dark panel with an iron frame, crimson inner line and studded corners."""
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        surf.fill((6, 3, 4, 200))
        pygame.draw.rect(surf, IRON0, (0, 0, w, h), 2)
        pygame.draw.rect(surf, IRON2, (2, 2, w - 4, h - 4), 1)
        pygame.draw.rect(surf, (74, 0, 0), (4, 4, w - 8, h - 8), 1)
        for x, y in ((0, 0), (w - 6, 0), (0, h - 6), (w - 6, h - 6)):
            surf.fill(IRON3, (x, y, 6, 6))
            surf.fill(IRON0, (x + 2, y + 2, 2, 2))
        return surf

    # ------------------------------------------------------------------- state
    def toast(self, text, seconds=2.6):
        self.toast_text, self.toast_time = text, seconds

    def flash_screen(self, seconds=0.3):
        self.flash_time = self.flash_total = seconds

    def update(self, dt):
        self.clock += dt
        if self.toast_time > 0.0:
            self.toast_time -= dt
        if self.flash_time > 0.0:
            self.flash_time -= dt

    # ----------------------------------------------------------------- helpers
    def text(self, surface, string, pos, color=BONE, font=None, shadow=True, align="left"):
        font = font or self.small
        key = (string, color, id(font))
        surf = self._text_cache.get(key)
        if surf is None:
            if len(self._text_cache) > 160:
                self._text_cache.clear()
            surf = self._text_cache[key] = font.render(string, True, color)
        x, y = pos
        if align == "right":
            x -= surf.get_width()
        elif align == "center":
            x -= surf.get_width() // 2
        if shadow:
            skey = (string, (0, 0, 0), id(font))
            sh = self._text_cache.get(skey)
            if sh is None:
                sh = self._text_cache[skey] = font.render(string, True, (0, 0, 0))
            surface.blit(sh, (x + 1, y + 1))
        surface.blit(surf, (x, y))

    def _bar(self, surface, x, y, h, resource, name):
        fill, light, dark, ghost = BAR_STYLES[name]
        w = BAR_W
        ic = assets.icon(ICON_FOR[name])
        surface.blit(ic, (x, y + h // 2 - ic.get_height() // 2))
        bx = x + 30
        surface.fill(IRON0, (bx - 3, y - 3, w + 6, h + 6))
        surface.fill(IRON2, (bx - 2, y - 2, w + 4, 1))
        surface.fill((12, 8, 10), (bx, y, w, h))
        gw = int(w * resource.ghost_fraction) // 2 * 2
        fw = int(w * resource.fraction) // 2 * 2
        if gw > fw:
            surface.fill(ghost, (bx + fw, y, gw - fw, h))
        if fw > 0:
            low = name == "health" and resource.fraction <= 0.3 and int(self.clock * 6) % 2
            surface.fill((192, 0, 0) if low else fill, (bx, y, fw, h))
            surface.fill(light, (bx, y, fw, 1))
            surface.fill(dark, (bx, y + h - 2, fw, 2))
        for i in range(1, 10):                                  # segment ticks
            surface.fill(IRON0, (bx + i * w // 10, y, 1, h))
        if h >= 14:
            self.text(surface, f"{int(resource.value + 0.99)}/{int(resource.maximum)}", (bx + w - 4, y + h // 2 - 5),
                      font=self.small, align="right")

    def _key_label(self, ability):
        label = self._key_labels.get(id(ability))
        if label is None:
            label = "?"
            if ability.keys:
                name = pygame.key.name(ability.keys[0]).upper()
                label = "SHIFT" if "SHIFT" in name else name[:5]
            self._key_labels[id(ability)] = label
        return label

    # -------------------------------------------------------------------- draw
    def draw(self, surface, player, level, show_help=True, fps=0.0):
        stats = player.stats
        w, h = self.size

        if stats.health.fraction <= 0.3 and not player.dead:     # low-health vignette
            self._vignette.set_alpha(int(110 + 100 * abs(((self.clock * 1.4) % 2) - 1)))
            surface.blit(self._vignette, (0, 0))
        if self.flash_time > 0.0:
            self._flash.set_alpha(int(120 * self.flash_time / self.flash_total))
            surface.blit(self._flash, (0, 0))

        surface.blit(self._panel, (10, 10))
        self._bar(surface, 22, 22, 16, stats.health, "health")
        self._bar(surface, 22, 46, 14, stats.mana, "mana")
        self._bar(surface, 22, 68, 10, stats.stamina, "stamina")

        x = 12
        for ability in player.abilities:                         # one slot per ability, drawn automatically
            self._slot(surface, x, 106, ability, player)
            x += 46

        self.text(surface, f"{level.name}", (w - 14, 12), font=self.font, align="right")
        self.text(surface, f"x {int(player.x)} / {level.width}", (w - 14, 30), color=(120, 108, 112), align="right")
        if fps:
            self.text(surface, f"{fps:.0f} fps", (w - 14, 46), color=(84, 74, 78), align="right")

        if show_help:
            for i, line in enumerate(HELP_LINES):
                self.text(surface, line, (w - 14, 70 + i * 15), color=(100, 90, 94), align="right")
        if self.toast_time > 0.0:
            self.text(surface, self.toast_text, (w // 2, 80), color=(192, 150, 140), font=self.font, align="center")

    def _slot(self, surface, x, y, ability, player):
        rect = pygame.Rect(x, y, 40, 40)
        ready = ability.cooldown_left <= 0.0 and not ability.active
        affordable = player.stats.can_afford(ability.costs)
        edge = IRON3 if (ready and affordable) else IRON2
        if ability.active:
            edge = (192, 0, 0)
        surface.fill(IRON0, rect)
        surface.fill((20, 12, 14), rect.inflate(-4, -4))
        if ability.icon is not None:
            ic = assets.icon(ability.icon)
            surface.blit(ic, (rect.centerx - ic.get_width() // 2, rect.centery - ic.get_height() // 2 - 2))
        frac = ability.cooldown_fraction
        if frac > 0.0:                                          # cooldown sweeps down the slot
            hh = max(2, int(36 * frac)) // 2 * 2
            surface.blit(self._slot_shade, (x + 2, y + 2), (0, 0, 36, hh))
        elif not affordable:
            surface.blit(self._slot_shade, (x + 2, y + 2))
        pygame.draw.rect(surface, edge, rect, 2)
        for cx, cy in ((rect.x, rect.y), (rect.right - 3, rect.y), (rect.x, rect.bottom - 3), (rect.right - 3, rect.bottom - 3)):
            surface.fill(IRON3, (cx, cy, 3, 3))
        self.text(surface, self._key_label(ability), (rect.centerx, rect.bottom - 11), font=self.small,
                  color=(170, 158, 160), align="center")
