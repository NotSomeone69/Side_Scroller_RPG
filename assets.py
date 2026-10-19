"""Asset loading and caching. Everything visual lives as PNG (+ optional JSON) in assets/."""
import json
import os
import shutil
import pygame

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
_images = {}


def path(*parts):
    return os.path.join(ROOT, *parts)


def load_json(file, default=None):
    try:
        with open(file, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def save_json(file, data):
    os.makedirs(os.path.dirname(file), exist_ok=True)
    with open(file, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1)


def load_image(file, cache=True):
    """Load a PNG as a per-pixel-alpha surface (cached by absolute path)."""
    file = os.path.abspath(file)
    surf = _images.get(file) if cache else None
    if surf is None:
        surf = pygame.image.load(file)
        surf = surf.convert_alpha() if pygame.display.get_surface() is not None else surf
        if cache:
            _images[file] = surf
    return surf


def forget(file=None):
    """Drop cached images (used by the editor after a PNG was edited/imported)."""
    if file is None:
        _images.clear()
    else:
        _images.pop(os.path.abspath(file), None)


def list_names(folder, ext=".png"):
    d = path(folder)
    if not os.path.isdir(d):
        return []
    return sorted(f[:-len(ext)] for f in os.listdir(d) if f.lower().endswith(ext))


def list_skins():
    return list_names("skins")


def list_tilesets():
    return list_names("tilesets")


def list_props():
    return list_names("props")


def list_backgrounds():
    d = path("backgrounds")
    if not os.path.isdir(d):
        return []
    return sorted(n for n in os.listdir(d) if os.path.isfile(os.path.join(d, n, "background.json")))


def unique_name(folder, name, ext=".png"):
    base, i = name, 2
    while os.path.exists(path(folder, name + ext)):
        name = f"{base}_{i}"
        i += 1
    return name


def import_png(src, kind, name=None, tile=16, frames=1, fps=6):
    """Copy a user PNG into assets/<kind>/ ('skins' | 'tilesets' | 'props') and write its JSON.

    The world uses 16px tiles. Art drawn on a 32px grid (tile=32) is scaled down 2x (nearest
    neighbour) while importing so it still lines up with the grid. Returns the asset name."""
    name = unique_name(kind, name or os.path.splitext(os.path.basename(src))[0].replace(" ", "_").lower())
    dest = path(kind, name + ".png")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if tile == 32:
        surf = pygame.image.load(src)
        surf = pygame.transform.scale(surf, (max(1, surf.get_width() // 2), max(1, surf.get_height() // 2)))
        pygame.image.save(surf, dest)
    else:
        shutil.copyfile(src, dest)
    img = load_image(dest, cache=False)
    w, h = img.get_size()
    if kind == "skins":
        save_json(path(kind, name + ".json"), {"tile": 16, "frames": frames, "fps": fps, "frame_w": w // max(1, frames)})
    elif kind == "props":
        save_json(path(kind, name + ".json"), {"frames": frames, "fps": fps})
    elif kind == "tilesets":
        save_json(path(kind, name + ".json"), {"tile": 16, "names": {}})
    return name


def import_background(src, name=None, parallax=0.15, tile_x=True, anchor="bottom"):
    """Create a background from one PNG (a single parallax layer over a dark sky)."""
    name = name or os.path.splitext(os.path.basename(src))[0].replace(" ", "_").lower()
    folder, i, base = path("backgrounds", name), 2, name
    while os.path.exists(folder):
        name = f"{base}_{i}"
        folder = path("backgrounds", name)
        i += 1
    os.makedirs(folder)
    shutil.copyfile(src, os.path.join(folder, "layer0.png"))
    save_json(os.path.join(folder, "background.json"), {
        "name": name.replace("_", " ").title(), "sky": [[0, 0, 0], [30, 4, 6]],
        "layers": [{"image": "layer0.png", "parallax": parallax, "anchor": anchor, "tile_x": tile_x}]})
    return name


_icon_sheet = None


def icon(name, scale=2):
    """Small UI icon (16x16 cell of assets/ui/icons.png) scaled by an integer factor."""
    global _icon_sheet
    key = ("icon", name, scale)
    surf = _images.get(key)
    if surf is None:
        if _icon_sheet is None:
            _icon_sheet = (load_image(path("ui", "icons.png")), load_json(path("ui", "icons.json"), {})["icons"])
        sheet, mapping = _icon_sheet
        col, row = mapping[name]
        cell = pygame.Surface((16, 16), pygame.SRCALPHA)
        cell.blit(sheet, (0, 0), pygame.Rect(col * 16, row * 16, 16, 16))
        surf = _images[key] = pygame.transform.scale(cell, (16 * scale, 16 * scale)) if scale != 1 else cell
    return surf
