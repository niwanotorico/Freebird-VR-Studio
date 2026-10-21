# SPDX-License-Identifier: GPL-2.0-or-later
"""The VR Studio area: one strip next to Freebird's main menu that holds the Studio sections
(Color, Look, later Assets / Modifiers ...), built from Freebird's own UI toolkit (bl_xr).

Placement (every frame, so it rides on the hand like the main menu):
  * the area sits on the side where Freebird opens its sub-menus (right for right-handed),
    bottom-aligned with the main menu, right next to it
  * when one of Freebird's own sub-menus (Pen, Shape, Edit, Plugins, Mirror ...) is open on
    that side and would overlap, the area slides past it, and slides back when it closes
  * visible sections stack upwards in registration order; hidden ones take no space

A section is anything with: node (bl_xr Node, origin bottom-left, metres), width, height,
visible, refresh(context_material) — see StudioSection. Adding "Assets" = one new section
class + one launcher button in __init__.py.

bl_xr notes (Freebird v2.15): an Image without `src` draws a rounded flat-colour rectangle;
raycasts prefer leaf nodes and round distances to 1 mm, so clickable tiles are leaves sitting
3 mm in front of their panel background; textures must not be loaded from a timer.
"""

import json
import os
import sys

import bpy
from mathutils import Quaternion, Vector

import bl_xr
from bl_xr import Image, Node, Text, root, xr_session
from bl_xr.utils import apply_haptic_feedback

PAD = 0.006
HEADER = 0.016
TILE_Z = 0.003  # in front of the panel background by more than bl_xr's 1 mm raycast rounding
TEXT_SCALE = 0.0003
SECTION_GAP = 0.006
SIDE_GAP = 0.008
AREA_Z = 0.005  # Freebird's SUBMENU_Z_OFFSET
PANEL_BG = (0.0, 0.005, 0.02)
HOVER_BORDER = (0.0022, (1.0, 1.0, 1.0, 1.0))
CURRENT_BORDER = (0.0022, (0.2, 0.55, 1.0, 1.0))
HOVER_FILL = (0.064, 0.155, 0.662)
HEADER_BG = (0.02, 0.045, 0.13)  # the strip you pull (trigger) to rearrange panels
HEADER_Z = 0.0024  # header strip: in front of the background, behind the texts (TILE_Z)
SCOPE_COLORS = {"GLOBAL": (0.05, 0.42, 0.22), "LOCAL": (0.55, 0.33, 0.04)}  # green / amber
REFRESH_EVERY = 12  # frames between "what does the selection look like now" checks

# Freebird main-menu geometry, used when freebird.ui.main_menu is not importable
FALLBACK_MENU_OFFSET = -0.04  # menu_group sits BUTTON_SIZE to the side of the alt controller
FALLBACK_MAIN = (0.0, 0.08, 0.051)  # main menu left, right, bottom in menu_group space


def haptic(kind="TINY_LIGHT"):
    try:
        apply_haptic_feedback(hand="main", type=kind)
    except Exception:
        pass


class Tile(Image):
    """A clickable square: flat colour (background=...) or thumbnail (src=...). A leaf node."""

    def __init__(self, section, label, size, on_press, src=None, background=None, hover_fill=False):
        style = {"border_radius": size * 0.2}
        if background is not None:
            style["background"] = tuple(background)
        super().__init__(src=src, width=size, height=size, style=style)
        self.section = section
        self.label = label
        self.on_press = on_press
        self.hover_fill = hover_fill
        self.hovered = False
        self.current = False
        self.add_event_listener("pointer_main_enter", self._on_enter)
        self.add_event_listener("pointer_main_leave", self._on_leave)
        self.add_event_listener("pointer_main_press_end", self._on_press)

    def _restyle(self):
        border = HOVER_BORDER if self.hovered else CURRENT_BORDER if self.current else None
        if border is None:
            self.style.pop("border", None)
        else:
            self.style["border"] = border
        if self.hover_fill:
            if self.hovered or self.current:
                self.style["background"] = HOVER_FILL if self.hovered else (0.02, 0.06, 0.2)
            else:
                self.style.pop("background", None)

    def set_current(self, state):
        if self.current != state:
            self.current = state
            self._restyle()

    def _on_enter(self, event_name, event):
        self.hovered = True
        self._restyle()
        self.section.show_status(self.label)
        haptic()

    def _on_leave(self, event_name, event):
        self.hovered = False
        self._restyle()
        self.section.show_status(None)

    def _on_press(self, event_name, event):
        self.section.press(self)


class StudioSection:
    """Base: a panel with a title, a status line and tiles. Subclasses fill self.body."""

    title = "SECTION"
    idle_message = ""
    scope = None  # "GLOBAL" (synced to the room) / "LOCAL" (just you): a badge in the header

    def __init__(self, width, body_height):
        self.width = width
        self.height = body_height + 2 * PAD + HEADER
        self.visible = False
        self.last_message = self.idle_message
        self.background = Image(  # also catches the laser between tiles, so it stays visible
            width=self.width,
            height=self.height,
            style={"background": PANEL_BG, "opacity": 0.95, "border_radius": 0.005,
                   "border": (0.002, (0, 0, 0.005, 1))},
        )
        self.background.add_event_listener("pointer_main_press_start", lambda *x: None)
        self.title_text = self._text(self.title, (PAD, body_height + PAD + 0.006), 24, (1, 1, 1, 1))
        self.status = self._text(self.last_message, (PAD + 0.032, body_height + PAD + 0.006), 20, (0.75, 0.8, 0.9, 1))
        self.body = Node(position=Vector((PAD, PAD, TILE_Z)))
        # header strip: pull it with the trigger to move the panel around the hand (puzzle style)
        header_y = body_height + PAD
        self.header = Image(width=self.width, height=self.height - header_y,
                            style={"background": HEADER_BG, "border_radius": 0.005})
        self.header.position = Vector((0.0, header_y, HEADER_Z))  # > 1 mm in front: bl_xr rounds to 1 mm
        self.header.add_event_listener("pointer_main_press_start", self._on_header_press)
        self.header.add_event_listener("pointer_main_enter", lambda *x: self.show_status("Pull to rearrange (or grip it)"))
        self.header.add_event_listener("pointer_main_leave", lambda *x: self.show_status(None))
        children = [self.background, self.header, self.body, self.title_text, self.status]
        children += self._badge(body_height)
        self.node = Node(child_nodes=children, style={"visible": False})
        self.area = None
        self.col = 0  # column on the hand (0 = next to Freebird's menu)
        self.order = 0  # position in the column, bottom-up

    def _on_header_press(self, event_name, event):
        if self.area is not None:
            self.area.start_arrange(self)

    def _badge(self, body_height):
        """GLOBAL / LOCAL pill at the right end of the header."""
        if self.scope not in SCOPE_COLORS:
            return []
        text = self._text(self.scope, (0, 0), 16, (1, 1, 1, 1))
        tw = text.bounds_local.size.x * text.scale.x
        w, h = tw + 0.006, 0.010
        x = self.width - PAD - w
        y = body_height + PAD + 0.003
        self._badge_x = x
        pill = Image(width=w, height=h, intersects=None,
                     style={"background": SCOPE_COLORS[self.scope], "border_radius": h * 0.5})
        pill.position = Vector((x, y, HEADER_Z + 0.0003))
        text.position = Vector((x + 0.003, y + 0.0025, TILE_Z))
        return [pill, text]

    @staticmethod
    def _text(text, xy, size, color):
        t = Text(text=text, style={"color": color, "font_size": size}, intersects=None,
                 position=Vector((xy[0], xy[1], TILE_Z)))
        t.scale = TEXT_SCALE
        return t

    def show_status(self, text):
        self.status.text = text if text else self.last_message

    def set_visible(self, state):
        self.visible = bool(state)
        self.node.style["visible"] = self.visible

    def finish(self, message):
        self.last_message = message
        self.status.text = message
        haptic("SHORT_LIGHT")

    def press(self, tile):
        raise NotImplementedError

    def refresh(self, mat):
        """Mark the tile matching the active object's material (mat may be None)."""


def context_material(context=None):
    """First material of the active (or first selected) object: what the panels highlight."""
    context = context or bpy.context
    vl = context.view_layer
    ob = vl.objects.active
    if ob is None or not ob.select_get(view_layer=vl):
        ob = next((o for o in vl.objects if o.select_get(view_layer=vl)), None)
    if ob is None:
        return None
    from .groups import is_group, with_descendants

    for m in with_descendants([ob]) if is_group(ob) else [ob]:  # a group: its first coloured member
        for slot in getattr(m, "material_slots", []):
            if slot.material is not None:
                return slot.material
    return None


class StudioArea:
    def __init__(self):
        self.sections = []
        self.node = Node(id="vr_studio_area", style={"fixed_scale": True, "visible": True})
        self.node.update = self._update
        self._x = None
        self._frame = 0
        self._dragging = None
        self._drag_source = "pointer"
        self._columns = []
        self._min_y = self._max_y = 0.0
        self.width = self.height = 0.0

    def add(self, section):
        section.area = self
        saved = _load_layout().get(section.title)
        if saved and len(saved) == 2:
            section.col, section.order = int(saved[0]), float(saved[1])
        else:
            section.col, section.order = 0, float(len(self.sections))
        self.sections.append(section)
        self.node.append_child(section.node)
        return section

    # -- show / hide ------------------------------------------------------
    def attach(self):
        if self.node.parent is None:
            root.append_child(self.node)

    def detach(self):
        if self.node.parent is not None:
            self.node.parent.remove_child(self.node)
        self._dragging = None

    def toggle(self, section):
        section.set_visible(not section.visible)
        self._layout()
        self._refresh()

    # -- layout -----------------------------------------------------------
    def _layout(self):
        y = 0.0
        visible = [s for s in self.sections if s.visible]
        cols = sorted({s.col for s in visible})
        x = 0.0
        self.height = self.width = 0.0
        self._columns = []  # (col, x0, x1) for arranging
        self._min_y = self._max_y = 0.0
        for c in cols:  # empty columns collapse
            col = [s for s in visible if s.col == c]
            col_w = max(s.width for s in col)
            y = 0.0  # above the baseline (bottom of Freebird's menu): stack upwards
            for s in sorted((s for s in col if s.order >= 0), key=lambda s: s.order):
                s.node.position = Vector((x, y, 0.0))
                y += s.height + SECTION_GAP
            self._max_y = max(self._max_y, y - SECTION_GAP)
            y = 0.0  # below the baseline: hang downwards (-1 = right under it)
            for s in sorted((s for s in col if s.order < 0), key=lambda s: -s.order):
                y -= s.height + (SECTION_GAP if y < 0 else 0.0)
                s.node.position = Vector((x, y, 0.0))
            self._min_y = min(self._min_y, y)
            self._columns.append((c, x, x + col_w))
            x += col_w + SECTION_GAP
        self.width = max(0.0, x - SECTION_GAP)
        self.height = self._max_y - self._min_y

    def _menu_space(self):
        """(left, right, bottom, [(l, r, b, t) of Freebird panels open beside the main menu])
        in Freebird's menu_group space (metres, before world scale)."""
        mm = sys.modules.get("freebird.ui.main_menu")
        if mm is None:
            left, right, bottom = FALLBACK_MAIN
            return left, right, bottom, []
        group = mm.menu_group
        panels = group.q("#main_menu_panels")
        off = panels.position if panels is not None else Vector()
        main = mm.main_menu
        b = main.bounds_local
        left, right = off.x + main.position.x + b.min.x, off.x + main.position.x + b.max.x
        bottom = off.y + main.position.y + b.min.y
        others = []
        if group.get_computed_style("visible", True):
            for node in list(mm.submenus.values()) + [mm.submenu_custom, getattr(mm, "mirror_panel", None)]:
                if node is None or not node.get_computed_style("visible", True):
                    continue
                p = off if node.parent is panels else Vector()
                nb = node.bounds_local
                x0, y0 = p.x + node.position.x, p.y + node.position.y
                others.append((x0 + nb.min.x, x0 + nb.max.x, y0 + nb.min.y, y0 + nb.max.y))
        return left, right, bottom, others

    def _target_x(self, left, right, bottom, others):
        top = bottom + getattr(self, "_max_y", self.height)
        bottom = bottom + getattr(self, "_min_y", 0.0)
        if bl_xr.main_hand == "right":  # Freebird's sub-menus open on the right: so do we
            edge = right
            for l, r, b, t in others:
                if l >= right - 0.002 and b < top and t > bottom:
                    edge = max(edge, r)
            return edge + SIDE_GAP
        edge = left
        for l, r, b, t in others:
            if r <= left + 0.002 and b < top and t > bottom:
                edge = min(edge, l)
        return edge - SIDE_GAP - self.width

    def _update(self):
        if not xr_session.is_running:
            return
        self._layout()
        visible = any(s.visible for s in self.sections)
        if not visible:
            return
        left, right, bottom, others = self._menu_space()
        tx = self._target_x(left, right, bottom, others)
        self._x = tx if self._x is None or abs(tx - self._x) < 0.001 else self._x + (tx - self._x) * 0.35
        scale = xr_session.viewer_scale
        rot = xr_session.controller_alt_aim_rotation
        origin = xr_session.controller_alt_aim_position + rot @ Vector((FALLBACK_MENU_OFFSET * scale, 0, 0))
        self.node.rotation = rot
        self.node.position = origin + rot @ (Vector((self._x, bottom, AREA_Z)) * scale)
        if self._dragging is not None:
            self._arrange_step()
        self._frame += 1
        if self._frame % REFRESH_EVERY == 0:
            self._refresh()

    # -- rearranging (pull a header) -----------------------------------------------------
    def start_arrange(self, section, source="pointer"):
        """Move a panel around the hand: pulled by its header (trigger) or held with the grip."""
        self._dragging = section
        self._drag_source = source
        section.show_status("Move me")
        haptic("SHORT_LIGHT")

    def to_local(self, world_point):
        scale = xr_session.viewer_scale
        return self.node.rotation.inverted() @ (Vector(world_point) - self.node.position) / scale

    def panel_at(self, world_point, margin):
        """The visible panel the grip sphere touches (area coordinates, `margin` in metres)."""
        if self.node.parent is None:
            return None
        p = self.to_local(world_point)
        if abs(p.z) > margin + 0.01:
            return None
        best, best_d = None, None
        for s in self.sections:
            if not s.visible:
                continue
            x, y = s.node.position.x, s.node.position.y
            dx = max(x - p.x, 0.0, p.x - (x + s.width))
            dy = max(y - p.y, 0.0, p.y - (y + s.height))
            d = (dx * dx + dy * dy) ** 0.5  # 0 inside the panel
            if d <= margin and (best_d is None or d < best_d):
                best, best_d = s, d
        return best

    def _pointer_local(self):
        """Where the main-hand laser hits the area's plane, in area coordinates (metres)."""
        from bl_xr.consts import VEC_FORWARD

        scale = xr_session.viewer_scale
        rot = self.node.rotation
        origin = self.node.position
        normal = rot @ Vector((0, 0, 1))
        p = Vector(xr_session.controller_main_aim_position)
        d = Quaternion(xr_session.controller_main_aim_rotation) @ VEC_FORWARD
        denom = d.dot(normal)
        if abs(denom) < 1e-6:
            return None
        t = (origin - p).dot(normal) / denom
        if t < 0:
            return None
        return rot.inverted() @ ((p + d * t) - origin) / scale

    def _arrange_step(self):
        from bl_xr.events.make_events import controller

        s = self._dragging
        button = "squeeze_main_press" if self._drag_source == "grip" else "trigger_main_press"
        if not controller.input_state.get(button, False):
            self._dragging = None
            _save_layout(self.sections)
            s.finish("Placed")
            return
        if self._drag_source == "grip":
            from .grab import grab_center

            pt = self.to_local(grab_center())
        else:
            pt = self._pointer_local()
        if pt is None:
            return
        # which column: existing ones, or a new one to the right of the last
        cols = getattr(self, "_columns", [])
        x = pt.x
        target_col = s.col
        if cols:
            last_c, _x0, last_x1 = cols[-1]
            if x > last_x1 + SECTION_GAP and len(cols) < MAX_COLUMNS:
                target_col = last_c + 1
            else:
                for c, x0, x1 in cols:
                    if x <= x1 + SECTION_GAP / 2:
                        target_col = c
                        break
                else:
                    target_col = last_c
        # where in the column: above the baseline (stacked up) or below it (hanging down)
        others = [o for o in self.sections if o.visible and o.col == target_col and o is not s]
        above = sorted((o for o in others if o.order >= 0), key=lambda o: o.order)  # bottom-up
        below = sorted((o for o in others if o.order < 0), key=lambda o: -o.order)  # top-down
        if pt.y >= 0:
            i = next((k for k, o in enumerate(above) if pt.y < o.node.position.y + o.height / 2), len(above))
            above.insert(i, s)
        else:
            i = next((k for k, o in enumerate(below) if pt.y > o.node.position.y + o.height / 2), len(below))
            below.insert(i, s)
        before = (s.col, s.order)
        old_col = s.col
        s.col = target_col
        for k, o in enumerate(above):
            o.order = float(k)
        for k, o in enumerate(below):
            o.order = -1.0 - k
        if (s.col, s.order) != before or old_col != target_col:
            self._normalise()
            self._layout()
            haptic()

    def _normalise(self):
        """Compact columns (0, 1, 2 ...) and orders (above: 0, 1, 2 ... / below: -1, -2 ...)."""
        cols = sorted({o.col for o in self.sections})
        remap = {c: i for i, c in enumerate(cols)}
        for o in self.sections:
            o.col = remap[o.col]
        for c in remap.values():
            col = [o for o in self.sections if o.col == c]
            for i, o in enumerate(sorted((o for o in col if o.order >= 0), key=lambda o: o.order)):
                o.order = float(i)
            for i, o in enumerate(sorted((o for o in col if o.order < 0), key=lambda o: -o.order)):
                o.order = -1.0 - i

    def _refresh(self):
        try:
            mat = context_material()
        except Exception:
            mat = None
        for s in self.sections:
            if s.visible:
                try:
                    s.refresh(mat)
                except Exception as e:
                    print(f"[vr_studio] refresh {s.title}: {e}")


MAX_COLUMNS = 3
LAYOUT_PATH = os.path.join(os.path.expanduser("~"), ".freebird", "vr_studio_settings.json")


def _slot(stack, order):
    """Index `order` would take in a column's stack."""
    return sum(1 for o in stack if o.order < order)


def _load_layout():
    try:
        with open(LAYOUT_PATH, "r", encoding="utf-8") as f:
            return json.load(f).get("layout", {})
    except Exception:
        return {}


def _save_layout(sections):
    try:
        data = {}
        if os.path.exists(LAYOUT_PATH):
            with open(LAYOUT_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        data.pop("floating", None)
        data["layout"] = {s.title: [s.col, s.order] for s in sections}
        os.makedirs(os.path.dirname(LAYOUT_PATH), exist_ok=True)
        with open(LAYOUT_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[vr_studio] could not save panel layout: {e}")
