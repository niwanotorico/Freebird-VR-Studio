# SPDX-License-Identifier: GPL-2.0-or-later
"""Edit Mode helpers (LOCAL: your mode and select mode; the mesh edits themselves sync as usual).

Uses Freebird's own functions (set_mode, set_tool, the main menu's VERT / EDGE / FACE and
proportional-edit toggles), so behaviour and undo steps match Freebird's menu buttons.
Leaving Edit Mode puts back the tool you had before (the pen is not usable in Edit Mode).
"""

import bpy

SELECT_MODES = ("VERT", "EDGE", "FACE")
_prev_tool = {"name": None}


def active():
    return bpy.context.view_layer.objects.active


def current_mode():
    return getattr(active(), "mode", "OBJECT")


def mesh_select_mode():
    v, e, f = bpy.context.scene.tool_settings.mesh_select_mode
    return "VERT" if v else "EDGE" if e else "FACE"


def _editable_active():
    """The active object, or (for a VR group) its first mesh member."""
    from .groups import is_group, with_descendants

    ob = active()
    if ob is not None and is_group(ob):
        mesh = next((m for m in with_descendants([ob])[1:] if m.type == "MESH"), None)
        if mesh is not None:
            bpy.context.view_layer.objects.active = mesh
            mesh.select_set(True)
            ob = mesh
    return ob


def set_mode(mode):
    """OBJECT / EDIT / POSE. Returns a short message."""
    from freebird import tools
    from freebird.utils import set_mode as fb_set_mode, set_tool

    ob = _editable_active() if mode != "OBJECT" else active()
    if ob is None:
        return "Select an object first"
    if mode == "EDIT" and ob.type not in ("MESH", "CURVE", "ARMATURE"):
        return f"{ob.type.title()} has no Edit Mode"
    if mode == "POSE" and ob.type != "ARMATURE":
        return "Pose Mode: armatures only"
    if ob.mode == mode:
        return f"Already {mode.title()}"
    if ob.mode == "OBJECT":
        _prev_tool["name"] = tools.active_tool
    if mode != "OBJECT":
        set_tool("select")
    if not fb_set_mode(mode):
        return f"Can't switch to {mode.title()}"
    if mode == "OBJECT":
        set_tool(_prev_tool["name"] or "select")  # back to the pen (or whatever you had)
        _prev_tool["name"] = None
    return f"{mode.title()} Mode"


def toggle_mode():
    return set_mode("OBJECT" if current_mode() != "OBJECT" else "EDIT")


def set_select_mode(kind):
    if current_mode() != "EDIT" or getattr(active(), "type", None) != "MESH":
        return "Mesh Edit Mode only"
    from freebird.ui.main_menu import set_edit_type

    set_edit_type(kind)
    return kind.title()


def step_select_mode(direction):
    i = SELECT_MODES.index(mesh_select_mode())
    return set_select_mode(SELECT_MODES[(i + direction) % len(SELECT_MODES)])


def proportional():
    return bpy.context.scene.tool_settings.use_proportional_edit


def toggle_proportional():
    from freebird.ui.main_menu import toggle_proportional_edit

    toggle_proportional_edit()
    return f"Proportional {'ON' if proportional() else 'OFF'}"


# -- proportional editing size (slider) ------------------------------------------
FALLOFF_MIN, FALLOFF_MAX = 0.01, 10.0  # Blender units, log scale on the slider


def _prop_attr(ts):
    return "proportional_distance" if hasattr(ts, "proportional_distance") else "proportional_size"


def falloff():
    ts = bpy.context.scene.tool_settings
    return getattr(ts, _prop_attr(ts))


def set_falloff(value):
    ts = bpy.context.scene.tool_settings
    setattr(ts, _prop_attr(ts), max(FALLOFF_MIN, min(FALLOFF_MAX, value)))


def slider_value(t):
    """0..1 -> falloff (log)"""
    return FALLOFF_MIN * (FALLOFF_MAX / FALLOFF_MIN) ** t


def slider_pos(value):
    import math

    value = max(FALLOFF_MIN, min(FALLOFF_MAX, value))
    return math.log(value / FALLOFF_MIN) / math.log(FALLOFF_MAX / FALLOFF_MIN)


def describe_falloff(value):
    return f"{value * 100:.0f} cm" if value < 1 else f"{value:.2f} m"
