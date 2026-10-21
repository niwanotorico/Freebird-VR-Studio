# SPDX-License-Identifier: GPL-2.0-or-later
"""GRAB section: how far your hand reaches when you squeeze (OFF / 3 / 5 / 8 cm), and where the
grab sphere sits on the hand (offset from the grip pose, to find the middle finger). LOCAL."""

from mathutils import Vector

from . import grab
from .area import StudioSection, Tile
from .color_section import WIDTH
from .look_section import GAP, LABEL_H, TILE

LABELS = {0: ("OFF", "Plain Freebird (all GS controls off)"),
          3: ("3 cm", "Reach 3 cm"),
          5: ("5 cm", "Reach 5 cm"),
          8: ("8 cm", "Reach 8 cm")}

AXES = ("X", "Y", "Z")
OFFSET_STEP_CM = 0.5
# offset row: action, text on the tile, label under it, hover text
OFFSET_TILES = (("axis", "X", "Axis", "Sphere offset: pick the axis X / Y / Z"),
                ("minus", "-", "-0.5 cm", "Move the sphere -0.5 cm along the axis"),
                ("plus", "+", "+0.5 cm", "Move the sphere +0.5 cm along the axis"),
                ("zero", "0", "Reset", "Sphere back on the middle finger (default offset)"))


def offset_text(offset):
    return " ".join(f"{a.lower()}{v:+.1f}" for a, v in zip(AXES, offset)) + " cm"


class GrabSection(StudioSection):
    title = "GRAB"
    scope = "LOCAL"
    idle_message = "Hand reach (just you)"

    def __init__(self):
        row = TILE + LABEL_H + 0.002
        super().__init__(WIDTH, 2 * row - 0.002)
        self.axis = 0
        self.offset_tiles = []
        for i, (action, inner, label, hover) in enumerate(OFFSET_TILES):
            x = i * (TILE + GAP)
            t = Tile(self, hover, TILE, None, background=(0.12, 0.14, 0.2), hover_fill=True)
            t.offset_action = action
            t.position = Vector((x, row + LABEL_H, 0.0))
            self.offset_tiles.append(t)
            self.body.append_child(t)
            text = self._text(inner, (0, 0), 26, (1, 1, 1, 1))
            w = text.bounds_local.size.x * text.scale.x
            text.position = Vector((x + max(0.0, (TILE - w) / 2), row + LABEL_H + TILE * 0.4, 0.003))
            self.body.append_child(text)
            if action == "axis":
                self.axis_text = text
            h = self._text(label, (0, 0), 16, (0.75, 0.8, 0.9, 1))
            hw = h.bounds_local.size.x * h.scale.x
            h.position = Vector((x + max(0.0, (TILE - hw) / 2), row + 0.0015, 0.0))
            self.body.append_child(h)
        self.tiles = []
        for i, cm in enumerate(grab.CHOICES):
            label, hover = LABELS[cm]
            x = i * (TILE + GAP)
            t = Tile(self, hover, TILE, None, background=(0.12, 0.14, 0.2), hover_fill=True)
            t.cm = cm
            t.position = Vector((x, LABEL_H, 0.0))
            self.tiles.append(t)
            self.body.append_child(t)
            text = self._text(label, (0, 0), 26 if cm else 22, (1, 1, 1, 1))
            w = text.bounds_local.size.x * text.scale.x
            text.position = Vector((x + max(0.0, (TILE - w) / 2), LABEL_H + TILE * 0.4, 0.003))
            self.body.append_child(text)
            hint = "Freebird" if cm == 0 else "easier" if cm == 5 else ""
            if hint:
                h = self._text(hint, (0, 0), 16, (0.75, 0.8, 0.9, 1))
                hw = h.bounds_local.size.x * h.scale.x
                h.position = Vector((x + max(0.0, (TILE - hw) / 2), 0.0015, 0.0))
                self.body.append_child(h)

    def press(self, tile):
        action = getattr(tile, "offset_action", None)
        if action is not None:
            self.press_offset(action)
            return
        grab.set_reach_cm(tile.cm)
        for t in self.tiles:
            t.set_current(t is tile)
        self.finish(LABELS[tile.cm][1])

    def press_offset(self, action):
        offset = list(grab.get_offset_cm())
        if action == "axis":
            self.axis = (self.axis + 1) % len(AXES)
            self.axis_text.text = AXES[self.axis]
        elif action == "zero":
            offset = list(grab.DEFAULT_OFFSET_CM)
        else:
            offset[self.axis] += OFFSET_STEP_CM if action == "plus" else -OFFSET_STEP_CM
        if action != "axis":
            grab.set_offset_cm(offset)
            grab.debug(f"grab offset -> {grab.get_offset_cm()} cm")
        self.finish(f"{AXES[self.axis]} axis: {offset_text(grab.get_offset_cm())}")

    def refresh(self, mat):
        cm = grab.get_reach_cm()
        nearest = min(self.tiles, key=lambda t: abs(t.cm - cm)) if cm else self.tiles[0]
        for t in self.tiles:  # the stick sets any size: mark the closest preset
            t.set_current(t is nearest)
        offset = grab.get_offset_cm()
        self.offset_tiles[3].set_current(tuple(offset) == tuple(grab.DEFAULT_OFFSET_CM))
        if cm and self.status.text == self.last_message:
            message = f"Reach {cm:.1f} cm (stick up/down)"
            if any(offset):
                message = f"Reach {cm:.1f}, {offset_text(offset)}"
            self.status.text = self.last_message = message
