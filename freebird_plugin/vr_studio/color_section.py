# SPDX-License-Identifier: GPL-2.0-or-later
"""COLOR section: 32 flat swatches (8 x 4). Press one = colour the selection (Look is kept)."""

import bpy
from mathutils import Vector

from . import brush, materials
from .area import StudioSection, Tile
from .palette import COLUMNS, swatches

SWATCH = 0.018
GAP = 0.004
CELL = SWATCH + GAP
WIDTH = COLUMNS * CELL - GAP + 2 * 0.006  # PAD on both sides: 0.184 m


class ColorSection(StudioSection):
    title = "COLOR"
    scope = "GLOBAL"
    idle_message = "Select, then pick a colour"

    def __init__(self):
        items = swatches()
        rows = (len(items) + COLUMNS - 1) // COLUMNS
        super().__init__(WIDTH, rows * CELL - GAP)
        self.tiles = []
        for i, (name, srgb, lin) in enumerate(items):
            t = Tile(self, name, SWATCH, None, background=srgb)
            t.linear = lin
            row, col = divmod(i, COLUMNS)
            t.position = Vector((col * CELL, (rows - 1 - row) * CELL, 0.0))
            self.tiles.append(t)
            self.body.append_child(t)

    def press(self, tile):
        try:
            brush.set_color(tile.linear, tile.label)  # what you draw next comes out in this colour
            targets = materials.selected_targets(bpy.context)
            report = materials.apply_color(targets, tile.linear)
            if report["objects"]:
                for name in report["objects"]:
                    ob = bpy.data.objects.get(name)
                    if ob is not None:  # Solid shading "Object" colour too (Freebird strokes use it)
                        ob.color = (*tile.linear, 1.0)
                bpy.ops.ed.undo_push(message=f"VR colour {tile.label}")
                for t in self.tiles:
                    t.set_current(t is tile)
            message = materials.describe(report) if report["objects"] else f"Pen: {tile.label}"
            for t in self.tiles:
                t.set_current(t is tile)
            print(f"[vr_studio] colour {tile.label}: {report}")
        except Exception as e:
            import traceback

            message = "Colour failed (see console)"
            print(f"[vr_studio] colour {tile.label} failed: {e}\n{traceback.format_exc()}")
        self.finish(message)

    def refresh(self, mat):
        col = materials.material_color(mat) if mat is not None else brush.state["color"]
        for t in self.tiles:
            t.set_current(col is not None and all(abs(a - b) < 0.004 for a, b in zip(col, t.linear)))
