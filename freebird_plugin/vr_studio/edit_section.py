# SPDX-License-Identifier: GPL-2.0-or-later
"""EDIT section: mode (Object / Edit / Pose), Vert / Edge / Face, proportional editing. LOCAL."""

import os

from mathutils import Vector

from . import editmode
from .area import StudioSection, Tile
from .color_section import WIDTH
from .look_section import GAP, LABEL_H, TILE

ROW = TILE + LABEL_H + 0.002
# (key, label, hover, Freebird icon)
TOP = [("OBJECT", "Object", "Object Mode (pen etc. back)", "object_mode.png"),
       ("EDIT", "Edit", "Edit Mode (grab vertices)", "edit_mode.png"),
       ("POSE", "Pose", "Pose Mode (armatures)", "armature.png"),
       ("PROP", "Prop.", "Proportional editing on / off", "proportional_edit.png")]
BOTTOM = [("VERT", "Vert", "Grab vertices (stick left/right)", "edit_vert.png"),
          ("EDGE", "Edge", "Grab edges (stick left/right)", "edit_edge.png"),
          ("FACE", "Face", "Grab faces (stick left/right)", "edit_face.png")]


def _fb_icon(name):
    try:
        import freebird

        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(freebird.__file__))), "images", name)
        return p if os.path.exists(p) else None
    except Exception:
        return None


SEGMENTS = 16
SLIDER_H = 0.012
SLIDER_ROW = SLIDER_H + LABEL_H + 0.004
SEG_ON = (0.2, 0.55, 1.0)
SEG_OFF = (0.12, 0.14, 0.2)


class SliderSegment(Tile):
    """One step of the falloff slider: press it, or slide across with the trigger held."""

    def __init__(self, section, index, width):
        super().__init__(section, "Proportional size", width, None, background=SEG_OFF)
        self.height = SLIDER_H
        self.style["border_radius"] = 0.002
        self.index = index
        self.add_event_listener("pointer_main_press_start", self._on_slide)

    def _on_enter(self, event_name, event):
        super()._on_enter(event_name, event)
        try:
            from bl_xr.events.make_events import controller

            if controller.input_state.get("trigger_main_press", False):
                self._on_slide(event_name, event)
        except Exception:
            pass

    def _on_slide(self, event_name, event):
        self.section.slide(self.index)

    def _on_press(self, event_name, event):
        self.section.slide(self.index)


class EditSection(StudioSection):
    title = "EDIT"
    scope = "LOCAL"
    idle_message = "Mode / Vert-Edge-Face"

    def __init__(self):
        super().__init__(WIDTH, 2 * ROW + SLIDER_ROW - 0.002)
        self.tiles = []
        # falloff slider (bottom): label + 16 segments
        inner = WIDTH - 2 * 0.006
        gap = 0.0015
        seg_w = (inner - (SEGMENTS - 1) * gap) / SEGMENTS
        self.segments = []
        for i in range(SEGMENTS):
            seg = SliderSegment(self, i, seg_w)
            seg.position = Vector((i * (seg_w + gap), LABEL_H, 0.0))
            self.segments.append(seg)
            self.body.append_child(seg)
        self.slider_label = self._text("Prop. size", (0, 0.0015), 18, (0.85, 0.88, 0.95, 1))
        self.body.append_child(self.slider_label)
        for r, row in enumerate((TOP, BOTTOM)):
            y = SLIDER_ROW + (1 - r) * ROW + LABEL_H
            for i, (key, label, hover, icon) in enumerate(row):
                x = i * (TILE + GAP)
                src = _fb_icon(icon)
                t = Tile(self, hover, TILE, None, src=src, background=None if src else (0.3, 0.3, 0.35),
                         hover_fill=True)
                t.key = key
                t.position = Vector((x, y, 0.0))
                self.tiles.append(t)
                self.body.append_child(t)
                text = self._text(label, (0, 0), 18, (0.85, 0.88, 0.95, 1))
                w = text.bounds_local.size.x * text.scale.x
                text.position = Vector((x + max(0.0, (TILE - w) / 2), y - LABEL_H + 0.0015, 0.0))
                self.body.append_child(text)

    def press(self, tile):
        try:
            if tile.key in ("OBJECT", "EDIT", "POSE"):
                message = editmode.set_mode(tile.key)
            elif tile.key == "PROP":
                message = editmode.toggle_proportional()
            else:
                message = editmode.set_select_mode(tile.key)
        except Exception as e:
            import traceback

            message = "Failed (see console)"
            print(f"[vr_studio] edit {tile.key}: {e}\n{traceback.format_exc()}")
        self.refresh(None)
        self.finish(message)

    def slide(self, index):
        value = editmode.slider_value(index / (SEGMENTS - 1))
        editmode.set_falloff(value)
        self._show_slider(value)
        msg = f"Prop. size {editmode.describe_falloff(value)}"
        if not editmode.proportional():
            msg += " (Prop. is OFF)"
        self.last_message = msg
        self.status.text = msg

    def _show_slider(self, value):
        n = round(editmode.slider_pos(value) * (SEGMENTS - 1))
        for seg in self.segments:
            seg.style["background"] = SEG_ON if seg.index <= n else SEG_OFF
        self.slider_label.text = f"Prop. size  {editmode.describe_falloff(value)}"

    def refresh(self, mat):
        try:
            self._show_slider(editmode.falloff())
        except Exception:
            pass
        try:
            mode = editmode.current_mode()
            sel = editmode.mesh_select_mode() if mode == "EDIT" else None
            prop = editmode.proportional()
        except Exception:
            return
        for t in self.tiles:
            t.set_current(t.key == mode or t.key == sel or (t.key == "PROP" and prop))
