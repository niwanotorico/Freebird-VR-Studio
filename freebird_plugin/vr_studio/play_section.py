# SPDX-License-Identifier: GPL-2.0-or-later
"""PUDDING section (Puddinger's "ぷるぷる"): four buttons side by side, Off / Soft / Wobbly / Jelly.
GLOBAL: the pudding level lives on the object; the wobble itself is drawn by each Blender."""

import os

import bpy
from mathutils import Vector

from . import jiggle
from .area import StudioSection, Tile
from .color_section import WIDTH
from .look_section import COLUMNS, GAP, ICON_DIR, LABEL_H, TILE

BUTTONS = (  # level, label, icon, hover
    (0, "Off", "pud_off.png", "Pudding off: back to solid"),
    (1, "Soft", "pud_soft.png", "Soft: a gentle wobble"),
    (2, "Wobbly", "pud_wobbly.png", "Wobbly: bigger, longer wobble"),
    (3, "Jelly", "pud_jelly.png", "Jelly: big, slow, hard to stop"),
)


class PlaySection(StudioSection):
    title = "PUDDING"
    scope = "GLOBAL"
    idle_message = "Pick a pudding, then touch it!"

    def __init__(self):
        row = TILE + LABEL_H + 0.002
        super().__init__(WIDTH, 2 * row - 0.002)
        self.tiles = []
        # second row: a new pudding, right in your hand
        icon = os.path.join(ICON_DIR, "pud_new.png")
        self.new_tile = Tile(self, "New pudding: appears in your hand", TILE, None,
                             src=icon if os.path.exists(icon) else None,
                             background=None if os.path.exists(icon) else (0.95, 0.75, 0.3), hover_fill=True)
        self.new_tile.level = None
        self.new_tile.position = Vector((0.0, LABEL_H, 0.0))
        self.body.append_child(self.new_tile)
        text = self._text("New", (0, 0), 18, (0.85, 0.88, 0.95, 1))
        w = text.bounds_local.size.x * text.scale.x
        text.position = Vector((max(0.0, (TILE - w) / 2), 0.0015, 0.0))
        self.body.append_child(text)
        for i, (lv, label, icon_name, hover) in enumerate(BUTTONS[:COLUMNS]):
            x = i * (TILE + GAP)
            icon = os.path.join(ICON_DIR, icon_name)
            if not os.path.exists(icon):
                icon = os.path.join(ICON_DIR, "play_jiggle.png")
            t = Tile(self, hover, TILE, None, src=icon if os.path.exists(icon) else None,
                     background=None if os.path.exists(icon) else (0.95, 0.75, 0.3), hover_fill=True)
            t.level = lv
            t.position = Vector((x, row + LABEL_H, 0.0))
            self.tiles.append(t)
            self.body.append_child(t)
            text = self._text(label, (0, 0), 18, (0.85, 0.88, 0.95, 1))
            w = text.bounds_local.size.x * text.scale.x
            text.position = Vector((x + max(0.0, (TILE - w) / 2), row + 0.0015, 0.0))
            self.body.append_child(text)

    def _targets(self):
        from . import grab

        held = grab.held_objects()
        if held:
            return held
        vl = bpy.context.view_layer
        return [o for o in vl.objects if o.select_get()]

    def press(self, tile):
        if tile is self.new_tile:
            try:
                from .spawn import new_pudding

                new_pudding(level=2)
                message = "New pudding! Grab it and shake"
            except Exception as e:
                import traceback

                message = "New pudding failed (see console)"
                print(f"[vr_studio] new pudding: {e}\n{traceback.format_exc()}")
            self.refresh(None)
            self.finish(message)
            return
        try:
            message = jiggle.set_level(self._targets(), getattr(tile, "level", 1))
        except Exception as e:
            import traceback

            message = "Pudding failed (see console)"
            print(f"[vr_studio] jiggle: {e}\n{traceback.format_exc()}")
        self.refresh(None)
        self.finish(message)

    def refresh(self, mat):
        try:
            lv = jiggle.common_level(self._targets())
            for t in self.tiles:
                t.set_current(lv is not None and t.level == lv)
        except Exception:
            pass
