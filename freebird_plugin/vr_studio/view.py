# SPDX-License-Identifier: GPL-2.0-or-later
"""VR viewport shading. Only bpy.

What the headset shows is NOT the 3D Viewport's shading: Blender's XR session draws with its
own View3DShading, `WindowManager.xr_session_settings.shading` (the "VR Scene Inspection"
settings). Freebird (v2.15) never changes it (it only sets base scale / pose / controllers /
object extras on the XR session settings), so VR Studio switches that one.

  * the desktop 3D Viewport keeps its own shading (independent, untouched)
  * local to this Blender: it lives on the WindowManager, not the Scene, so FreebirdCollabo
    neither sends it nor receives it (a guest opens the host's scene with load_ui=False,
    which keeps its own WindowManager). A: Solid / B: Material Preview is fine.
  * kept across VR restarts in the same Blender session (and saved with the .blend's UI)
"""

import bpy

MODES = [
    # shading.type, tile label, hover text
    ("WIREFRAME", "Wire", "Wireframe"),
    ("SOLID", "Solid", "Solid"),
    ("MATERIAL", "Material", "Material Preview - heavy in VR"),
    ("RENDERED", "Rendered", "Rendered - very heavy in VR"),
]


def _xr_shading(context=None):
    context = context or bpy.context
    settings = getattr(context.window_manager, "xr_session_settings", None)
    return getattr(settings, "shading", None)


def get_vr_shading(context=None):
    shading = _xr_shading(context)
    return shading.type if shading is not None else None


def set_vr_shading(mode, context=None):
    """Switch what the headset shows. Returns the render engine name for RENDERED (for the status line)."""
    shading = _xr_shading(context)
    if shading is None:
        raise RuntimeError("no XR session settings")
    shading.type = mode
    return (context or bpy.context).scene.render.engine if mode == "RENDERED" else None


# -- VR overlays (floor grid, selection outlines, empties / lights / cameras, annotations) ------
# Freebird's and VR Studio's own VR UI are "custom overlays": never touched here.
OVERLAY_PROPS = ("show_floor", "show_selection", "show_object_extras", "show_annotation")
_saved_overlays = {}


def _xr_settings(context=None):
    context = context or bpy.context
    return getattr(context.window_manager, "xr_session_settings", None)


def overlays_on(context=None):
    st = _xr_settings(context)
    return st is not None and any(getattr(st, p, False) for p in OVERLAY_PROPS)


def toggle_overlays(context=None):
    """All off (remembering what was on) / back to how they were. Returns the new state."""
    st = _xr_settings(context)
    if st is None:
        raise RuntimeError("no XR session settings")
    if overlays_on(context):
        _saved_overlays.clear()
        for p in OVERLAY_PROPS:
            _saved_overlays[p] = getattr(st, p)
            setattr(st, p, False)
        return False
    for p in OVERLAY_PROPS:
        setattr(st, p, _saved_overlays.get(p, True))
    return True
