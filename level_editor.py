"""
Level editor for the side-scroller (run:  python level_editor.py  from the project folder).

Mouse
  Objects layer : pick a type in the palette, then click-drag on the canvas to draw it.
                  Click an object to select it; drag it to move; drag the 8 handles (edges /
                  corners) to resize it on the grid; right-click deletes.
  Tile layers   : pick tiles in the tileset picker (drag to pick a block), click/drag to paint,
                  right-drag to erase, Shift+drag fills a rectangle, Alt+click picks a tile.
  Wheel         : zoom at the cursor        Middle-drag / Space+drag : pan
Keys
  Ctrl+S save   Ctrl+O open   Ctrl+N new level   Ctrl+Z / Ctrl+Y undo / redo   Ctrl+D duplicate
  Del delete    G grid snapping   F flip ramp   Arrow keys nudge the selection by one tile
  Esc cancels the current tool / closes dialogs
"""
import math
import os
import sys

import pygame

import assets
import leveldata as LD
import settings as S
from background import get_background
from leveldata import GRID, LevelData
from skins import SLOT_NAMES, STANDARD, get_skin, get_tileset, slot_for

# ----------------------------------------------------------------------------- look
BG = (6, 3, 5)
PANEL = (16, 10, 12)
PANEL2 = (26, 17, 20)
BORDER = (58, 40, 42)
TEXT = (206, 194, 190)
MUTED = (130, 112, 112)
ACCENT = (192, 0, 0)
ACCENT_DIM = (128, 0, 0)
GOOD = (150, 170, 130)
GRID_COL = (24, 14, 17)
GRID_COL2 = (40, 22, 26)

LEFT_W, RIGHT_W, TOP_H, BOTTOM_H = 262, 292, 50, 26

OBJECT_TYPES = [
    ("Solid block", S.SOLID), ("One-way platform", S.ONE_WAY), ("Moving vertical", S.MOVING_VERTICAL),
    ("Moving horizontal", S.MOVING_HORIZONTAL), ("Crumble (resets)", S.CRUMBLE_RESET), ("Crumble (persistent)", S.CRUMBLE_PERSISTENT),
    ("Kill platform", S.KILL), ("Damage platform", S.DAMAGE), ("Transition box", S.TRANSITION),
]
SLOPE_TYPES = [("Ramp (one-way)", S.SLOPE_ONE_WAY), ("Ramp (solid)", S.SLOPE_SOLID)]
ZOOMS = [0.25, 0.4, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0]
HANDLE_CURSORS = {"n": "SIZENS", "s": "SIZENS", "e": "SIZEWE", "w": "SIZEWE", "ne": "SIZENESW", "sw": "SIZENESW", "nw": "SIZENWSE", "se": "SIZENWSE"}


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def to_int(text, default=0):
    try:
        return int(round(float(text)))
    except (TypeError, ValueError):
        return default


def to_float(text, default=0.0):
    try:
        return float(text)
    except (TypeError, ValueError):
        return default


class Field:
    """State of one text box (the editor mirrors the model into it until it gets focus)."""

    def __init__(self, numeric=True):
        self.value = ""
        self.focused = False
        self.numeric = numeric
        self.setter = None


class Modal:
    """A simple centred dialog: message, optional text fields, and buttons."""

    def __init__(self, title, message="", fields=None, buttons=("OK", "Cancel"), on_result=None, items=None, width=460):
        self.title, self.message = title, message
        self.fields = [(label, key, Field(numeric), default) for (label, key, default, numeric) in (fields or [])]
        for _, _, f, default in self.fields:
            f.value = str(default)
        self.buttons = buttons
        self.on_result = on_result
        self.items = items or []           # (label, value) pairs for list dialogs
        self.scroll = 0
        self.width = width
        self.focus = 0
        if self.fields:
            self.fields[0][2].focused = True
        self.hot = []


class LevelEditor:
    def __init__(self, level_path=None):
        pygame.init()
        pygame.display.set_caption("Level Editor")
        self.screen = pygame.display.set_mode((1440, 900), pygame.RESIZABLE)
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("segoeui,arial,dejavusans", 15)
        self.small = pygame.font.SysFont("segoeui,arial,dejavusans", 12)
        self.big = pygame.font.SysFont("segoeui,arial,dejavusans", 19, bold=True)
        self.running = True
        self.time = 0.0

        # document
        self.level = LevelData.blank()
        self.path = None
        self.dirty = False
        self.undo_stack, self.redo_stack = [], []

        # view
        self.zoom = 1.0
        self.cam = [0.0, 0.0]
        self.grid_on = True
        self.show_bg = True
        self._bg_cache = None

        # interaction state
        self.active_layer = "objects"          # "objects" or an index into level.layers
        self.tool = ("select",)                # ("select",) ("object", kind) ("slope", kind) ("prop", name)
        self.selected = None                   # ("platform"|"slope"|"prop"|"start", index)
        self.drag = None
        self.space_down = False
        self.hover_handle = None
        self.cursor_name = None
        self.status = "Ready"
        self.status_time = 0.0

        # palettes / pickers
        self.palette_scroll = 0
        self.picker_scroll = 0
        self.tileset_name = (assets.list_tilesets() or [None])[0]
        self.brush = []                        # [(dx, dy, col, row)]
        self.brush_sel = None                  # (col0, row0, col1, row1) selection in the picker
        self.slot_sel = "tm"                   # slot being edited in the inspector
        self.source_skin = None                # skin whose tiles are offered for the selected slot
        self.import_tile = 16                  # 16 or 32px art when importing PNGs
        self.fields = {}
        self.hot = []                          # (rect, callback, clip) rebuilt every frame
        self.field_hot = []
        self.modal = None
        self.caps = {}                         # scaled-surface cache

        if level_path and os.path.exists(level_path):
            self.open_path(level_path)
        else:
            first = os.path.join(LD.LEVELS_DIR, "level_01.py")
            if os.path.exists(first):
                self.open_path(first)
            else:
                self.new_level_named(LD.next_level_name(), "Level 1", 200)

    # ====================================================================== document
    def set_status(self, text):
        self.status, self.status_time = text, 4.0

    def checkpoint(self):
        """Call right before mutating the level (pushes an undo snapshot)."""
        self.undo_stack.append(self.level.snapshot())
        if len(self.undo_stack) > 60:
            self.undo_stack.pop(0)
        self.redo_stack.clear()
        self.dirty = True

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(self.level.snapshot())
            self.level.restore(self.undo_stack.pop())
            self.selected = None
            self.dirty = True
            self._bg_cache = None
            self.set_status("Undo")

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(self.level.snapshot())
            self.level.restore(self.redo_stack.pop())
            self.selected = None
            self.dirty = True
            self._bg_cache = None
            self.set_status("Redo")

    def open_path(self, path):
        try:
            self.level = LevelData.load(path)
        except Exception as exc:                     # a broken level file must not kill the editor
            self.set_status(f"Could not open {os.path.basename(path)}: {exc}")
            return
        self.path = os.path.abspath(path)
        self.dirty = False
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.selected = None
        self.active_layer = "objects"
        self.cam = [0.0, 0.0]
        self._bg_cache = None
        self.set_status(f"Opened {os.path.basename(path)}")

    def new_level_named(self, filename, title, width_tiles):
        filename = "".join(c for c in filename if c.isalnum() or c in "_-") or LD.next_level_name()
        path = os.path.join(LD.LEVELS_DIR, filename + ".py")
        if os.path.exists(path):
            self.set_status(f"{filename}.py already exists - choose another name")
            return False
        self.level = LevelData.blank(title or filename, max(60, width_tiles) * GRID)
        self.path = path
        self.level.save(path)                         # written right away so portals can target it
        self.dirty = False
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.selected = None
        self.active_layer = "objects"
        self.cam = [0.0, 0.0]
        self._bg_cache = None
        self.set_status(f"Created {filename}.py")
        return True

    def save(self):
        if not self.path:
            self.save_as()
            return
        try:
            self.level.save(self.path)
        except OSError as exc:
            self.set_status(f"Save failed: {exc}")
            return
        self.dirty = False
        self.set_status(f"Saved {os.path.basename(self.path)}")

    def save_as(self):
        default = os.path.splitext(os.path.basename(self.path))[0] if self.path else LD.next_level_name()

        def done(vals):
            name = "".join(c for c in vals["name"] if c.isalnum() or c in "_-")
            if name:
                self.path = os.path.join(LD.LEVELS_DIR, name + ".py")
                self.save()
        self.modal = Modal("Save level as", "File name inside the levels/ folder (this is the name portals use):",
                           [("File name", "name", default, False)], on_result=done)

    def confirm_discard(self, then):
        if not self.dirty:
            then()
            return
        self.modal = Modal("Unsaved changes", "Discard the unsaved changes to this level?", buttons=("Discard", "Cancel"),
                           on_result=lambda v: then())

    def action_new(self):
        def ask():
            def done(vals):
                self.new_level_named(vals["file"], vals["title"], to_int(vals["width"], 200))
            self.modal = Modal("New level", "Creates levels/<file>.py with a starter floor.",
                               [("File name", "file", LD.next_level_name(), False), ("Title", "title", "New Level", False),
                                ("Width (tiles of 16px)", "width", 200, True)], on_result=done)
        self.confirm_discard(ask)

    def action_open(self):
        def ask():
            items = [(n, n) for n in LD.available_levels()]
            self.modal = Modal("Open level", "Pick a level:", items=items,
                               on_result=lambda v: self.open_path(os.path.join(LD.LEVELS_DIR, v + ".py")), buttons=("Cancel",))
        self.confirm_discard(ask)

    # ============================================================== coordinate helpers
    def canvas_rect(self):
        w, h = self.screen.get_size()
        return pygame.Rect(LEFT_W, TOP_H, w - LEFT_W - RIGHT_W, h - TOP_H - BOTTOM_H)

    def to_screen(self, wx, wy):
        c = self.canvas_rect()
        return c.x + (wx - self.cam[0]) * self.zoom, c.y + (wy - self.cam[1]) * self.zoom

    def to_world(self, sx, sy):
        c = self.canvas_rect()
        return (sx - c.x) / self.zoom + self.cam[0], (sy - c.y) / self.zoom + self.cam[1]

    def snapv(self, v):
        return LD.snap(v, GRID) if self.grid_on else int(round(v))

    def world_rect_to_screen(self, x, y, w, h):
        sx, sy = self.to_screen(x, y)
        return pygame.Rect(round(sx), round(sy), max(1, round(w * self.zoom)), max(1, round(h * self.zoom)))

    def scaled(self, key, surf):
        """Surface scaled to the current zoom (cached)."""
        if self.zoom == 1.0:
            return surf
        ck = (key, self.zoom)
        out = self.caps.get(ck)
        if out is None:
            if len(self.caps) > 900:
                self.caps.clear()
            out = self.caps[ck] = pygame.transform.scale(surf, (max(1, round(surf.get_width() * self.zoom)), max(1, round(surf.get_height() * self.zoom))))
        return out

    # ================================================================= model queries
    def item_list(self, group):
        return {"platform": self.level.platforms, "slope": self.level.slopes, "prop": self.level.props}[group]

    def selected_item(self):
        if not self.selected or self.selected[0] == "start":
            return None
        group, idx = self.selected
        items = self.item_list(group)
        return items[idx] if 0 <= idx < len(items) else None

    def prop_size(self, prop):
        img = assets.load_image(assets.path("props", prop["name"] + ".png"))
        meta = assets.load_json(assets.path("props", prop["name"] + ".json"), {})
        frames = max(1, int(prop["options"].get("frames", meta.get("frames", 1))))
        return img.get_width() // frames, img.get_height()

    def item_rect(self, group, item):
        if group == "prop":
            w, h = self.prop_size(item)
            return item["x"], item["y"], w, h
        return item["x"], item["y"], item["w"], item["h"]

    def hit_item(self, wx, wy):
        for group in ("prop", "slope", "platform"):
            items = self.item_list(group)
            for idx in range(len(items) - 1, -1, -1):
                x, y, w, h = self.item_rect(group, items[idx])
                if x <= wx <= x + w and y <= wy <= y + h:
                    if group == "slope" and not self._in_triangle(items[idx], wx, wy):
                        continue
                    return group, idx
        return None

    @staticmethod
    def _in_triangle(s, wx, wy):
        u = (wx - s["x"]) / s["w"]
        edge = s["y"] + s["h"] * ((1 - u) if s["direction"] == "up_right" else u)
        return wy >= edge - 4

    # ============================================================== immediate-mode UI
    def btn(self, rect, label, callback, active=False, enabled=True, font=None, color=None):
        rect = pygame.Rect(rect)
        hover = rect.collidepoint(pygame.mouse.get_pos()) and enabled and self.modal is None
        bg = (58, 18, 20) if active else (40, 26, 28) if hover else PANEL2
        pygame.draw.rect(self.screen, bg, rect, border_radius=4)
        pygame.draw.rect(self.screen, ACCENT if active else BORDER, rect, 1, border_radius=4)
        f = font or self.small
        surf = f.render(label, True, color or (TEXT if enabled else MUTED))
        self.screen.blit(surf, surf.get_rect(center=rect.center))
        if enabled and callback:
            self.hot.append((rect, callback, self.screen.get_clip()))

    def label(self, text, pos, color=MUTED, font=None):
        self.screen.blit((font or self.small).render(str(text), True, color), pos)

    def header(self, text, x, y, w):
        self.label(text.upper(), (x, y), ACCENT_DIM, self.small)
        pygame.draw.line(self.screen, BORDER, (x, y + 15), (x + w, y + 15))
        return y + 22

    def field(self, key, rect, label, getter, setter, numeric=True):
        rect = pygame.Rect(rect)
        f = self.fields.setdefault(key, Field(numeric))
        f.numeric, f.setter = numeric, setter
        if not f.focused:
            try:
                f.value = str(getter())
            except Exception:
                f.value = ""
        self.label(label, (rect.x, rect.y - 14))
        pygame.draw.rect(self.screen, (10, 6, 8), rect, border_radius=3)
        pygame.draw.rect(self.screen, ACCENT if f.focused else BORDER, rect, 1, border_radius=3)
        text = f.value + ("|" if f.focused and int(self.time * 2) % 2 == 0 else "")
        self.screen.set_clip(rect.inflate(-6, 0))
        self.screen.blit(self.font.render(text, True, TEXT), (rect.x + 6, rect.y + 4))
        self.screen.set_clip(None)
        self.field_hot.append((rect, key))

    def commit_field(self, key):
        f = self.fields.get(key)
        if f and f.focused:
            f.focused = False
            if f.setter:
                f.setter(f.value)

    def blur_fields(self):
        for key in list(self.fields):
            self.commit_field(key)

    def overlay(self, rect, color):
        s = pygame.Surface(rect.size, pygame.SRCALPHA)
        s.fill(color)
        self.screen.blit(s, rect.topleft)

    # =================================================================== canvas drawing
    def prop_surface(self, name, frames):
        key = ("prop", name, frames)
        surf = self.caps.get(key)
        if surf is None:
            img = assets.load_image(assets.path("props", name + ".png"))
            w = img.get_width() // max(1, frames)
            surf = pygame.Surface((w, img.get_height()), pygame.SRCALPHA)
            surf.blit(img, (0, 0), (0, 0, w, img.get_height()))
            self.caps[key] = surf
        return surf

    def draw_background_preview(self, c):
        if not self.show_bg:
            return
        view_w = int(c.w / self.zoom) + 2
        key = (self.level.background, int(self.cam[0]), self.zoom, view_w)
        if self._bg_cache is None or self._bg_cache[0] != key:
            temp = pygame.Surface((view_w, S.SCREEN_HEIGHT))
            try:
                get_background(self.level.background).draw(temp, self.cam[0], 0)
            except Exception:
                temp.fill((0, 0, 0))
            scaled = pygame.transform.scale(temp, (round(view_w * self.zoom), round(S.SCREEN_HEIGHT * self.zoom))) if self.zoom != 1.0 else temp
            self._bg_cache = (key, scaled)
        sy = self.to_screen(0, 0)[1]
        self.screen.blit(self._bg_cache[1], (c.x, round(sy)))

    def draw_grid(self, c):
        if not self.grid_on:
            return
        step = GRID if self.zoom >= 0.75 else GRID * 4 if self.zoom >= 0.4 else GRID * 8
        x0, y0 = self.to_world(c.x, c.y)
        x1, y1 = self.to_world(c.right, c.bottom)
        gx = int(math.floor(x0 / step)) * step
        while gx <= x1:
            sx = round(self.to_screen(gx, 0)[0])
            pygame.draw.line(self.screen, GRID_COL2 if (gx // step) % 4 == 0 else GRID_COL, (sx, c.y), (sx, c.bottom))
            gx += step
        gy = int(math.floor(y0 / step)) * step
        while gy <= y1:
            sy = round(self.to_screen(0, gy)[1])
            pygame.draw.line(self.screen, GRID_COL2 if (gy // step) % 4 == 0 else GRID_COL, (c.x, sy), (c.right, sy))
            gy += step

    def draw_tile_layer(self, layer, c):
        x0, y0 = self.to_world(c.x, c.y)
        x1, y1 = self.to_world(c.right, c.bottom)
        tx0, tx1 = int(math.floor(x0 / GRID)), int(math.floor(x1 / GRID))
        ty0, ty1 = int(math.floor(y0 / GRID)), int(math.floor(y1 / GRID))
        tiles = layer["tiles"]
        for ty in range(ty0, ty1 + 1):
            for tx in range(tx0, tx1 + 1):
                t = tiles.get((tx, ty))
                if t is None:
                    continue
                try:
                    surf = self.scaled(("tile",) + tuple(t), get_tileset(t[0]).tile(t[1], t[2]))
                except Exception:
                    continue
                sx, sy = self.to_screen(tx * GRID, ty * GRID)
                self.screen.blit(surf, (round(sx), round(sy)))

    def draw_object(self, group, item, selected):
        frame_t = self.time
        if group == "platform":
            skin = get_skin(item["options"].get("skin") or S.DEFAULT_SKINS[item["kind"]])
            ov = item["options"].get("tiles") or None
            f = skin.frame_index(frame_t)
            ovk = tuple(sorted((k, tuple(v)) for k, v in ov.items())) if ov else ()
            surf = self.scaled(("p", skin.name, item["w"], item["h"], f, ovk), skin.render(item["w"], item["h"], f, ov))
            sx, sy = self.to_screen(item["x"], item["y"])
            self.screen.blit(surf, (round(sx), round(sy)))
            if item["kind"] in (S.MOVING_HORIZONTAL, S.MOVING_VERTICAL):
                self.draw_travel(item, selected)
            if item["kind"] == S.TRANSITION:
                self.label(">  " + str(item["options"].get("target", "?")), (round(sx), round(sy) - 15), (190, 150, 150))
        elif group == "slope":
            skin = get_skin(item["options"].get("skin") or S.DEFAULT_SKINS[item["kind"]])
            ov = item["options"].get("tiles") or None
            f = skin.frame_index(frame_t)
            ovk = tuple(sorted((k, tuple(v)) for k, v in ov.items())) if ov else ()
            one_way = item["kind"] == S.SLOPE_ONE_WAY
            surf = self.scaled(("s", skin.name, item["w"], item["h"], item["direction"], one_way, f, ovk),
                               skin.render_slope(item["w"], item["h"], item["direction"] == "up_right", one_way, f, ov))
            sx, sy = self.to_screen(item["x"], item["y"])
            self.screen.blit(surf, (round(sx), round(sy)))
        else:
            w, h = self.prop_size(item)
            meta = assets.load_json(assets.path("props", item["name"] + ".json"), {})
            frames = max(1, int(item["options"].get("frames", meta.get("frames", 1))))
            surf = self.scaled(("pr", item["name"], frames), self.prop_surface(item["name"], frames))
            sx, sy = self.to_screen(item["x"], item["y"])
            self.screen.blit(surf, (round(sx), round(sy)))
            if item["options"].get("layer") == "front":
                pygame.draw.rect(self.screen, (120, 80, 160), pygame.Rect(round(sx), round(sy), round(w * self.zoom), round(h * self.zoom)), 1)

    def draw_travel(self, item, selected):
        o, w, h = item["options"], item["w"], item["h"]
        if item["kind"] == S.MOVING_HORIZONTAL:
            a, b = (o.get("min_x", item["x"]), item["y"]), (o.get("max_x", item["x"]), item["y"])
        else:
            a, b = (item["x"], o.get("min_y", item["y"])), (item["x"], o.get("max_y", item["y"]))
        col = ACCENT if selected else (96, 40, 44)
        ra, rb = self.world_rect_to_screen(a[0], a[1], w, h), self.world_rect_to_screen(b[0], b[1], w, h)
        pygame.draw.line(self.screen, col, ra.center, rb.center, 1)
        for r in (ra, rb):
            pygame.draw.rect(self.screen, col, r, 1)

    def selection_handles(self):
        """(handle, screen rect) for the selected object's 8 resize handles (empty for props/start)."""
        if not self.selected or self.selected[0] in ("prop", "start"):
            return []
        item = self.selected_item()
        if item is None:
            return []
        pts = LD.handle_points(item["x"], item["y"], item["w"], item["h"])
        out = []
        for name in LD.HANDLES:
            sx, sy = self.to_screen(*pts[name])
            out.append((name, pygame.Rect(round(sx) - 5, round(sy) - 5, 10, 10)))
        return out

    def draw_canvas(self):
        c = self.canvas_rect()
        pygame.draw.rect(self.screen, BG, c)
        self.screen.set_clip(c)
        self.draw_background_preview(c)
        self.draw_grid(c)
        lv = self.level
        bounds = self.world_rect_to_screen(0, 0, lv.width, lv.height)
        for layer in lv.layers:
            if layer["order"] != "front" and layer.get("visible", True):
                self.draw_tile_layer(layer, c)
        for prop in lv.props:
            if prop["options"].get("layer") != "front":
                self.draw_object("prop", prop, False)
        for i, p in enumerate(lv.platforms):
            self.draw_object("platform", p, self.selected == ("platform", i))
        for i, s in enumerate(lv.slopes):
            self.draw_object("slope", s, self.selected == ("slope", i))
        for prop in lv.props:
            if prop["options"].get("layer") == "front":
                self.draw_object("prop", prop, False)
        for layer in lv.layers:
            if layer["order"] == "front" and layer.get("visible", True):
                self.draw_tile_layer(layer, c)
        pygame.draw.rect(self.screen, (90, 40, 44), bounds, 2)

        # player start marker
        sx, sy = self.to_screen(*lv.start)
        marker = pygame.Rect(round(sx), round(sy), round(32 * self.zoom), round(48 * self.zoom))
        pygame.draw.rect(self.screen, GOOD, marker, 1)
        pygame.draw.line(self.screen, GOOD, marker.midbottom, (marker.centerx, marker.bottom + 6))
        self.label("START", (marker.x, marker.y - 14), GOOD)
        if self.selected == ("start", 0):
            pygame.draw.rect(self.screen, (255, 255, 255), marker.inflate(6, 6), 1)

        # selection outline + handles
        item = self.selected_item()
        if item is not None:
            group = self.selected[0]
            x, y, w, h = self.item_rect(group, item)
            r = self.world_rect_to_screen(x, y, w, h)
            pygame.draw.rect(self.screen, (255, 255, 255), r.inflate(4, 4), 1)
            for name, hr in self.selection_handles():
                active = name == self.hover_handle or (self.drag and self.drag.get("handle") == name)
                pygame.draw.rect(self.screen, ACCENT if active else (240, 230, 226), hr)
                pygame.draw.rect(self.screen, BG, hr, 1)
            self.label(f"{w // GRID} x {h // GRID} tiles  ({w} x {h}px)", (r.x, r.bottom + 6), TEXT)

        # placement preview / tile brush preview
        mx, my = pygame.mouse.get_pos()
        if c.collidepoint(mx, my) and self.modal is None:
            wx, wy = self.to_world(mx, my)
            if self.active_layer != "objects":
                self.draw_brush_preview(wx, wy)
            elif self.tool[0] != "select" and not self.drag:
                r = self.world_rect_to_screen(self.snapv(wx), self.snapv(wy), GRID, GRID)
                pygame.draw.rect(self.screen, ACCENT, r, 1)
        if self.drag and self.drag.get("mode") == "rect":
            x0, y0, x1, y1 = self.drag["cells"]
            r = self.world_rect_to_screen(min(x0, x1) * GRID, min(y0, y1) * GRID, (abs(x1 - x0) + 1) * GRID, (abs(y1 - y0) + 1) * GRID)
            pygame.draw.rect(self.screen, ACCENT, r, 2)
        self.screen.set_clip(None)
        mode_col = ACCENT if self.active_layer != "objects" else BORDER
        pygame.draw.rect(self.screen, mode_col, c, 2)

    def draw_brush_preview(self, wx, wy):
        if not self.brush or not self.tileset_name:
            return
        tx, ty = int(math.floor(wx / GRID)), int(math.floor(wy / GRID))
        ts = get_tileset(self.tileset_name)
        for dx, dy, col, row in self.brush:
            surf = self.scaled(("tile", self.tileset_name, col, row), ts.tile(col, row))
            sx, sy = self.to_screen((tx + dx) * GRID, (ty + dy) * GRID)
            prev = surf.copy()
            prev.set_alpha(150)
            self.screen.blit(prev, (round(sx), round(sy)))
        sx, sy = self.to_screen(tx * GRID, ty * GRID)
        pygame.draw.rect(self.screen, ACCENT, pygame.Rect(round(sx), round(sy), round(GRID * self.zoom), round(GRID * self.zoom)), 1)

    # ==================================================================== top bar
    def draw_top(self):
        w = self.screen.get_width()
        pygame.draw.rect(self.screen, PANEL, (0, 0, w, TOP_H))
        pygame.draw.line(self.screen, BORDER, (0, TOP_H - 1), (w, TOP_H - 1))
        x = 10
        for label, cb, bw in (("New", self.action_new, 54), ("Open", self.action_open, 58), ("Save", self.save, 58), ("Save as", self.save_as, 70)):
            self.btn((x, 10, bw, 30), label, cb)
            x += bw + 6
        x += 10
        self.btn((x, 10, 54, 30), "Undo", self.undo, enabled=bool(self.undo_stack)); x += 60
        self.btn((x, 10, 54, 30), "Redo", self.redo, enabled=bool(self.redo_stack)); x += 70
        self.btn((x, 10, 78, 30), "Grid: ON" if self.grid_on else "Grid: OFF", self.toggle_grid, active=self.grid_on); x += 84
        self.btn((x, 10, 70, 30), "BG: ON" if self.show_bg else "BG: OFF", self.toggle_bg, active=self.show_bg); x += 80
        self.btn((x, 10, 28, 30), "-", lambda: self.zoom_by(-1)); x += 32
        self.label(f"{int(self.zoom * 100)}%", (x, 17), TEXT, self.font); x += 46
        self.btn((x, 10, 28, 30), "+", lambda: self.zoom_by(1)); x += 36
        self.btn((x, 10, 70, 30), "Reset view", self.reset_view)
        title = f"{self.level.name}  -  {os.path.basename(self.path) if self.path else 'unsaved'}{' *' if self.dirty else ''}"
        self.label(title, (w - RIGHT_W - 10 - self.font.size(title)[0] + RIGHT_W, 16), TEXT, self.font)

    def toggle_grid(self):
        self.grid_on = not self.grid_on

    def toggle_bg(self):
        self.show_bg = not self.show_bg

    def reset_view(self):
        self.zoom, self.cam = 1.0, [0.0, 0.0]
        self._bg_cache = None

    def zoom_by(self, step, anchor=None):
        c = self.canvas_rect()
        ax, ay = anchor or c.center
        before = self.to_world(ax, ay)
        idx = min(range(len(ZOOMS)), key=lambda i: abs(ZOOMS[i] - self.zoom))
        self.zoom = ZOOMS[clamp(idx + step, 0, len(ZOOMS) - 1)]
        after = self.to_world(ax, ay)
        self.cam[0] += before[0] - after[0]
        self.cam[1] += before[1] - after[1]
        self._bg_cache = None

    # ================================================================ left panel
    def draw_left(self):
        h = self.screen.get_height()
        pygame.draw.rect(self.screen, PANEL, (0, TOP_H, LEFT_W, h - TOP_H))
        pygame.draw.line(self.screen, BORDER, (LEFT_W - 1, TOP_H), (LEFT_W - 1, h))
        x, w = 10, LEFT_W - 20
        y = self.header("Layers", x, TOP_H + 10, w)
        rows = [("objects", "Objects (collision + props)", None)] + [(i, l["name"], l) for i, l in enumerate(self.level.layers)]
        for key, name, layer in rows:
            r = pygame.Rect(x, y, w, 22)
            active = self.active_layer == key
            pygame.draw.rect(self.screen, (52, 22, 24) if active else PANEL2, r, border_radius=3)
            pygame.draw.rect(self.screen, ACCENT if active else BORDER, r, 1, border_radius=3)
            if layer is not None:
                vis = layer.get("visible", True)
                self.btn((x + 3, y + 3, 16, 16), "o" if vis else "-", (lambda L=layer: L.update(visible=not L.get("visible", True))), active=vis)
                tag = ("B" if layer["order"] != "front" else "F") + (f" {layer['dim']:.1f}" if layer["dim"] else "")
                self.label(tag, (r.right - 44, y + 4), MUTED)
                self.label(name[:20], (x + 26, y + 4), TEXT)
            else:
                self.label(name, (x + 8, y + 4), TEXT)
            self.hot.append((pygame.Rect(x + 22, y, w - 70, 22), (lambda k=key: self.select_layer(k)), None))
            y += 25
        y += 4
        lay = self.active_layer if self.active_layer != "objects" else None
        row = [("+ Layer", self.add_layer, True), ("Delete", self.delete_layer, lay is not None), ("Up", lambda: self.move_layer(-1), lay is not None),
               ("Down", lambda: self.move_layer(1), lay is not None)]
        bw = (w - 9) // 4
        for i, (label, cb, en) in enumerate(row):
            self.btn((x + i * (bw + 3), y, bw, 22), label, cb, enabled=en)
        y += 26
        row = [("Rename", self.rename_layer, lay is not None), ("Back/Front", self.flip_layer_order, lay is not None),
               ("Dim -", lambda: self.dim_layer(-0.1), lay is not None), ("Dim +", lambda: self.dim_layer(0.1), lay is not None)]
        for i, (label, cb, en) in enumerate(row):
            self.btn((x + i * (bw + 3), y, bw, 22), label, cb, enabled=en)
        y += 34
        if self.active_layer == "objects":
            self.draw_object_palette(x, y, w)
        else:
            self.draw_tile_palette(x, y, w)

    def select_layer(self, key):
        self.active_layer = key
        self.tool = ("select",)
        self.selected = None

    def add_layer(self):
        def done(vals):
            self.checkpoint()
            self.level.layers.append({"name": vals["name"] or "Layer", "order": vals["order"].lower().startswith("f") and "front" or "back",
                                      "dim": 0.0, "tiles": {}, "visible": True})
            self.active_layer = len(self.level.layers) - 1
        self.modal = Modal("New tile layer", "Back layers draw behind the platforms, front layers over the player.",
                           [("Name", "name", f"Layer {len(self.level.layers) + 1}", False), ("Order (back / front)", "order", "back", False)], on_result=done)

    def delete_layer(self):
        if self.active_layer == "objects":
            return
        idx = self.active_layer

        def done(_):
            self.checkpoint()
            del self.level.layers[idx]
            self.active_layer = "objects"
        self.modal = Modal("Delete layer", f"Delete layer '{self.level.layers[idx]['name']}' and all of its tiles?", buttons=("Delete", "Cancel"), on_result=done)

    def move_layer(self, d):
        i = self.active_layer
        if i == "objects" or not 0 <= i + d < len(self.level.layers):
            return
        self.checkpoint()
        L = self.level.layers
        L[i], L[i + d] = L[i + d], L[i]
        self.active_layer = i + d

    def rename_layer(self):
        layer = self.level.layers[self.active_layer]

        def done(vals):
            self.checkpoint()
            layer["name"] = vals["name"] or layer["name"]
        self.modal = Modal("Rename layer", "", [("Name", "name", layer["name"], False)], on_result=done)

    def flip_layer_order(self):
        self.checkpoint()
        layer = self.level.layers[self.active_layer]
        layer["order"] = "front" if layer["order"] != "front" else "back"

    def dim_layer(self, d):
        self.checkpoint()
        layer = self.level.layers[self.active_layer]
        layer["dim"] = round(clamp(layer["dim"] + d, 0.0, 0.9), 2)

    # ------------------------------------------------------------------ object palette
    def draw_object_palette(self, x, y, w):
        h = self.screen.get_height()
        y = self.header("Objects", x, y, w)
        area = pygame.Rect(x - 4, y, w + 8, h - BOTTOM_H - y - 4)
        self.screen.set_clip(area)
        yy = y - self.palette_scroll
        entries = [("Select / move", ("select",), None)]
        entries += [(n, ("object", k), S.DEFAULT_SKINS[k]) for n, k in OBJECT_TYPES]
        entries += [("-", None, None)]
        entries += [(n, ("slope", k), S.DEFAULT_SKINS[k]) for n, k in SLOPE_TYPES]
        entries += [("-", None, None)]
        entries += [(f"Prop: {n}", ("prop", n), None) for n in assets.list_props()]
        for label, tool, skin_name in entries:
            if tool is None:
                yy += 8
                continue
            r = pygame.Rect(x, yy, w, 32)
            active = self.tool == tool
            pygame.draw.rect(self.screen, (52, 22, 24) if active else PANEL2, r, border_radius=4)
            pygame.draw.rect(self.screen, ACCENT if active else BORDER, r, 1, border_radius=4)
            self.draw_thumb(tool, skin_name, pygame.Rect(x + 4, yy + 4, 42, 24))
            self.label(label, (x + 54, yy + 9), TEXT)
            self.hot.append((r, (lambda t=tool: self.set_tool(t)), area))
            yy += 36
        yy += 4
        self.btn((x, yy, w, 26), "Import prop PNG...", lambda: self.import_png("props"))
        self.content_h = yy + 40 - (y - self.palette_scroll)
        self.palette_area = area
        self.screen.set_clip(None)

    def draw_thumb(self, tool, skin_name, rect):
        if tool[0] == "select":
            pygame.draw.polygon(self.screen, TEXT, [(rect.x + 8, rect.y + 2), (rect.x + 8, rect.y + 20), (rect.x + 13, rect.y + 15), (rect.x + 17, rect.y + 22), (rect.x + 20, rect.y + 20), (rect.x + 16, rect.y + 14), (rect.x + 22, rect.y + 14)])
            return
        if tool[0] == "prop":
            img = self.prop_surface(tool[1], max(1, int((assets.load_json(assets.path("props", tool[1] + ".json"), {}) or {}).get("frames", 1))))
            k = min(rect.w / img.get_width(), rect.h / img.get_height(), 1.0)
            self.screen.blit(pygame.transform.scale(img, (max(1, int(img.get_width() * k)), max(1, int(img.get_height() * k)))), rect.topleft)
            return
        skin = get_skin(skin_name)
        if tool[0] == "slope":
            surf = skin.render_slope(48, 24, True, tool[1] == S.SLOPE_ONE_WAY, 0, None)
        else:
            surf = skin.render(48, 24, 0, None)
        self.screen.blit(surf, rect.topleft, (0, 0, rect.w, rect.h))

    def set_tool(self, tool):
        self.tool = tool
        self.selected = None if tool[0] != "select" else self.selected
        self.set_status("Drag on the canvas to draw" if tool[0] in ("object", "slope") else "Click the canvas to place" if tool[0] == "prop" else "Select tool")

    # ------------------------------------------------------------------ tile palette
    def draw_tile_palette(self, x, y, w):
        h = self.screen.get_height()
        y = self.header("Tileset", x, y, w)
        names = assets.list_tilesets()
        if self.tileset_name not in names:
            self.tileset_name = names[0] if names else None
        self.btn((x, y, 26, 24), "<", lambda: self.cycle_tileset(-1))
        self.btn((x + w - 26, y, 26, 24), ">", lambda: self.cycle_tileset(1))
        self.label(self.tileset_name or "(none)", (x + 34, y + 5), TEXT, self.font)
        y += 30
        self.btn((x, y, w - 62, 24), "Import tileset PNG...", lambda: self.import_png("tilesets"))
        self.btn((x + w - 58, y, 58, 24), f"{self.import_tile}px art", self.toggle_import_tile)
        y += 32
        self.picker_rect = pygame.Rect(x, y, w, h - BOTTOM_H - y - 40)
        pygame.draw.rect(self.screen, (8, 4, 6), self.picker_rect)
        pygame.draw.rect(self.screen, BORDER, self.picker_rect, 1)
        if self.tileset_name:
            ts = get_tileset(self.tileset_name)
            scale = 2
            self.screen.set_clip(self.picker_rect)
            big = self.scaled_picker(ts, scale)
            ox, oy = self.picker_rect.x + 2, self.picker_rect.y + 2 - self.picker_scroll
            self.screen.blit(big, (ox, oy))
            for c in range(ts.cols + 1):
                pygame.draw.line(self.screen, (30, 18, 20), (ox + c * GRID * scale, oy), (ox + c * GRID * scale, oy + ts.rows * GRID * scale))
            for r in range(ts.rows + 1):
                pygame.draw.line(self.screen, (30, 18, 20), (ox, oy + r * GRID * scale), (ox + ts.cols * GRID * scale, oy + r * GRID * scale))
            if self.brush_sel:
                c0, r0, c1, r1 = self.brush_sel
                sel = pygame.Rect(ox + min(c0, c1) * GRID * scale, oy + min(r0, r1) * GRID * scale, (abs(c1 - c0) + 1) * GRID * scale, (abs(r1 - r0) + 1) * GRID * scale)
                pygame.draw.rect(self.screen, ACCENT, sel, 2)
            self.screen.set_clip(None)
            self.picker_origin = (ox, oy, scale)
        self.label("drag to pick a block - Alt+click on canvas picks", (x, self.picker_rect.bottom + 6))

    def scaled_picker(self, ts, scale):
        key = ("picker", ts.name, scale)
        surf = self.caps.get(key)
        if surf is None:
            surf = self.caps[key] = pygame.transform.scale(ts.image, (ts.image.get_width() * scale, ts.image.get_height() * scale))
        return surf

    def cycle_tileset(self, d):
        names = assets.list_tilesets()
        if names:
            self.tileset_name = names[(names.index(self.tileset_name) + d) % len(names)] if self.tileset_name in names else names[0]
            self.brush, self.brush_sel, self.picker_scroll = [], None, 0

    def toggle_import_tile(self):
        self.import_tile = 32 if self.import_tile == 16 else 16

    def picker_cell(self, pos):
        if not self.tileset_name or not hasattr(self, "picker_origin"):
            return None
        ox, oy, scale = self.picker_origin
        ts = get_tileset(self.tileset_name)
        col, row = int((pos[0] - ox) // (GRID * scale)), int((pos[1] - oy) // (GRID * scale))
        if 0 <= col < ts.cols and 0 <= row < ts.rows:
            return col, row
        return None

    def set_brush_from_selection(self):
        c0, r0, c1, r1 = self.brush_sel
        ca, cb, ra, rb = min(c0, c1), max(c0, c1), min(r0, r1), max(r0, r1)
        self.brush = [(c - ca, r - ra, c, r) for r in range(ra, rb + 1) for c in range(ca, cb + 1)]

    # ================================================================== right panel
    def draw_right(self):
        w, h = self.screen.get_size()
        panel = pygame.Rect(w - RIGHT_W, TOP_H, RIGHT_W, h - TOP_H - BOTTOM_H)
        pygame.draw.rect(self.screen, PANEL, panel)
        pygame.draw.line(self.screen, BORDER, (panel.x, TOP_H), (panel.x, h))
        self.screen.set_clip(panel)
        self.right_panel = panel
        x, width = panel.x + 12, RIGHT_W - 24
        y = TOP_H + 10 - self.right_scroll
        sel, item = self.selected, self.selected_item()
        if sel and sel[0] == "start":
            y = self.inspect_start(x, y, width)
        elif item is not None and sel[0] in ("platform", "slope"):
            y = self.inspect_shape(sel[0], item, x, y, width)
        elif item is not None and sel[0] == "prop":
            y = self.inspect_prop(item, x, y, width)
        else:
            y = self.header("Inspector", x, y, width)
            self.label("Nothing selected.", (x, y), MUTED)
            self.label("Pick a type on the left and drag on", (x, y + 18), MUTED)
            self.label("the canvas, or click an object.", (x, y + 34), MUTED)
            y += 60
        y = self.inspect_level(x, y + 14, width)
        self.right_content = y + self.right_scroll - TOP_H
        self.screen.set_clip(None)

    def edit(self, fn):
        self.checkpoint()
        fn()
        self._bg_cache = None

    def row_fields(self, y, x, width, specs):
        """Lay out up to 3 text fields in a row. specs: (key, label, getter, setter, numeric)."""
        n = len(specs)
        fw = (width - (n - 1) * 8) // n
        for i, (key, label, getter, setter, numeric) in enumerate(specs):
            self.field(key, (x + i * (fw + 8), y + 14, fw, 24), label, getter, setter, numeric)
        return y + 50

    def inspect_shape(self, group, item, x, y, width):
        kind = item["kind"]
        title = {k: n for n, k in OBJECT_TYPES + SLOPE_TYPES}.get(kind, kind)
        y = self.header(title, x, y, width)
        gid = f"{group}{self.selected[1]}"

        def geom(key):
            return (lambda: item[key]), (lambda v, key=key: self.set_geom(item, key, v))
        specs = []
        for key, label in (("x", "X (px)"), ("y", "Y (px)")):
            g, s = geom(key); specs.append((f"{gid}.{key}", label, g, s, True))
        y = self.row_fields(y, x, width, specs)
        specs = []
        for key, label in (("w", "Width (px)"), ("h", "Height (px)")):
            g, s = geom(key); specs.append((f"{gid}.{key}", label, g, s, True))
        y = self.row_fields(y, x, width, specs)
        self.label(f"= {item['w'] // GRID} x {item['h'] // GRID} tiles   (drag the edges on the canvas to resize)", (x, y - 8), MUTED)
        y += 14

        # skin
        opts = item["options"]
        skin_name = opts.get("skin") or S.DEFAULT_SKINS[kind]
        self.label("TEXTURE (skin PNG)", (x, y), ACCENT_DIM)
        y += 16
        self.btn((x, y, 26, 24), "<", lambda: self.cycle_skin(item, -1))
        self.btn((x + width - 92, y, 26, 24), ">", lambda: self.cycle_skin(item, 1))
        self.btn((x + width - 62, y, 62, 24), "Import", lambda: self.import_png("skins"))
        self.label(skin_name, (x + 34, y + 5), TEXT, self.font)
        y += 32

        # tile slots
        skin = get_skin(skin_name)
        overrides = opts.get("tiles") or {}
        tw, th = max(1, math.ceil(item["w"] / GRID)), max(1, math.ceil(item["h"] / GRID))
        used = {"mm", "tm"} if group == "slope" else {slot_for(tx, ty, tw, th) for ty in range(th) for tx in range(tw)}
        self.label("TILE SLOTS  (first / middle / last, top / middle / bottom)", (x, y), ACCENT_DIM)
        y += 16
        cw, ch = (width - 4) // 3, 40
        for i, slot in enumerate(SLOT_NAMES):
            cx, cy = x + (i % 3) * (cw + 2), y + (i // 3) * (ch + 2)
            r = pygame.Rect(cx, cy, cw, ch)
            sel = slot == self.slot_sel
            pygame.draw.rect(self.screen, (40, 18, 20) if sel else (10, 6, 8), r)
            pygame.draw.rect(self.screen, ACCENT if sel else (BORDER if slot in used else (36, 24, 26)), r, 2 if sel else 1)
            tile = pygame.transform.scale(skin.slot_tile(slot, skin.frame_index(self.time), overrides), (32, 32))
            if slot not in used:
                tile = tile.copy()
                tile.set_alpha(80)
            self.screen.blit(tile, (r.x + 4, r.y + 4))
            self.label(slot, (r.x + 42, r.y + 4), TEXT if slot in used else MUTED)
            self.label("custom" if slot in overrides else "skin", (r.x + 42, r.y + 20), ACCENT if slot in overrides else MUTED)
            self.hot.append((r, (lambda s=slot: setattr(self, "slot_sel", s)), self.screen.get_clip()))
        y += 4 * (ch + 2) + 6

        # tile source picker for the selected slot
        src_name = self.source_skin or skin_name
        src = get_skin(src_name)
        self.label(f"PICK A TILE FOR '{self.slot_sel}' FROM:", (x, y), ACCENT_DIM)
        y += 16
        self.btn((x, y, 26, 22), "<", lambda: self.cycle_source(-1))
        self.btn((x + 30, y, 26, 22), ">", lambda: self.cycle_source(1))
        self.label(src_name, (x + 64, y + 4), TEXT)
        y += 28
        sheet = pygame.Surface((src.frame_w, src.image.get_height()), pygame.SRCALPHA)
        sheet.blit(src.image, (0, 0), (0, 0, src.frame_w, src.image.get_height()))
        scale = 2 if sheet.get_width() <= 120 else 1
        big = pygame.transform.scale(sheet, (sheet.get_width() * scale, sheet.get_height() * scale))
        sheet_rect = pygame.Rect(x, y, big.get_width(), big.get_height())
        pygame.draw.rect(self.screen, (8, 4, 6), sheet_rect)
        self.screen.blit(big, sheet_rect.topleft)
        for c in range(sheet.get_width() // GRID + 1):
            pygame.draw.line(self.screen, (30, 18, 20), (x + c * GRID * scale, y), (x + c * GRID * scale, y + big.get_height()))
        for r_ in range(sheet.get_height() // GRID + 1):
            pygame.draw.line(self.screen, (30, 18, 20), (x, y + r_ * GRID * scale), (x + big.get_width(), y + r_ * GRID * scale))
        cur = overrides.get(self.slot_sel)
        if cur and cur[0] == src_name:
            pygame.draw.rect(self.screen, ACCENT, pygame.Rect(x + cur[1] * GRID * scale, y + cur[2] * GRID * scale, GRID * scale, GRID * scale), 2)
        self.hot.append((sheet_rect, (lambda r=sheet_rect, sc=scale, n=src_name: self.pick_source_tile(item, r, sc, n)), self.screen.get_clip()))
        y += big.get_height() + 6
        self.btn((x, y, 100, 22), "Reset slot", lambda: self.reset_slot(item, self.slot_sel), enabled=self.slot_sel in overrides)
        self.btn((x + 106, y, 100, 22), "Reset all", lambda: self.reset_slot(item, None), enabled=bool(overrides))
        y += 36

        # type-specific settings
        if kind in (S.MOVING_HORIZONTAL, S.MOVING_VERTICAL):
            a, b = ("min_x", "max_x") if kind == S.MOVING_HORIZONTAL else ("min_y", "max_y")
            y = self.row_fields(y, x, width, [
                (f"{gid}.speed", "Speed (px/s)", lambda: opts.get("speed", 80), lambda v: self.set_opt(opts, "speed", max(0, to_int(v, 80))), True),
                (f"{gid}.{a}", "Travel from (px)", lambda: opts.get(a, 0), lambda v: self.set_opt(opts, a, to_int(v, 0)), True),
                (f"{gid}.{b}", "to (px)", lambda: opts.get(b, 0), lambda v: self.set_opt(opts, b, to_int(v, 0)), True)])
            self.btn((x, y - 8, width, 22), "Start direction: " + ("forward" if opts.get("direction", 1) > 0 else "backward"), lambda: self.edit(lambda: opts.update(direction=-opts.get("direction", 1))))
            y += 28
            self.label("(drag the outlined end positions on the canvas too)", (x, y - 4), MUTED)
            y += 14
        elif kind in (S.CRUMBLE_RESET, S.CRUMBLE_PERSISTENT):
            y = self.row_fields(y, x, width, [
                (f"{gid}.break", "Break after (s)", lambda: opts.get("break_after", 3.0), lambda v: self.set_opt(opts, "break_after", max(0.1, to_float(v, 3.0))), True),
                (f"{gid}.respawn", "Respawn after (s)", lambda: opts.get("respawn_after", 1.5), lambda v: self.set_opt(opts, "respawn_after", max(0.1, to_float(v, 1.5))), True)])
        elif kind == S.DAMAGE:
            y = self.row_fields(y, x, width, [(f"{gid}.dmg", "Damage", lambda: opts.get("damage", S.DAMAGE_PLATFORM_DAMAGE), lambda v: self.set_opt(opts, "damage", max(0, to_int(v, 20))), True)])
        elif kind == S.TRANSITION:
            self.field(f"{gid}.target", (x, y + 14, width - 66, 24), "Target level (file name in levels/)", lambda: opts.get("target", ""), lambda v: self.set_opt(opts, "target", v.strip()), False)
            self.btn((x + width - 60, y + 14, 60, 24), "Pick...", self.pick_target_level)
            y += 50
            sp = opts.get("spawn")
            y = self.row_fields(y, x, width, [
                (f"{gid}.spx", "Spawn X (blank = start)", lambda: int(sp[0]) if sp else "", lambda v: self.set_spawn(opts, 0, v), True),
                (f"{gid}.spy", "Spawn Y", lambda: int(sp[1]) if sp else "", lambda v: self.set_spawn(opts, 1, v), True)])
        elif group == "slope":
            self.btn((x, y, width, 24), "Flip direction  (F)   now: " + item["direction"].replace("_", " "), self.flip_slope)
            y += 34
        self.btn((x, y, width // 2 - 3, 26), "Duplicate  (Ctrl+D)", self.duplicate_selected)
        self.btn((x + width // 2 + 3, y, width // 2 - 3, 26), "Delete  (Del)", self.delete_selected)
        return y + 34

    def inspect_prop(self, item, x, y, width):
        y = self.header("Prop", x, y, width)
        self.btn((x, y, 26, 24), "<", lambda: self.cycle_prop(item, -1))
        self.btn((x + width - 26, y, 26, 24), ">", lambda: self.cycle_prop(item, 1))
        self.label(item["name"], (x + 34, y + 5), TEXT, self.font)
        y += 34
        gid = f"prop{self.selected[1]}"
        y = self.row_fields(y, x, width, [
            (f"{gid}.x", "X (px)", lambda: item["x"], lambda v: self.edit(lambda: item.update(x=self.snapv(to_int(v, item["x"])))), True),
            (f"{gid}.y", "Y (px)", lambda: item["y"], lambda v: self.edit(lambda: item.update(y=self.snapv(to_int(v, item["y"])))), True)])
        layer = item["options"].get("layer", "back")
        self.btn((x, y - 6, width, 24), f"Draws: {layer}  ({'behind' if layer != 'front' else 'in front of'} the player)", lambda: self.edit(lambda: item["options"].update(layer="front" if layer != "front" else "back")))
        y += 30
        self.btn((x, y, width // 2 - 3, 26), "Duplicate", self.duplicate_selected)
        self.btn((x + width // 2 + 3, y, width // 2 - 3, 26), "Delete", self.delete_selected)
        return y + 34

    def inspect_start(self, x, y, width):
        y = self.header("Player start", x, y, width)
        lv = self.level
        return self.row_fields(y, x, width, [
            ("start.x", "X (px)", lambda: lv.start[0], lambda v: self.edit(lambda: lv.start.__setitem__(0, self.snapv(to_int(v, lv.start[0])))), True),
            ("start.y", "Y (px)", lambda: lv.start[1], lambda v: self.edit(lambda: lv.start.__setitem__(1, self.snapv(to_int(v, lv.start[1])))), True)])

    def inspect_level(self, x, y, width):
        lv = self.level
        y = self.header("Level", x, y, width)
        self.field("lv.name", (x, y + 14, width, 24), "Title", lambda: lv.name, lambda v: self.edit(lambda: setattr(lv, "name", v or lv.name)), False)
        y += 50
        self.field("lv.width", (x, y + 14, width // 2 - 4, 24), "Width (px)", lambda: lv.width,
                   lambda v: self.edit(lambda: setattr(lv, "width", max(960, LD.snap(to_int(v, lv.width))))), True)
        self.label(f"{lv.width // GRID} tiles", (x + width // 2 + 8, y + 19), MUTED)
        y += 50
        self.label("BACKGROUND", (x, y), ACCENT_DIM)
        y += 16
        names = assets.list_backgrounds()
        self.btn((x, y, 26, 24), "<", lambda: self.cycle_background(-1))
        self.btn((x + width - 92, y, 26, 24), ">", lambda: self.cycle_background(1))
        self.btn((x + width - 62, y, 62, 24), "Import", self.import_background)
        self.label(lv.background, (x + 34, y + 5), TEXT, self.font)
        y += 34
        self.btn((x, y, width, 22), "Select player start marker", lambda: setattr(self, "selected", ("start", 0)))
        return y + 30

    # ----------------------------------------------------------------- inspector actions
    def set_geom(self, item, key, text):
        old = item[key]
        v = to_int(text, old)
        if key in ("x", "y"):
            v = self.snapv(v)
            if v != old:
                self.checkpoint()
                LD.translate_item(item, v - old if key == "x" else 0, v - old if key == "y" else 0)
        else:
            v = max(GRID, self.snapv(v))
            if v != old:
                self.checkpoint()
                item[key] = v

    def set_opt(self, opts, key, value):
        if opts.get(key) != value:
            self.checkpoint()
            opts[key] = value

    def set_spawn(self, opts, idx, text):
        self.checkpoint()
        cur = list(opts.get("spawn") or [None, None])
        cur[idx] = to_int(text, 0) if str(text).strip() != "" else None
        if cur[0] is None and cur[1] is None:
            opts.pop("spawn", None)
        else:
            opts["spawn"] = (cur[0] or 0, cur[1] or 0)

    def cycle_skin(self, item, d):
        names = assets.list_skins()
        if not names:
            return
        cur = item["options"].get("skin") or S.DEFAULT_SKINS[item["kind"]]
        i = names.index(cur) if cur in names else 0
        self.checkpoint()
        item["options"]["skin"] = names[(i + d) % len(names)]
        item["options"].pop("tiles", None)
        self.source_skin = None

    def cycle_source(self, d):
        names = assets.list_skins()
        item = self.selected_item()
        if not names or item is None:
            return
        cur = self.source_skin or item["options"].get("skin") or S.DEFAULT_SKINS[item["kind"]]
        self.source_skin = names[((names.index(cur) if cur in names else 0) + d) % len(names)]

    def pick_source_tile(self, item, rect, scale, name):
        px, py = getattr(self, "last_click", (0, 0))
        col, row = int((px - rect.x) // (GRID * scale)), int((py - rect.y) // (GRID * scale))
        self.checkpoint()
        item["options"].setdefault("tiles", {})[self.slot_sel] = (name, col, row)

    def reset_slot(self, item, slot):
        self.checkpoint()
        tiles = item["options"].get("tiles", {})
        if slot is None:
            item["options"].pop("tiles", None)
        else:
            tiles.pop(slot, None)
            if not tiles:
                item["options"].pop("tiles", None)

    def cycle_prop(self, item, d):
        names = assets.list_props()
        if names and item["name"] in names:
            self.checkpoint()
            item["name"] = names[(names.index(item["name"]) + d) % len(names)]

    def cycle_background(self, d):
        names = assets.list_backgrounds()
        if names:
            cur = self.level.background
            self.checkpoint()
            self.level.background = names[((names.index(cur) if cur in names else 0) + d) % len(names)]
            self._bg_cache = None

    def pick_target_level(self):
        item = self.selected_item()
        items = [(n, n) for n in LD.available_levels()]

        def done(v):
            self.set_opt(item["options"], "target", v)
        self.modal = Modal("Portal target", "Pick the level this transition box leads to:", items=items, on_result=done, buttons=("Cancel",))

    def flip_slope(self):
        item = self.selected_item()
        if item is not None and self.selected[0] == "slope":
            self.checkpoint()
            item["direction"] = "up_left" if item["direction"] == "up_right" else "up_right"

    # ------------------------------------------------------------------------- importing
    def ask_png(self, callback):
        try:
            import tkinter
            from tkinter import filedialog
            root = tkinter.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            path = filedialog.askopenfilename(title="Choose a PNG", filetypes=[("PNG images", "*.png"), ("All files", "*.*")])
            root.destroy()
            callback(path or None)
        except Exception:
            self.modal = Modal("Import PNG", "No file dialog available - type the path of the PNG:",
                               [("Path", "path", "", False)], on_result=lambda v: callback(v["path"].strip().strip('"') or None))

    def import_png(self, kind):
        def got(path):
            if not path or not os.path.isfile(path):
                if path:
                    self.set_status("File not found: " + path)
                return
            try:
                name = assets.import_png(path, kind, tile=self.import_tile)
            except Exception as exc:
                self.set_status(f"Import failed: {exc}")
                return
            self.caps.clear()
            if kind == "skins":
                item = self.selected_item()
                if item is not None and self.selected[0] in ("platform", "slope"):
                    self.checkpoint()
                    item["options"]["skin"] = name
                    item["options"].pop("tiles", None)
                self.source_skin = None
            elif kind == "tilesets":
                self.tileset_name, self.brush, self.brush_sel = name, [], None
            elif kind == "props":
                self.tool = ("prop", name)
            self.set_status(f"Imported {name} ({self.import_tile}px art) into assets/{kind}/")
        self.ask_png(got)

    def import_background(self):
        def got(path):
            if not path or not os.path.isfile(path):
                return
            try:
                name = assets.import_background(path)
            except Exception as exc:
                self.set_status(f"Import failed: {exc}")
                return
            self.checkpoint()
            self.level.background = name
            self._bg_cache = None
            self.set_status(f"Imported background '{name}' (edit assets/backgrounds/{name}/background.json for parallax)")
        self.ask_png(got)

    # ================================================================ object actions
    def delete_selected(self):
        if not self.selected or self.selected[0] == "start":
            return
        group, idx = self.selected
        items = self.item_list(group)
        if 0 <= idx < len(items):
            self.checkpoint()
            items.pop(idx)
        self.selected = None

    def duplicate_selected(self):
        item = self.selected_item()
        if item is None:
            return
        import copy
        self.checkpoint()
        clone = copy.deepcopy(item)
        LD.translate_item(clone, GRID, GRID)
        items = self.item_list(self.selected[0])
        items.append(clone)
        self.selected = (self.selected[0], len(items) - 1)

    def nudge(self, dx, dy):
        if self.selected == ("start", 0):
            self.checkpoint()
            self.level.start[0] += dx
            self.level.start[1] += dy
            return
        item = self.selected_item()
        if item is not None:
            self.checkpoint()
            LD.translate_item(item, dx, dy)

    # ================================================================== tile painting
    def cell_at(self, wx, wy):
        return int(math.floor(wx / GRID)), int(math.floor(wy / GRID))

    def active_tile_layer(self):
        return self.level.layers[self.active_layer] if isinstance(self.active_layer, int) and self.active_layer < len(self.level.layers) else None

    def paint_at(self, tx, ty, erase=False):
        layer = self.active_tile_layer()
        if layer is None:
            return
        max_tx, max_ty = self.level.width // GRID, self.level.height // GRID
        if erase:
            layer["tiles"].pop((tx, ty), None)
            return
        if not self.brush or not self.tileset_name:
            self.set_status("Pick a tile in the tileset picker first")
            return
        for dx, dy, col, row in self.brush:
            x, y = tx + dx, ty + dy
            if 0 <= x < max_tx and 0 <= y < max_ty:
                layer["tiles"][(x, y)] = (self.tileset_name, col, row)

    def fill_rect(self, x0, y0, x1, y1, erase=False):
        layer = self.active_tile_layer()
        if layer is None:
            return
        ax, bx, ay, by = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)
        max_tx, max_ty = self.level.width // GRID, self.level.height // GRID
        sw = max((b[0] for b in self.brush), default=0) + 1
        sh = max((b[1] for b in self.brush), default=0) + 1
        lookup = {(b[0], b[1]): b for b in self.brush}
        for ty in range(ay, by + 1):
            for tx in range(ax, bx + 1):
                if not (0 <= tx < max_tx and 0 <= ty < max_ty):
                    continue
                if erase:
                    layer["tiles"].pop((tx, ty), None)
                elif self.brush and self.tileset_name:
                    b = lookup.get(((tx - ax) % sw, (ty - ay) % sh))
                    if b:
                        layer["tiles"][(tx, ty)] = (self.tileset_name, b[2], b[3])

    # ================================================================ canvas mouse
    def hit_handle(self, pos):
        for name, r in self.selection_handles():
            if r.inflate(4, 4).collidepoint(pos):
                return name
        return None

    def travel_ghosts(self):
        item = self.selected_item()
        if item is None or self.selected[0] != "platform" or item["kind"] not in (S.MOVING_HORIZONTAL, S.MOVING_VERTICAL):
            return []
        o = item["options"]
        if item["kind"] == S.MOVING_HORIZONTAL:
            return [("min", (o.get("min_x", item["x"]), item["y"])), ("max", (o.get("max_x", item["x"]), item["y"]))]
        return [("min", (item["x"], o.get("min_y", item["y"]))), ("max", (item["x"], o.get("max_y", item["y"])))]

    def canvas_down(self, pos, button):
        wx, wy = self.to_world(*pos)
        mods = pygame.key.get_mods()
        if button == 2 or (button == 1 and self.space_down):
            self.drag = {"mode": "pan", "start": pos, "cam": list(self.cam)}
            return
        if self.active_layer != "objects":
            layer = self.active_tile_layer()
            if layer is None:
                return
            cell = self.cell_at(wx, wy)
            if button == 1 and mods & pygame.KMOD_ALT:                       # eyedropper
                t = layer["tiles"].get(cell)
                if t:
                    self.tileset_name = t[0]
                    self.brush, self.brush_sel = [(0, 0, t[1], t[2])], (t[1], t[2], t[1], t[2])
                return
            erase = button == 3
            self.checkpoint()
            if mods & pygame.KMOD_SHIFT:
                self.drag = {"mode": "rect", "cells": (cell[0], cell[1], cell[0], cell[1]), "erase": erase}
            else:
                self.drag = {"mode": "paint", "erase": erase, "last": cell}
                self.paint_at(cell[0], cell[1], erase)
            return
        if button == 3:                                                    # right click deletes
            hit = self.hit_item(wx, wy)
            if hit:
                self.selected = hit
                self.delete_selected()
            return
        if button != 1:
            return
        # 1. resize handles
        handle = self.hit_handle(pos)
        if handle:
            item = self.selected_item()
            self.drag = {"mode": "resize", "handle": handle, "orig": (item["x"], item["y"], item["w"], item["h"]), "moved": False}
            return
        # 2. moving-platform travel ends
        item = self.selected_item()
        for which, (gx, gy) in self.travel_ghosts():
            r = self.world_rect_to_screen(gx, gy, item["w"], item["h"])
            if r.collidepoint(pos) and not self.world_rect_to_screen(item["x"], item["y"], item["w"], item["h"]).collidepoint(pos):
                self.drag = {"mode": "travel", "which": which, "moved": False}
                return
        # 3. placement tools
        if self.tool[0] != "select":
            self.place_tool(wx, wy)
            return
        # 4. pick / move
        hit = self.hit_item(wx, wy)
        if hit:
            self.selected = hit
            it = self.selected_item()
            self.drag = {"mode": "move", "start": (wx, wy), "orig": (it["x"], it["y"]), "moved": False}
            return
        sx, sy = self.to_screen(*self.level.start)
        if pygame.Rect(round(sx), round(sy), round(32 * self.zoom), round(48 * self.zoom)).collidepoint(pos):
            self.selected = ("start", 0)
            self.drag = {"mode": "start", "start": (wx, wy), "orig": tuple(self.level.start), "moved": False}
            return
        self.selected = None

    def place_tool(self, wx, wy):
        kind_tool, value = self.tool[0], self.tool[1] if len(self.tool) > 1 else None
        x, y = max(0, self.snapv(wx)), max(0, self.snapv(wy))
        keep = pygame.key.get_mods() & pygame.KMOD_SHIFT
        self.checkpoint()
        if kind_tool == "prop":
            self.level.props.append({"name": value, "x": x, "y": y, "options": {}})
            self.selected = ("prop", len(self.level.props) - 1)
        elif kind_tool == "slope":
            self.level.slopes.append(LD.make_slope(value, x, y, GRID * 2, GRID))
            self.selected = ("slope", len(self.level.slopes) - 1)
            self.drag = {"mode": "resize", "handle": "se", "orig": (x, y, GRID * 2, GRID), "moved": False, "placed": True}
        else:
            self.level.platforms.append(LD.make_platform(value, x, y, GRID, GRID))
            self.selected = ("platform", len(self.level.platforms) - 1)
            self.drag = {"mode": "resize", "handle": "se", "orig": (x, y, GRID, GRID), "moved": False, "placed": True}
        if not keep:
            self.tool = ("select",)

    def canvas_motion(self, pos):
        d = self.drag
        if d is None:
            return
        wx, wy = self.to_world(*pos)
        mode = d["mode"]
        if mode == "pan":
            self.cam[0] = d["cam"][0] - (pos[0] - d["start"][0]) / self.zoom
            self.cam[1] = d["cam"][1] - (pos[1] - d["start"][1]) / self.zoom
            self._bg_cache = None
        elif mode == "paint":
            cell = self.cell_at(wx, wy)
            if cell != d["last"]:
                self.paint_at(cell[0], cell[1], d["erase"])
                d["last"] = cell
        elif mode == "rect":
            cx, cy = self.cell_at(wx, wy)
            d["cells"] = (d["cells"][0], d["cells"][1], cx, cy)
        elif mode == "resize":
            item = self.selected_item()
            if item is None:
                return
            grid = GRID if self.grid_on else 1
            nx, ny, nw, nh = LD.resize_rect(d["orig"], d["handle"], wx, wy, grid, GRID if self.grid_on else 4, GRID if self.grid_on else 4)
            if (nx, ny, nw, nh) != (item["x"], item["y"], item["w"], item["h"]):
                if not d["moved"] and not d.get("placed"):
                    self.checkpoint()
                d["moved"] = True
                item["x"], item["y"], item["w"], item["h"] = nx, ny, nw, nh
        elif mode == "move":
            item = self.selected_item()
            if item is None:
                return
            nx = self.snapv(d["orig"][0] + wx - d["start"][0])
            ny = self.snapv(d["orig"][1] + wy - d["start"][1])
            dx, dy = nx - item["x"], ny - item["y"]
            if dx or dy:
                if not d["moved"]:
                    self.checkpoint()
                d["moved"] = True
                LD.translate_item(item, dx, dy)
        elif mode == "start":
            nx = self.snapv(d["orig"][0] + wx - d["start"][0])
            ny = self.snapv(d["orig"][1] + wy - d["start"][1])
            if [nx, ny] != self.level.start:
                if not d["moved"]:
                    self.checkpoint()
                d["moved"] = True
                self.level.start[:] = [nx, ny]
        elif mode == "travel":
            item = self.selected_item()
            if item is None:
                return
            o = item["options"]
            horizontal = item["kind"] == S.MOVING_HORIZONTAL
            key = ("min_x" if d["which"] == "min" else "max_x") if horizontal else ("min_y" if d["which"] == "min" else "max_y")
            v = self.snapv((wx - item["w"] / 2) if horizontal else (wy - item["h"] / 2))
            if o.get(key) != v:
                if not d["moved"]:
                    self.checkpoint()
                d["moved"] = True
                o[key] = v
                lo, hi = ("min_x", "max_x") if horizontal else ("min_y", "max_y")
                if o.get(lo, 0) > o.get(hi, 0):
                    o[lo], o[hi] = o[hi], o[lo]
                    d["which"] = "max" if d["which"] == "min" else "min"

    def canvas_up(self, pos, button):
        d = self.drag
        if d is None:
            return
        if d["mode"] == "rect":
            x0, y0, x1, y1 = d["cells"]
            self.fill_rect(x0, y0, x1, y1, d["erase"])
        elif d["mode"] == "resize" and d.get("placed"):
            item = self.selected_item()
            if item is not None and (item["w"], item["h"]) == d["orig"][2:]:     # a plain click: use the default size
                if self.selected[0] == "slope":
                    item["w"], item["h"] = 128, 64
                else:
                    item["w"], item["h"] = LD.DEFAULT_SIZES.get(item["kind"], (96, 32))
                if item["kind"] == S.TRANSITION or item["kind"] == S.KILL or item["kind"] == S.DAMAGE:
                    pass
        self.drag = None

    # ===================================================================== modals
    def draw_modal(self):
        m = self.modal
        w, h = self.screen.get_size()
        self.overlay(pygame.Rect(0, 0, w, h), (0, 0, 0, 170))
        mw = m.width
        list_h = min(260, 28 * len(m.items) + 8) if m.items else 0
        mh = 46 + (22 if m.message else 0) + 54 * len(m.fields) + list_h + 52
        r = pygame.Rect((w - mw) // 2, (h - mh) // 2, mw, mh)
        pygame.draw.rect(self.screen, PANEL, r, border_radius=6)
        pygame.draw.rect(self.screen, ACCENT_DIM, r, 2, border_radius=6)
        self.label(m.title, (r.x + 16, r.y + 12), TEXT, self.big)
        y = r.y + 44
        m.hot = []
        if m.message:
            self.label(m.message, (r.x + 16, y), MUTED)
            y += 22
        for i, (label, key, f, _) in enumerate(m.fields):
            fr = pygame.Rect(r.x + 16, y + 16, mw - 32, 26)
            self.label(label, (fr.x, fr.y - 15))
            pygame.draw.rect(self.screen, (10, 6, 8), fr, border_radius=3)
            pygame.draw.rect(self.screen, ACCENT if f.focused else BORDER, fr, 1, border_radius=3)
            self.screen.blit(self.font.render(f.value + ("|" if f.focused and int(self.time * 2) % 2 == 0 else ""), True, TEXT), (fr.x + 6, fr.y + 5))
            m.hot.append((fr, ("field", i)))
            y += 54
        if m.items:
            lr = pygame.Rect(r.x + 16, y, mw - 32, list_h)
            pygame.draw.rect(self.screen, (10, 6, 8), lr)
            self.screen.set_clip(lr)
            yy = lr.y + 4 - m.scroll
            for label, value in m.items:
                ir = pygame.Rect(lr.x + 4, yy, lr.w - 8, 24)
                hover = ir.collidepoint(pygame.mouse.get_pos())
                pygame.draw.rect(self.screen, (52, 22, 24) if hover else PANEL2, ir, border_radius=3)
                self.label(label, (ir.x + 8, ir.y + 5), TEXT)
                m.hot.append((ir.clip(lr), ("item", value)))
                yy += 28
            self.screen.set_clip(None)
            y += list_h + 8
        bx = r.right - 16
        for label in reversed(m.buttons):
            bw = 90
            br = pygame.Rect(bx - bw, r.bottom - 44, bw, 30)
            first = label == m.buttons[0] and len(m.buttons) > 1 or (len(m.buttons) == 1 and not m.items)
            self.btn_modal(br, label, first)
            m.hot.append((br, ("button", label)))
            bx -= bw + 8

    def btn_modal(self, rect, label, primary):
        pygame.draw.rect(self.screen, (80, 14, 16) if primary else PANEL2, rect, border_radius=4)
        pygame.draw.rect(self.screen, ACCENT if primary else BORDER, rect, 1, border_radius=4)
        s = self.font.render(label, True, TEXT)
        self.screen.blit(s, s.get_rect(center=rect.center))

    def modal_values(self):
        return {key: f.value for _, key, f, _ in self.modal.fields}

    def modal_finish(self, accepted, item_value=None):
        m, self.modal = self.modal, None
        if not accepted or m.on_result is None:
            return
        if m.items:
            m.on_result(item_value)
        elif m.fields:
            m.on_result({key: f.value for _, key, f, _ in m.fields})
        else:
            m.on_result(None)

    def modal_event(self, e):
        m = self.modal
        if e.type == pygame.MOUSEWHEEL:
            m.scroll = max(0, m.scroll - e.y * 30)
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for rect, (kind, value) in m.hot:
                if rect.collidepoint(e.pos):
                    if kind == "field":
                        for i, (_, _, f, _) in enumerate(m.fields):
                            f.focused = i == value
                    elif kind == "item":
                        self.modal_finish(True, value)
                    elif kind == "button":
                        self.modal_finish(value == m.buttons[0] and not (len(m.buttons) == 1 and m.items), None)
                    return
        elif e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                self.modal_finish(False)
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if not m.items:
                    self.modal_finish(True)
            elif e.key == pygame.K_TAB and m.fields:
                cur = next((i for i, (_, _, f, _) in enumerate(m.fields) if f.focused), 0)
                for i, (_, _, f, _) in enumerate(m.fields):
                    f.focused = i == (cur + 1) % len(m.fields)
            else:
                for _, _, f, _ in m.fields:
                    if f.focused:
                        if e.key == pygame.K_BACKSPACE:
                            f.value = f.value[:-1]
                        elif e.unicode and e.unicode.isprintable():
                            ok = (e.unicode.isdigit() or e.unicode in ".-") if f.numeric else True
                            if ok:
                                f.value += e.unicode

    # ================================================================ main events
    def handle_event(self, e):
        if e.type == pygame.QUIT:
            self.confirm_discard(lambda: setattr(self, "running", False))
            return
        if e.type == pygame.VIDEORESIZE:
            self.screen = pygame.display.set_mode(e.size, pygame.RESIZABLE)
            self._bg_cache = None
            return
        if self.modal is not None:
            self.modal_event(e)
            return
        if e.type == pygame.MOUSEWHEEL:
            self.wheel(e)
        elif e.type == pygame.MOUSEBUTTONDOWN:
            self.mouse_down(e.pos, e.button)
        elif e.type == pygame.MOUSEBUTTONUP:
            self.canvas_up(e.pos, e.button)
            if getattr(self, "picker_drag", None):
                self.picker_drag = None
        elif e.type == pygame.MOUSEMOTION:
            self.mouse_motion(e.pos)
        elif e.type == pygame.KEYUP:
            if e.key == pygame.K_SPACE:
                self.space_down = False
        elif e.type == pygame.KEYDOWN:
            self.key_down(e)

    def wheel(self, e):
        pos = pygame.mouse.get_pos()
        w, h = self.screen.get_size()
        if self.canvas_rect().collidepoint(pos):
            if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                self.cam[0] -= e.y * 80 / self.zoom
                self._bg_cache = None
            else:
                self.zoom_by(1 if e.y > 0 else -1, pos)
        elif pos[0] < LEFT_W:
            if self.active_layer == "objects":
                self.palette_scroll = clamp(self.palette_scroll - e.y * 40, 0, max(0, getattr(self, "content_h", 0) - 300))
            else:
                self.picker_scroll = max(0, self.picker_scroll - e.y * 40)
        elif pos[0] > w - RIGHT_W:
            self.right_scroll = clamp(self.right_scroll - e.y * 40, 0, max(0, getattr(self, "right_content", 0) - (h - TOP_H - BOTTOM_H) + 20))

    right_scroll = 0

    def mouse_down(self, pos, button):
        self.last_click = pos
        if button != 1 and not self.canvas_rect().collidepoint(pos):
            return
        # text fields get the click first
        for rect, key in self.field_hot:
            if rect.collidepoint(pos) and (self.right_panel.collidepoint(pos) if hasattr(self, "right_panel") else True):
                for k in list(self.fields):
                    if k != key:
                        self.commit_field(k)
                self.fields[key].focused = True
                return
        self.blur_fields()
        for rect, cb, clip in reversed(self.hot):
            if rect.collidepoint(pos) and (clip is None or clip.collidepoint(pos)):
                cb()
                return
        if self.active_layer != "objects" and hasattr(self, "picker_rect") and self.picker_rect.collidepoint(pos) and pos[0] < LEFT_W:
            cell = self.picker_cell(pos)
            if cell:
                self.picker_drag = cell
                self.brush_sel = (cell[0], cell[1], cell[0], cell[1])
                self.set_brush_from_selection()
            return
        if self.canvas_rect().collidepoint(pos):
            self.canvas_down(pos, button)

    def mouse_motion(self, pos):
        if getattr(self, "picker_drag", None):
            cell = self.picker_cell(pos)
            if cell:
                c0, r0 = self.picker_drag
                self.brush_sel = (c0, r0, cell[0], cell[1])
                self.set_brush_from_selection()
        self.canvas_motion(pos)
        self.hover_handle = None
        if self.drag is None and self.canvas_rect().collidepoint(pos) and self.modal is None and self.active_layer == "objects":
            self.hover_handle = self.hit_handle(pos)
        self.set_cursor(self.hover_handle or (self.drag or {}).get("handle"))

    def set_cursor(self, handle):
        name = HANDLE_CURSORS.get(handle) if handle else None
        if name != self.cursor_name:
            self.cursor_name = name
            try:
                pygame.mouse.set_cursor(getattr(pygame, "SYSTEM_CURSOR_" + (name or "ARROW")))
            except Exception:
                pass

    def key_down(self, e):
        focused = next((k for k, f in self.fields.items() if f.focused), None)
        if focused is not None:
            f = self.fields[focused]
            if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_TAB):
                self.commit_field(focused)
            elif e.key == pygame.K_ESCAPE:
                f.focused = False
            elif e.key == pygame.K_BACKSPACE:
                f.value = f.value[:-1]
            elif e.unicode and e.unicode.isprintable():
                ok = (e.unicode.isdigit() or e.unicode in ".-") if f.numeric else (e.unicode.isalnum() or e.unicode in "_- .>")
                if ok:
                    f.value += e.unicode
            return
        mods = pygame.key.get_mods()
        ctrl = mods & pygame.KMOD_CTRL
        if ctrl and e.key == pygame.K_s:
            self.save()
        elif ctrl and e.key == pygame.K_o:
            self.action_open()
        elif ctrl and e.key == pygame.K_n:
            self.action_new()
        elif ctrl and e.key == pygame.K_z:
            self.undo()
        elif ctrl and e.key == pygame.K_y:
            self.redo()
        elif ctrl and e.key == pygame.K_d:
            self.duplicate_selected()
        elif e.key == pygame.K_SPACE:
            self.space_down = True
        elif e.key == pygame.K_g:
            self.toggle_grid()
        elif e.key == pygame.K_f:
            self.flip_slope()
        elif e.key == pygame.K_DELETE:
            self.delete_selected()
        elif e.key == pygame.K_ESCAPE:
            self.tool = ("select",)
            self.selected = None
        elif e.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN) and self.selected:
            step = GRID if self.grid_on else 1
            self.nudge({pygame.K_LEFT: -step, pygame.K_RIGHT: step}.get(e.key, 0), {pygame.K_UP: -step, pygame.K_DOWN: step}.get(e.key, 0))

    # ===================================================================== frame
    def draw(self):
        w, h = self.screen.get_size()
        self.screen.fill(BG)
        self.hot, self.field_hot = [], []
        self.draw_canvas()
        self.draw_left()
        self.draw_right()
        self.draw_top()
        pygame.draw.rect(self.screen, PANEL, (0, h - BOTTOM_H, w, BOTTOM_H))
        pygame.draw.line(self.screen, BORDER, (0, h - BOTTOM_H), (w, h - BOTTOM_H))
        mx, my = pygame.mouse.get_pos()
        info = ""
        if self.canvas_rect().collidepoint(mx, my):
            wx, wy = self.to_world(mx, my)
            info = f"x {int(wx)}  y {int(wy)}   tile {int(wx // GRID)}, {int(wy // GRID)}"
        msg = self.status if self.status_time > 0 else "Ctrl+S save - Ctrl+Z undo - drag object edges to resize - wheel zooms - middle-drag pans"
        self.label(msg, (10, h - BOTTOM_H + 6), GOOD if "Saved" in msg else MUTED)
        self.label(info, (w - RIGHT_W - 220, h - BOTTOM_H + 6), TEXT)
        if self.modal is not None:
            self.draw_modal()
        pygame.display.flip()

    def run(self):
        while self.running:
            dt = self.clock.tick(60) / 1000.0
            self.time += dt
            self.status_time = max(0.0, self.status_time - dt)
            for event in pygame.event.get():
                self.handle_event(event)
            self.draw()
        pygame.quit()


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else None
    LevelEditor(path).run()


if __name__ == "__main__":
    main()
