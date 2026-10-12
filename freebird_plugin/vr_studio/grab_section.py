# SPDX-License-Identifier: GPL-2.0-or-later
"""GRAB section: how far your hand reaches when you squeeze (OFF / 3 / 5 / 8 cm). LOCAL."""

from mathutils import Vector

from . import grab
from .area import StudioSection, Tile
from .color_section import WIDTH
from .look_section import GAP, LABEL_H, TILE

LABELS = {0: ("OFF", "Plain Freebird (all GS controls off)"),
          3: ("3 cm", "Reach 3 cm"),
          5: ("5 cm", "Reach 5 cm"),
          8: ("8 cm", "Reach 8 cm")}


class GrabSection(StudioSection):
    title = "GRAB"
    scope = "LOCAL"
    idle_message = "Hand reach (just you)"

    def __init__(self):
        super().__init__(WIDTH, TILE + LABEL_H)
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
        grab.set_reach_cm(tile.cm)
        for t in self.tiles:
            t.set_current(t is tile)
        self.finish(LABELS[tile.cm][1])

    def refresh(self, mat):
        cm = grab.get_reach_cm()
        nearest = min(self.tiles, key=lambda t: abs(t.cm - cm)) if cm else self.tiles[0]
        for t in self.tiles:  # the stick sets any size: mark the closest preset
            t.set_current(t is nearest)
        if cm and self.status.text == self.last_message:
            self.status.text = self.last_message = f"Reach {cm:.1f} cm (stick up/down)"
