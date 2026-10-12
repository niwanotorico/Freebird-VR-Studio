# SPDX-License-Identifier: GPL-2.0-or-later
"""Gravity Sketch style buttons (right-handed names; Freebird mirrors them for left-handers):

    main B   empty hand: UNDO (Freebird's undo, so FreebirdCollabo's own-changes undo in a room)
             holding something: DELETE it              (Freebird's quick tools are not used)
    main A   COLOR: open / close VR Studio's colour panel   (clone = grip + trigger instead)
    alt X    GROUP (tap) - see groups.py; hold = Freebird's select-while-held
    main stick up/down      grab sphere size (up = bigger); Edit Mode + proportional editing +
                            holding vertices: Freebird's falloff size
    main stick left/right   Freebird's own pen / cursor size; Edit Mode: Vert / Edge / Face

The controller buttons' icons / tooltips are re-labelled to match. Nothing in Freebird's files
changes: its listeners get a filter in front of them at runtime, and all of it is undone when
VR Studio is unloaded.
"""

import os
import time

ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")
REACH_SPEED_CM = 14.0  # cm per second at full stick
REACH_MIN_CM, REACH_MAX_CM = 1.0, 15.0

_patched = []  # (owner, event, callback, original options)
_added = []  # (event, callback) we added on root
_overlays = []  # (button, [overlay images])
_saved = {}  # node id -> (tooltip text, original icon visible)
_stick = {"t": None, "moved": False}
_color_toggle = None  # set by __init__: toggles the COLOR section


# -- listener plumbing ---------------------------------------------------------
def _wrap(owner, event, callback, make_filter, marker):
    entries = getattr(owner, "event_listeners", {}).get(event, [])
    for i in range(len(entries) - 1, -1, -1):
        l, opts = entries[i]
        if l != callback:  # == : bound methods (cursor.on_cursor_resize) are new objects each time
            continue
        if not opts.get(marker) and any(l2 == l and o2.get(marker) for l2, o2 in entries):
            del entries[i]  # Freebird re-added it after we wrapped it
            continue
        if not opts.get(marker):
            new = dict(opts)
            new["filter_fn"] = make_filter(opts.get("filter_fn"))
            new[marker] = True
            for k, v in opts.items():
                if k.startswith("_vr_studio"):
                    new[k] = v
            entries[i] = (l, new)
            _patched.append((owner, event, l, opts, marker))


def _never(prev):
    return lambda *a: False


def _add(event, cb):
    from bl_xr import root

    if (event, cb) not in _added:
        root.add_event_listener(event, cb)
        _added.append((event, cb))


# -- actions -----------------------------------------------------------------------
def undo():
    try:
        from freebird.undo_redo import undo as fb_undo

        fb_undo()
        from .grab import debug

        debug("B: undo")
    except Exception as e:
        print(f"[vr_studio] undo failed: {e}")


def _keyframe_joystick_active():
    try:
        from freebird import gizmos

        return "joystick_for_keyframe" in gizmos.active_gizmos
    except Exception:
        return False


def on_a_start(self, event_name, event):
    if _keyframe_joystick_active() or _color_toggle is None:
        return
    try:
        _color_toggle()
    except Exception as e:
        print(f"[vr_studio] A: colour panel: {e}")


def on_stick(self, event_name, event):
    from . import grab

    try:
        from freebird import settings

        if settings["world_nav.nav_mode"] in ("WALK", "FLY") or _keyframe_joystick_active():
            return
    except Exception:
        pass
    if _proportional_stick():
        return  # holding vertices with proportional editing on: up/down = falloff size (Freebird)
    cm = grab.get_reach_cm()
    now = time.time()
    dt = 0.0 if _stick["t"] is None else min(now - _stick["t"], 0.1)
    _stick["t"] = now
    if not cm:
        return  # OFF stays OFF (Freebird's own grab)
    value = getattr(event, "value", 0.0) or 0.0
    cm = max(REACH_MIN_CM, min(REACH_MAX_CM, cm + value * REACH_SPEED_CM * dt))
    grab.set_reach_cm(cm, save=False)
    _stick["moved"] = True


def _squeezing():
    try:
        from bl_xr.events.make_events import controller

        return controller.input_state.get("squeeze_main_press", False)
    except Exception:
        return False


def _proportional_stick():
    """Edit Mode + proportional editing + holding something: Freebird's falloff resize."""
    try:
        from . import editmode

        return editmode.current_mode() != "OBJECT" and editmode.proportional() and _squeezing()
    except Exception:
        return False


def _only_when_proportional(prev):
    def filt(self, event_name, event):
        if not _proportional_stick():
            return False  # otherwise up/down is the grab sphere size
        return prev(self, event_name, event) if prev else True

    return filt


def _not_in_edit_mode(prev):
    def filt(self, event_name, event):
        try:
            from . import editmode

            if editmode.current_mode() == "EDIT":
                return False  # left/right = Vert / Edge / Face in Edit Mode
        except Exception:
            pass
        return prev(self, event_name, event) if prev else True

    return filt


def _not_while_arranging(prev):
    def filt(self, event_name, event):
        try:
            from .grab import arranging

            if arranging():
                return False
        except Exception:
            pass
        return prev(self, event_name, event) if prev else True

    return filt


FLICK_ON, FLICK_OFF = 0.7, 0.3
_flick = {"latched": False}


def on_stick_x(self, event_name, event):
    """Edit Mode: flick right / left = next / previous of Vert -> Edge -> Face."""
    from . import editmode

    if editmode.current_mode() != "EDIT" or _keyframe_joystick_active():
        return
    v = getattr(event, "value", 0.0) or 0.0
    if _flick["latched"]:
        if abs(v) < FLICK_OFF:
            _flick["latched"] = False
        return
    if abs(v) >= FLICK_ON:
        _flick["latched"] = True
        msg = editmode.step_select_mode(1 if v > 0 else -1)
        try:
            from bl_xr.utils import apply_haptic_feedback

            apply_haptic_feedback(hand="main", type="TINY_LIGHT")
        except Exception:
            pass
        from .grab import debug

        debug(f"stick: {msg}")


def on_stick_x_end(self, event_name, event):
    _flick["latched"] = False


def on_stick_end(self, event_name, event):
    from . import grab

    _stick["t"] = None
    if _stick["moved"]:
        _stick["moved"] = False
        grab.set_reach_cm(grab.get_reach_cm(), save=True)


# -- controller labels ---------------------------------------------------------------
LABELS = {  # node id: (normal icon, normal tooltip, holding icon, holding tooltip)
    "controller_main_b": ("undo.png", "UNDO", "trash.png", "DELETE"),
    "controller_main_a": ("color.png", "COLOR", None, None),
    "controller_alt_a": ("group.png", "GROUP", None, None),
}


def _set_tooltip(btn, text):
    t = btn.tooltip
    if t.text == text:
        return
    t.text = text
    try:
        w = t.bounds_local.size.x * t.scale.x
        t.position.x = 0.5 - min(w, 0.95) / 2
    except Exception:
        pass


def _icon_path(name):
    p = os.path.join(ICON_DIR, name)
    if os.path.exists(p):
        return p
    try:  # Freebird's own icons (undo.png ...)
        import freebird

        q = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(freebird.__file__))), "images", name)
        return q if os.path.exists(q) else None
    except Exception:
        return None


def build_labels():
    """Add our icons on top of Freebird's controller buttons. Call at VR start only
    (bl_xr loads textures when `src` is set, which must not happen in a timer)."""
    from bl_xr import Image, root

    if _overlays:
        return
    for node_id, (icon, tip, hold_icon, _hold_tip) in LABELS.items():
        btn = root.q(f"#{node_id}")
        if btn is None or not hasattr(btn, "icon"):
            continue
        imgs = []
        for name in (icon, hold_icon):
            path = _icon_path(name) if name else None
            img = None
            if path:
                img = Image(src=path, intersects=None)  # same as Freebird's Button icon
                btn.append_child(img)
            imgs.append(img)
        _saved[node_id] = (btn.tooltip.text, btn.icon.style.get("visible", True))
        btn.icon.style["visible"] = False
        _overlays.append((btn, node_id, imgs))


_labels_active = {"on": True}


def set_labels_active(on):
    """OFF = Freebird's own icons / tooltips back (our overlays stay loaded, just hidden:
    textures can't be loaded again outside VR start)."""
    if _labels_active["on"] == on:
        return
    _labels_active["on"] = on
    for btn, node_id, imgs in _overlays:
        for img in imgs:
            if img is not None:
                img.style["visible"] = False
        text, icon_visible = _saved.get(node_id, (None, True))
        btn.icon.style["visible"] = icon_visible if not on else False
        if not on:
            if text is not None:
                _set_tooltip(btn, text)
            if node_id == "controller_alt_a":
                btn.style["visible"] = False


def update_labels(holding):
    if not _labels_active["on"]:
        return
    for btn, node_id, (normal, held) in _overlays:
        _icon, tip, _hicon, hold_tip = LABELS[node_id]
        show_held = holding and held is not None
        if normal is not None:
            normal.style["visible"] = not show_held
        if held is not None:
            held.style["visible"] = show_held
        _set_tooltip(btn, hold_tip if show_held else tip)
        if node_id in ("controller_main_a", "controller_alt_a"):
            btn.style["visible"] = True  # Freebird hides these; ours are always in use


def remove_labels():
    for btn, node_id, imgs in _overlays:
        for img in imgs:
            if img is not None and img.parent is btn:
                btn.remove_child(img)
        text, icon_visible = _saved.get(node_id, (None, True))
        btn.icon.style["visible"] = icon_visible
        if text is not None:
            _set_tooltip(btn, text)
        if node_id == "controller_alt_a":
            btn.style["visible"] = False
    _overlays.clear()
    _saved.clear()


# -- install / every frame / uninstall -------------------------------------------------
def ensure():
    """Every frame (cheap): keep our filters in front of Freebird's listeners."""
    from bl_xr import root

    try:
        from freebird.tools import clone

        _wrap(root, "button_a_main_start", clone.on_clone_start, _never, "_vr_studio_a")
        _wrap(root, "button_a_main_press", clone.on_clone_press, _never, "_vr_studio_a")
    except Exception:
        pass
    _add("button_a_main_start", on_a_start)
    _add("joystick_y_main_press", on_stick)  # up / down = grab sphere size
    _add("joystick_y_main_end", on_stick_end)
    _ensure_prop_sphere_on_grip()
    try:  # gripping a VR Studio panel must not also move the world (Freebird GRAB navigation)
        from freebird import navigate

        for ev, cb in (("drag_start", navigate.on_nav_transform_start), ("drag", navigate.on_nav_transform),
                       ("drag_end", navigate.on_nav_transform_end)):
            _wrap(root, ev, cb, _not_while_arranging, "_vr_studio_nav")
    except Exception:
        pass
    _add("joystick_x_main_press", on_stick_x)  # Edit Mode: left / right = Vert / Edge / Face
    _add("joystick_x_main_end", on_stick_x_end)
    try:
        from freebird.tools.transform_common import on_joystick_vertical

        _wrap(root, "joystick_y_main_press", on_joystick_vertical, _only_when_proportional, "_vr_studio_y")
    except Exception:
        pass
    try:
        from freebird.gizmos.cursor import cursor

        _wrap(root, "joystick_x_main_press", cursor.on_cursor_resize, _not_in_edit_mode, "_vr_studio_x")
    except Exception:
        pass


def uninstall():
    uninstall_hooks()
    remove_labels()


def _prop_sphere():
    try:
        from freebird.gizmos.proportional_edit_cursor import proportional_edit_sphere

        return proportional_edit_sphere
    except Exception:
        return None


def _ensure_prop_sphere_on_grip():
    """Freebird puts the proportional-editing sphere on the pointer tip (index finger);
    vertices are grabbed with the grip sphere now, so show the falloff around the grip."""
    node = _prop_sphere()
    if node is None or "update" in vars(node):
        return
    orig = type(node).update

    def update():
        orig(node)
        try:
            from bl_xr import xr_session

            from .grab import grab_center

            if node.sphere.style.get("visible", False):
                node.position = grab_center()
                node.rotation = xr_session.controller_main_grip_rotation
        except Exception:
            pass

    node.update = update


def _restore_prop_sphere():
    node = _prop_sphere()
    if node is not None and "update" in vars(node):
        del node.update


def uninstall_hooks():
    from bl_xr import root

    _restore_prop_sphere()

    for owner, event, cb, opts, marker in _patched:
        entries = getattr(owner, "event_listeners", {}).get(event, [])
        for i, (l, o) in enumerate(entries):
            if l == cb and o.get(marker):
                entries[i] = (l, opts)
    _patched.clear()
    for event, cb in _added:
        root.remove_event_listener(event, cb)
    _added.clear()
