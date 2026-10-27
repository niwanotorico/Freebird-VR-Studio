# SPDX-License-Identifier: GPL-2.0-or-later
"""LOOK section: 8 material-ball tiles (4 x 2) with names. Press one = give the selection that
Look (its colour is kept). Bottom row: Flat / Smooth shading of the selection (synced to the room)."""

import os

import bpy
from mathutils import Vector

from . import brush, materials, shading
from .area import StudioSection, Tile
from .color_section import WIDTH
from .looks import LOOK_NAMES

COLUMNS = 4
LABEL_H = 0.008
INNER = WIDTH - 2 * 0.006
GAP = 0.006
TILE = (INNER - (COLUMNS - 1) * GAP) / COLUMNS  # ~0.039 m
ROW = TILE + LABEL_H + 0.002
SHADES = [("FLAT", "Flat", "Shade Flat (faceted)", "shade_flat.png"),
          ("SMOOTH", "Smooth", "Shade Smooth", "shade_smooth.png")]
ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")


class LookSection(StudioSection):
    title = "LOOK"
    scope = "GLOBAL"
    idle_message = "Select, then pick a look"

    def __init__(self):
        rows = (len(LOOK_NAMES) + COLUMNS - 1) // COLUMNS
        super().__init__(WIDTH, (rows + 1) * ROW - 0.002)  # + the Flat / Smooth row at the bottom
        self.tiles = []
        self.shade_tiles = []
        for i, (key, label, hover, icon) in enumerate(SHADES):
            x, y = i * (TILE + GAP), LABEL_H
            src = os.path.join(ICON_DIR, icon)
            t = Tile(self, hover, TILE, None, src=src if os.path.exists(src) else None,
                     background=None if os.path.exists(src) else (0.3, 0.3, 0.35), hover_fill=True)
            t.shade = key
            t.position = Vector((x, y, 0.0))
            self.shade_tiles.append(t)
            self.body.append_child(t)
            text = self._text(label, (0, 0), 18, (0.85, 0.88, 0.95, 1))
            w = text.bounds_local.size.x * text.scale.x
            text.position = Vector((x + max(0.0, (TILE - w) / 2), y - LABEL_H + 0.0015, 0.0))
            self.body.append_child(text)
        for i, name in enumerate(LOOK_NAMES):
            row, col = divmod(i, COLUMNS)
            x, y = col * (TILE + GAP), (rows - row) * ROW + LABEL_H
            icon = os.path.join(ICON_DIR, f"look_{name.lower()}.png")
            t = Tile(self, name, TILE, None, src=icon if os.path.exists(icon) else None,
                     background=None if os.path.exists(icon) else (0.3, 0.3, 0.35), hover_fill=True)
            t.look = name
            t.position = Vector((x, y, 0.0))
            self.tiles.append(t)
            self.body.append_child(t)
            label = self._text(name, (0, 0), 18, (0.85, 0.88, 0.95, 1))
            w = label.bounds_local.size.x * label.scale.x
            label.position = Vector((x + max(0.0, (TILE - w) / 2), y - LABEL_H + 0.0015, 0.0))
            self.body.append_child(label)

    def press(self, tile):
        if getattr(tile, "shade", None):
            self._press_shade(tile)
            return
        try:
            brush.set_look(tile.look)  # what you draw next gets this look
            targets = materials.selected_targets(bpy.context)
            report = materials.apply_look(targets, tile.look)
            if report["objects"]:
                bpy.ops.ed.undo_push(message=f"VR look {tile.look}")
                for t in self.tiles:
                    t.set_current(t is tile)
            message = materials.describe(report) if report["objects"] else f"Pen: {tile.look}"
            for t in self.tiles:
                t.set_current(t is tile)
            if report["objects"] and tile.look == "Toon":
                message += " (Material Preview)"
            print(f"[vr_studio] look {tile.look}: {report}")
        except Exception as e:
            import traceback

            message = "Look failed (see console)"
            print(f"[vr_studio] look {tile.look} failed: {e}\n{traceback.format_exc()}")
        self.finish(message)

    def _press_shade(self, tile):
        smooth = tile.shade == "SMOOTH"
        try:
            targets = materials.selected_targets(bpy.context)
            n = shading.set_shading(targets, smooth)
            if n:
                bpy.ops.ed.undo_push(message=f"VR shade {tile.shade.lower()}")
                message = f"{'Smooth' if smooth else 'Flat'}: {n} object{'s' if n != 1 else ''}"
            else:
                message = "Select something to shade"
        except Exception as e:
            import traceback

            message = "Shade failed (see console)"
            print(f"[vr_studio] shade {tile.shade} failed: {e}\n{traceback.format_exc()}")
        self._refresh_shade()
        self.finish(message)

    def _refresh_shade(self):
        try:
            cur = shading.current(materials.selected_targets(bpy.context))
        except Exception:
            cur = None
        for t in self.shade_tiles:
            t.set_current(t.shade == cur)

    def refresh(self, mat):
        look = materials.detect_look(mat) if mat is not None else brush.state["look"]
        for t in self.tiles:
            t.set_current(t.look == look)
        self._refresh_shade()
