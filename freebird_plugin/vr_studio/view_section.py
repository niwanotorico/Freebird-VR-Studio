# SPDX-License-Identifier: GPL-2.0-or-later
"""VIEW section: 4 big buttons for the headset's viewport shading (Wireframe / Solid /
Material Preview / Rendered), plus Overlay on / off and Controller Normal / See-through.
Local display settings, never synced (see view.py, controller_look.py)."""

import os

from mathutils import Vector

from . import controller_look, view
from .area import StudioSection, Tile
from .look_section import COLUMNS, GAP, ICON_DIR, LABEL_H, TILE
from .color_section import WIDTH

ENGINE_NAMES = {"BLENDER_EEVEE_NEXT": "EEVEE", "BLENDER_EEVEE": "EEVEE", "CYCLES": "Cycles",
                "BLENDER_WORKBENCH": "Workbench"}


class ViewSection(StudioSection):
    title = "VIEW"
    scope = "LOCAL"
    idle_message = "Just you. Solid is lightest"

    def __init__(self):
        row = TILE + LABEL_H + 0.002
        super().__init__(WIDTH, 2 * row - 0.002)
        self.tiles = []
        # second row: overlays on / off
        icon = os.path.join(ICON_DIR, "view_overlay.png")
        self.overlay_tile = Tile(self, "Overlays: floor, outlines, empties", TILE, None,
                                 src=icon if os.path.exists(icon) else None,
                                 background=None if os.path.exists(icon) else (0.3, 0.3, 0.35), hover_fill=True)
        self.overlay_tile.mode = "OVERLAY"
        self.overlay_tile.position = Vector((0.0, LABEL_H, 0.0))
        self.body.append_child(self.overlay_tile)
        text = self._text("Overlay", (0, 0), 18, (0.85, 0.88, 0.95, 1))
        w = text.bounds_local.size.x * text.scale.x
        text.position = Vector((max(0.0, (TILE - w) / 2), 0.0015, 0.0))
        self.body.append_child(text)
        # second row, next to Overlay: controller card Normal / See-through (controller_look.py)
        x = TILE + GAP
        self.controller_tile = Tile(self, "Controller: Normal / See-through", TILE, None,
                                    background=(0.12, 0.14, 0.2), hover_fill=True)
        self.controller_tile.position = Vector((x, LABEL_H, 0.0))
        self.body.append_child(self.controller_tile)
        self.controller_state = self._text("", (0, 0), 22, (1, 1, 1, 1))
        self.body.append_child(self.controller_state)
        self._show_controller_state(controller_look.get_see_through())
        text = self._text("Controller", (0, 0), 18, (0.85, 0.88, 0.95, 1))
        w = text.bounds_local.size.x * text.scale.x
        text.position = Vector((x + max(0.0, (TILE - w) / 2), 0.0015, 0.0))
        self.body.append_child(text)
        for i, (mode, label, hover) in enumerate(view.MODES):
            x = i * (TILE + GAP)
            icon = os.path.join(ICON_DIR, f"view_{mode.lower()}.png")
            t = Tile(self, hover, TILE, None, src=icon if os.path.exists(icon) else None,
                     background=None if os.path.exists(icon) else (0.3, 0.3, 0.35), hover_fill=True)
            t.mode = mode
            t.position = Vector((x, row + LABEL_H, 0.0))
            self.tiles.append(t)
            self.body.append_child(t)
            heavy = mode in ("MATERIAL", "RENDERED")
            # amber label = heavy in VR (the hover text says so too)
            text = self._text(label, (0, 0), 18, (1.0, 0.72, 0.3, 1) if heavy else (0.85, 0.88, 0.95, 1))
            w = text.bounds_local.size.x * text.scale.x
            text.position = Vector((x + max(0.0, (TILE - w) / 2), row + 0.0015, 0.0))
            self.body.append_child(text)
        assert len(self.tiles) == COLUMNS

    def _show_controller_state(self, see_through):
        self.controller_state.text = "See" if see_through else "Normal"
        w = self.controller_state.bounds_local.size.x * self.controller_state.scale.x
        x = TILE + GAP
        self.controller_state.position = Vector((x + max(0.0, (TILE - w) / 2), LABEL_H + TILE * 0.4, 0.003))
        self.controller_tile.set_current(see_through)

    def press(self, tile):
        if tile is self.controller_tile:
            try:
                on = not controller_look.get_see_through()
                found = controller_look.set_see_through(on)
                self._show_controller_state(on)
                message = "Controller: See-through" if on else "Controller: Normal"
                if not found:
                    message += " (controller not found)"
            except Exception as e:
                message = "Controller look failed (see console)"
                print(f"[vr_studio] controller look: {e}")
            self.finish(message)
            return
        if tile is self.overlay_tile:
            try:
                on = view.toggle_overlays()
                tile.set_current(on)
                message = "Overlays ON" if on else "Overlays OFF"
            except Exception as e:
                message = "Overlays failed (see console)"
                print(f"[vr_studio] overlays: {e}")
            self.finish(message)
            return
        try:
            engine = view.set_vr_shading(tile.mode)
            message = tile.label
            if engine:
                message += f" ({ENGINE_NAMES.get(engine, engine)})"
            for t in self.tiles:
                t.set_current(t is tile)
            print(f"[vr_studio] VR shading -> {tile.mode}")
        except Exception as e:
            import traceback

            message = "View failed (see console)"
            print(f"[vr_studio] VR shading {tile.mode} failed: {e}\n{traceback.format_exc()}")
        self.finish(message)

    def refresh(self, mat):
        try:
            self.overlay_tile.set_current(view.overlays_on())
        except Exception:
            pass
        self._show_controller_state(controller_look.get_see_through())
        mode = view.get_vr_shading()
        for t in self.tiles:
            t.set_current(t.mode == mode)
