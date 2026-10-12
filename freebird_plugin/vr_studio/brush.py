# SPDX-License-Identifier: GPL-2.0-or-later
"""Pen colour / look (Gravity Sketch: pick a colour, then draw in it).

The last COLOR / LOOK you pressed becomes the colour / look of everything you draw next with
Freebird's pen, pipe, shapes and hulls. Freebird links every object those tools create with
`link_to_configured_collection`; VR Studio puts a small wrapper around that name in those tool
modules only (not clone, not FreebirdCollabo), so copies and objects arriving from the room are
never recoloured. Until you pick something, Freebird's defaults stay (black pen).
The chosen colour is LOCAL (your pen); the strokes and their materials are GLOBAL as usual.
"""

import sys

TOOL_MODULES = ("freebird.tools.draw_stroke", "freebird.tools.draw_shape", "freebird.tools.draw_hull")

state = {"color": None, "color_name": None, "look": None}
_pending_color = []  # names: Freebird sets ob.color (black pen) right after linking; redo it next frame
_patched = {}  # module name -> original function


def set_color(linear_rgb, name):
    state["color"], state["color_name"] = tuple(linear_rgb), name


def set_look(name):
    state["look"] = name


_recent = []  # strokes to report (pressure check) once the trigger is released


def _apply(ob):
    if state["color"] is None and state["look"] is None:
        return
    from . import materials

    try:
        if state["color"] is not None:
            materials.apply_color([ob], state["color"])
            _pending_color.append(ob.name)
        if state["look"] is not None:
            materials.apply_look([ob], state["look"])
    except Exception as e:
        print(f"[vr_studio] pen colour on {getattr(ob, 'name', ob)}: {e}")


def _wrap(orig):
    def link_to_configured_collection(ob, *args, **kwargs):
        result = orig(ob, *args, **kwargs)
        _apply(ob)
        return result

    link_to_configured_collection._vr_studio_orig = orig
    return link_to_configured_collection


def ensure():
    """Every frame (cheap): wrap the draw tools' link function once they are loaded."""
    for name in TOOL_MODULES:
        mod = sys.modules.get(name)
        fn = getattr(mod, "link_to_configured_collection", None) if mod else None
        if fn is None or hasattr(fn, "_vr_studio_orig"):
            continue
        _patched[name] = fn
        mod.link_to_configured_collection = _wrap(fn)


def _report_pressure():
    """Diagnostics: log how much the thickness varies along each finished stroke."""
    try:
        from bl_xr.events.make_events import controller

        if controller.input_state.get("trigger_main_press", False) or not _recent:
            return
        import bpy

        from .grab import debug

        try:
            from freebird import settings

            flags = f"fixed_thickness={settings['stroke.fixed_thickness']} straight={settings['stroke.straight_line']}"
        except Exception:
            flags = "settings ?"
        for name in _recent:
            ob = bpy.data.objects.get(name)
            if ob is None or not ob.data.splines:
                continue
            radii = [p.radius for sp in ob.data.splines for p in sp.points]
            if radii:
                full = sum(1 for r in radii if r >= 0.95) * 100 // len(radii)
                debug(f"stroke {name}: {len(radii)} pts, radius {min(radii):.2f}..{max(radii):.2f} "
                      f"({full}% at max), bevel {ob.data.bevel_depth:.4f}, {flags}, "
                      f"radii {[round(r, 2) for r in radii]}")
        _recent.clear()
    except Exception as e:
        print(f"[vr_studio] pressure report: {e}")
        _recent.clear()


_known = {"names": None}


def diagnose():
    """Every frame, in both modes (GS on / plain Freebird): notice strokes drawn while the
    trigger is down and log their thickness once it is released."""
    try:
        import bpy
        from bl_xr.events.make_events import controller

        names = {o.name for o in bpy.data.objects if o.type == "CURVE"}
        if _known["names"] is not None and controller.input_state.get("trigger_main_press", False):
            _recent.extend(sorted(names - _known["names"]))
        _known["names"] = names
    except Exception:
        pass
    _report_pressure()


def update():
    """Every frame: give new strokes the solid-view colour too (Freebird set it to black)."""
    if not _pending_color or state["color"] is None:
        _pending_color.clear()
        return
    import bpy

    for name in _pending_color:
        ob = bpy.data.objects.get(name)
        if ob is not None:
            ob.color = (*state["color"], 1.0)
    _pending_color.clear()


def uninstall():
    for name, orig in _patched.items():
        mod = sys.modules.get(name)
        if mod is not None and hasattr(getattr(mod, "link_to_configured_collection", None), "_vr_studio_orig"):
            mod.link_to_configured_collection = orig
    _patched.clear()
