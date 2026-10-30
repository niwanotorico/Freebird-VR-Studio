# SPDX-License-Identifier: GPL-2.0-or-later
"""
Puddinger VR (formerly "VR Studio"): "Blender is powerful but hard in VR" -> "in VR you just touch it".

A Freebird XR plugin (folder plugin). Install by copying the whole `vr_studio` folder to
    ~/.freebird/plugins/vr_studio/      (C:\\Users\\<you>\\.freebird\\plugins\\vr_studio)
and restarting Blender (Freebird loads plugins when it starts).

Freebird menu -> Plugins (CUSTOM) -> "Color" / "Look" / "View" toggle their panels in the VR Studio
area, right next to the main menu on the left hand (on the side Freebird's sub-menus open).
    COLOR  32 colours.   Select objects, point at a colour, pull the trigger: done.
           The colour (and LOOK) you pick is also your pen's: what you draw next comes out in it.
    LOOK   8 materials (Clay / Matte / Glossy / Plastic / Metallic / Glass / Emission / Toon).
           Independent of Color: blue + Matte -> blue + Metallic keeps the blue, and a new
           colour keeps the Look.
    VIEW   the headset's shading: Wireframe / Solid / Material Preview / Rendered.
           Only this person's view (never synced to the collab room).
           Controller: Normal / See-through (Freebird's controller card faint and drawn without
           depth, so the grab sphere and things behind it show through). Also just you.
    GRAB   Gravity Sketch style grab: a sphere on your hand (middle finger), always shown,
           red when a squeeze would grab. Reach OFF (Freebird's 1 cm tip) / 3 / 5 / 8 cm.
           Everything the sphere touches is grabbed together and stays selected after you let
           go (hand deep inside a big object grabs that one). Just you (LOCAL).
           Offset row (Axis / - / + / Reset, 0.5 cm steps) moves the sphere on the hand, to put
           it on the middle finger; grabbing, vertex grab and the proportional sphere follow.
    DELETE squeeze to hold something + B = delete it (Gravity Sketch). Empty hand + B is
           Freebird's quick tools as before. Undo brings it back.
    COPY   squeeze to hold something + trigger = duplicate it (Freebird's clone; the copy stays
           in your hand). Freebird's A button still clones too.
    BUTTONS Gravity Sketch style: B = undo (holding something: delete), A = COLOR panel,
           X tap = group, right stick up/down = grab sphere size. Controller icons match.
    OUTLINE what the grab sphere touches (or what you hold) gets a red outline. Just you.
    GROUP  left X tap: 2+ selected (or held) -> group (an Empty "VRGroup" parent); a group ->
           ungroup. Grabbing a member grabs the whole group. Holding X is still Freebird's
           "select while held".
    EDIT   Object / Edit / Pose Mode (leaving Edit Mode brings your pen back), Vert / Edge /
           Face, proportional editing on / off. In Edit Mode the grab sphere grabs vertices.
    PICKER any colour (hue x lightness map + saturation strip) and an eyedropper: Pick, then
           touch something with the grab sphere; its colour becomes the pen's / current colour.
    PLAY   Puddinger behaviours. Jiggle: selected / held things become jiggly; bump them with
           the grab sphere or move them and they wobble (each Blender draws its own wobble).
Section headers show GLOBAL (synced to the room) or LOCAL (just you).
Undo / Redo are Freebird's own (left joystick / controller buttons).

Independent of the freebird_collab add-on: it only edits Blender materials, and the
collab material + node tree sync (when a room is open) carries the change to everyone.
"""

import os

# Shown name renamed from "VR Studio" (v0.5.2). The folder / PLUGIN_ID stay "vr_studio" so existing installs,
# ~/.freebird/vr_studio_settings.json and room sync keep working.
fb_info = {"name": "Puddinger VR", "version": (0, 5, 2)}

PLUGIN_ID = "vr_studio"
ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")

# launcher button id, label, icon, section class (module, name). Order = bottom-to-top in the area.
SECTIONS = [
    ("color", "Color", "color.png", ("color_section", "ColorSection")),
    ("picker", "Picker", "picker.png", ("picker_section", "PickerSection")),
    ("look", "Look", "look.png", ("look_section", "LookSection")),
    ("view", "View", "view.png", ("view_section", "ViewSection")),
    ("grab", "Grab", "grab.png", ("grab_section", "GrabSection")),
    ("edit", "Edit", "edit.png", ("edit_section", "EditSection")),
    ("play", "Pudding", "play.png", ("play_section", "PlaySection")),
]

_area = None
_sections = {}


def _build():
    """Build the area and its sections. Called at VR start (Freebird builds its own menus then too;
    thumbnails must not be loaded from an application timer)."""
    global _area
    if _area is not None:
        return _area
    import importlib

    from .area import StudioArea

    area = StudioArea()
    for button_id, _label, _icon, (mod_name, cls_name) in SECTIONS:
        try:
            mod = importlib.import_module(f".{mod_name}", __name__)
            _sections[button_id] = area.add(getattr(mod, cls_name)())
        except Exception as e:
            import traceback

            print(f"[vr_studio] could not build {cls_name}: {e}\n{traceback.format_exc()}")
    _area = area
    return area


def _toggler(button_id):
    def toggle():
        area = _build()
        area.attach()
        section = _sections.get(button_id)
        if section is not None:
            area.toggle(section)

    return toggle


def _on_xr_start(self, event_name, event):
    _build().attach()  # sections stay hidden until their button is pressed
    _grab_sphere(True)
    _controller_look()


def _controller_look(restore=False):
    try:
        from . import controller_look

        controller_look.restore() if restore else controller_look.apply()
    except Exception as e:
        print(f"[vr_studio] controller look: {e}")


def _grab_sphere(state):
    try:
        from . import grab

        grab.show_sphere() if state else grab.hide_sphere()
    except Exception as e:
        print(f"[vr_studio] grab sphere: {e}")


def _on_xr_end(self, event_name, event):
    _grab_sphere(False)
    if _area is not None:
        _area.detach()


def _icon(name):
    p = os.path.join(ICON_DIR, name)
    return p if os.path.exists(p) else None


def _bridge_timer():
    """Hook the FreebirdCollabo session (groups + pudding ride on the room). In or out of VR."""
    try:
        from . import collab_bridge

        collab_bridge.ensure()
    except Exception as e:
        print(f"[vr_studio] collab bridge: {e}")
    return 1.0


def register():
    import bpy
    from bl_xr import root, xr_session

    if not bpy.app.timers.is_registered(_bridge_timer):
        bpy.app.timers.register(_bridge_timer, first_interval=1.0, persistent=True)
    from freebird.api import add_launcher_button

    try:
        from . import controls

        controls._color_toggle = _toggler("color")  # right A = COLOR (Gravity Sketch)
    except Exception as e:
        print(f"[vr_studio] controls: {e}")

    for button_id, label, icon, _cls in SECTIONS:
        add_launcher_button(PLUGIN_ID, button_id, label, _toggler(button_id), _icon(icon))
    root.add_event_listener("fb.xr_start", _on_xr_start)
    root.add_event_listener("fb.xr_end", _on_xr_end)
    try:
        from . import grab

        grab.install()
    except Exception as e:
        print(f"[vr_studio] easy grab not installed: {e}")
    try:
        if xr_session.is_running:  # plugin (re)loaded while already in VR
            _build().attach()
            _grab_sphere(True)
            _controller_look()
    except Exception:
        pass


def unregister():
    global _area
    import bpy
    from bl_xr import root

    if bpy.app.timers.is_registered(_bridge_timer):
        bpy.app.timers.unregister(_bridge_timer)
    try:
        from . import collab_bridge

        collab_bridge.uninstall()
    except Exception:
        pass
    from freebird.api import remove_launcher_button

    for button_id, *_ in SECTIONS:
        remove_launcher_button(PLUGIN_ID, button_id)
    root.remove_event_listener("fb.xr_start", _on_xr_start)
    root.remove_event_listener("fb.xr_end", _on_xr_end)
    try:
        from . import grab

        grab.uninstall()
        grab.hide_sphere()
    except Exception:
        pass
    _controller_look(restore=True)
    if _area is not None:
        _area.detach()
    _area = None
    _sections.clear()
