# SPDX-License-Identifier: GPL-2.0-or-later
"""PICKER section: any colour, not just the 32 swatches, plus an eyedropper.

    map      hue (left -> right) x lightness (bottom dark -> top light). Pull the trigger on it:
             the colour follows the laser while you hold, and is applied when you let go.
    strip    8 steps from grey to full colour (saturation) of the current hue / lightness.
    Paint    colour the selection with the current colour again.
    Pick     eyedropper: then touch something with the grab sphere (the ball on your hand)
             and its colour becomes the current colour and your pen's.
Like COLOR: applying colours the selection (or what you hold) and your pen; the material change
is synced to the room by the collab material sync (GLOBAL).
"""

import colorsys
import os

import bpy
from bl_xr import Image
from mathutils import Vector

from . import brush, materials
from .area import HOVER_BORDER, StudioSection, Tile, haptic
from .color_section import CELL, GAP as SW_GAP, SWATCH, WIDTH
from .look_section import ICON_DIR, LABEL_H, TILE
from .palette import linear_to_srgb, srgb_hex, srgb_to_linear

INNER = WIDTH - 2 * 0.006
MAP_H = 0.07
STEPS = 8
ROW_GAP = 0.004
L_MIN, L_MAX = 0.04, 0.96  # the map's bottom / top lightness (strip has the greys)


class MapTile(Image):
    """The hue x lightness image. Leaf node, clickable."""

    def __init__(self, section, src, width, height):
        super().__init__(src=src, width=width, height=height, style={"border_radius": 0.003})
        self.section = section
        self.label = "Pull on it: hue / light"
        self.w, self.h = width, height
        self.add_event_listener("pointer_main_enter", lambda *x: section.show_status(self.label))
        self.add_event_listener("pointer_main_leave", lambda *x: section.show_status(None))
        self.add_event_listener("pointer_main_press_start", lambda *x: section.map_start())
        self.add_event_listener("pointer_main_press_end", lambda *x: section.map_end())


class PickerSection(StudioSection):
    title = "PICKER"
    scope = "GLOBAL"
    idle_message = "Any colour / Pick"

    def __init__(self):
        bottom = TILE + LABEL_H
        strip_y = bottom + ROW_GAP
        map_y = strip_y + SWATCH + ROW_GAP
        super().__init__(WIDTH, map_y + MAP_H)
        self.h, self.l, self.s = 0.0, 0.5, 1.0
        self.dragging = False
        self.picking = False
        # map
        src = os.path.join(ICON_DIR, "picker_map.png")
        self.map = MapTile(self, src if os.path.exists(src) else None, INNER, MAP_H)
        self.map.position = Vector((0.0, map_y, 0.0))
        self.body.append_child(self.map)
        # saturation strip
        self.strip = []
        for k in range(STEPS):
            t = Tile(self, "", SWATCH, None, background=(0.5, 0.5, 0.5))
            t.sat = k / (STEPS - 1)
            t.position = Vector((k * CELL, strip_y, 0.0))
            self.strip.append(t)
            self.body.append_child(t)
        # Paint (= current colour) and Pick (eyedropper)
        self.paint_tile = Tile(self, "Paint the selection", TILE, None, background=(1, 0, 0))
        self.paint_tile.position = Vector((0.0, LABEL_H, 0.0))
        icon = os.path.join(ICON_DIR, "picker_dropper.png")
        self.pick_tile = Tile(self, "Pick: touch something with the ball", TILE, None,
                              src=icon if os.path.exists(icon) else None,
                              background=None if os.path.exists(icon) else (0.3, 0.3, 0.35), hover_fill=True)
        self.pick_tile.position = Vector((TILE + 0.006, LABEL_H, 0.0))
        self.body.append_child(self.paint_tile)
        self.body.append_child(self.pick_tile)
        for x, label in ((0.0, "Paint"), (TILE + 0.006, "Pick")):
            text = self._text(label, (0, 0), 18, (0.85, 0.88, 0.95, 1))
            w = text.bounds_local.size.x * text.scale.x
            text.position = Vector((x + max(0.0, (TILE - w) / 2), 0.0015, 0.0))
            self.body.append_child(text)
        self.hex_text = self._text("", (2 * (TILE + 0.006) + 0.004, LABEL_H + TILE / 2 - 0.003), 22, (1, 1, 1, 1))
        self.body.append_child(self.hex_text)
        self._show()

    # -- colour state -------------------------------------------------------------------------
    def srgb(self, s=None):
        return colorsys.hls_to_rgb(self.h, self.l, self.s if s is None else s)

    def set_from_srgb(self, rgb):
        h, l, s = colorsys.rgb_to_hls(*rgb[:3])
        if s > 0.02:  # greys keep the last hue
            self.h = h
        self.l, self.s = l, s
        self._show()

    def _show(self):
        cur = self.srgb()
        self.paint_tile.style["background"] = tuple(cur)
        for t in self.strip:
            t.style["background"] = tuple(self.srgb(t.sat))
            t.label = f"Saturation {round(t.sat * 100)}%"
            t.set_current(abs(t.sat - self.s) < 0.5 / (STEPS - 1))
        self.hex_text.text = srgb_hex(cur)

    def _apply(self, message_prefix=""):
        srgb = self.srgb()
        lin = srgb_to_linear(srgb)
        name = srgb_hex(srgb)
        brush.set_color(lin, name)  # what you draw next comes out in this colour
        targets = materials.selected_targets(bpy.context)
        report = materials.apply_color(targets, lin)
        if report["objects"]:
            for n in report["objects"]:
                ob = bpy.data.objects.get(n)
                if ob is not None:
                    ob.color = (*lin, 1.0)
            try:
                bpy.ops.ed.undo_push(message=f"VR colour {name}")
            except Exception:
                pass
            return message_prefix + materials.describe(report)
        return message_prefix + f"Pen: {name}"

    # -- map: hold the trigger and slide, let go to apply ----------------------------------------
    def _map_uv(self):
        area = self.area
        if area is None:
            return None
        p = area._pointer_local()
        if p is None:
            return None
        x = p.x - self.node.position.x - self.body.position.x - self.map.position.x
        y = p.y - self.node.position.y - self.body.position.y - self.map.position.y
        return max(0.0, min(1.0, x / self.map.w)), max(0.0, min(1.0, y / self.map.h))

    def _map_read(self):
        uv = self._map_uv()
        if uv is None:
            return False
        self.h = min(uv[0], 0.999)
        self.l = L_MIN + (L_MAX - L_MIN) * uv[1]
        if self.s < 0.05:  # coming from grey: show the colour you are pointing at
            self.s = 1.0
        self._show()
        return True

    def map_start(self):
        self.dragging = True
        self._map_read()

    def map_end(self):
        self.dragging = False
        try:
            self._map_read()
            message = self._apply()
        except Exception as e:
            import traceback

            message = "Colour failed (see console)"
            print(f"[vr_studio] picker: {e}\n{traceback.format_exc()}")
        self.finish(message)

    def tick(self):
        if self.dragging:
            from bl_xr.events.make_events import controller

            if controller.input_state.get("trigger_main_press", False):
                self._map_read()
            else:
                self.dragging = False
        if self.picking:
            self._pick_step()

    # -- tiles -------------------------------------------------------------------------------
    def press(self, tile):
        try:
            if tile is self.pick_tile:
                self.picking = not self.picking
                tile.set_current(self.picking)
                self.finish("Touch something with the ball" if self.picking else "Pick off")
                return
            if tile in self.strip:
                self.s = tile.sat
                self._show()
            message = self._apply()
        except Exception as e:
            import traceback

            message = "Colour failed (see console)"
            print(f"[vr_studio] picker: {e}\n{traceback.format_exc()}")
        self.finish(message)

    # -- eyedropper ------------------------------------------------------------------------------
    def _pick_step(self):
        ob = touched_object()
        if ob is None:
            return
        lin = object_color(ob)
        if lin is None:
            return
        self.set_from_srgb(linear_to_srgb(lin))
        name = srgb_hex(self.srgb())
        brush.set_color(srgb_to_linear(self.srgb()), name)
        self.picking = False
        self.pick_tile.set_current(False)
        haptic("SHORT_MEDIUM")
        self.finish(f"Picked {name} (pen). Paint = colour selection")

    def refresh(self, mat):
        self.pick_tile.set_current(self.picking)


def object_color(ob):
    """Linear RGB of what you see: first material's colour, else the object colour (strokes)."""
    for slot in getattr(ob, "material_slots", []):
        if slot.material is not None:
            col = materials.material_color(slot.material)
            if col is not None:
                return tuple(col)
    if ob.type in ("MESH", "CURVE", "FONT", "SURFACE", "GREASEPENCIL", "GPENCIL"):
        return tuple(ob.color[:3])
    return None


def touched_object():
    """The nearest object the grab sphere touches (a real object, never a group Empty)."""
    from bl_xr import xr_session

    from .grab import _mesh_distance, _near_bounds, get_reach_cm, grab_center

    center = Vector(grab_center())
    reach = (get_reach_cm() or 3) / 100.0 * xr_session.viewer_scale
    best, best_d = None, None
    for ob in bpy.context.view_layer.objects:
        if ob.type not in ("MESH", "CURVE", "FONT", "SURFACE") or not ob.visible_get():
            continue
        if not _near_bounds(ob, center, reach):
            continue
        try:
            r = _mesh_distance(ob, center)
        except Exception:
            r = None
        # touching a surface beats being inside something big (a room shell)
        d = 0.0 if r is None else (reach * 0.9 if r[1] else r[0])
        if r is not None and d > reach:
            continue
        if best_d is None or d < best_d:
            best, best_d = ob, d
    return best
