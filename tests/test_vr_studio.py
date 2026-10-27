# SPDX-License-Identifier: GPL-2.0-or-later
"""
VR Studio (freebird_plugin/vr_studio) test: one-press colour, no VR needed.

    python3 tests/test_vr_studio.py unit           # colour logic on Blender data (single process)
    python3 tests/test_vr_studio.py ui             # unit, then the bl_xr panel: raycast a swatch, press it (needs Freebird's
                                                   #   files, FREEBIRD_XR_DIR=<...>/scripts/addons/freebird_xr; skipped if missing)

Without the bpy module, run it through Blender:
    blender --background --factory-startup --python tests/blender_runner.py -- tests/test_vr_studio.py ui

The two-instance sync test (direct / relay) lives in FreebirdCollabo, next to its collab test harness.
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "freebird_plugin"))


def _lin(hex_str):
    from vr_studio.palette import hex_to_srgb, srgb_to_linear

    return srgb_to_linear(hex_to_srgb(hex_str))


def _r3(v):
    return tuple(round(x, 3) for x in v)


def _base(mat):
    from vr_studio.materials import _principled

    return _r3(_principled(mat).inputs["Base Color"].default_value)


# ----------------------------------------------------------------------
def run_unit():
    import bpy
    from vr_studio import materials, palette

    assert len(palette.PALETTE) == 32 and len(palette.swatches()) == 32
    assert _r3(_lin("#FFFFFF")) == (1.0, 1.0, 1.0) and _r3(_lin("#000000")) == (0.0, 0.0, 0.0)
    assert abs(palette.srgb_to_linear((0.5,))[0] - 0.214) < 0.001, "sRGB -> linear"
    # Picker: linear -> sRGB is the inverse, hex for the readout
    for c in ((0.0, 0.5, 1.0), (0.002, 0.2, 0.8)):
        assert _r3(palette.linear_to_srgb(palette.srgb_to_linear(c))) == _r3(c)
    assert palette.srgb_hex((1.0, 0.5, 0.0)) == "#FF8000" and palette.srgb_hex((2.0, -1.0, 0.0, 1.0)) == "#FF0000"

    red, blue, green = _lin("#E53935"), _lin("#1E88E5"), _lin("#43A047")
    cube = bpy.data.objects["Cube"]
    cube.data.materials.clear()

    # nothing selected: nothing happens
    for ob in bpy.context.view_layer.objects:
        ob.select_set(False)
    rep = materials.apply_color(materials.selected_targets(), red)
    assert rep["objects"] == [] and materials.describe(rep) == "Select an object first"

    # 1. object without material -> new "VR Cube", Base Color + Solid colour set
    cube.select_set(True)
    targets = materials.selected_targets()
    assert targets == [cube], targets  # camera / light are never targets
    rep = materials.apply_color(targets, red)
    assert rep["created"] == ["VR Cube"], rep
    mat = cube.material_slots[0].material
    assert mat.name == "VR Cube" and _base(mat) == _r3((*red, 1.0)) and _r3(mat.diffuse_color) == _r3((*red, 1.0))
    assert _r3(mat[materials.COLOR_PROP]) == _r3(red)

    # 2. pressing another colour edits the same material (no material spam)
    n = len(bpy.data.materials)
    materials.apply_color([cube], blue)
    assert len(bpy.data.materials) == n and _base(cube.material_slots[0].material) == _r3((*blue, 1.0))

    # 3. material shared with an UNSELECTED object -> copy-on-write, the other keeps its colour
    bpy.ops.mesh.primitive_uv_sphere_add(location=(3, 0, 0))
    sphere = bpy.context.active_object
    sphere.data.materials.append(mat)
    for ob in bpy.context.view_layer.objects:
        ob.select_set(ob == sphere)
    rep = materials.apply_color(materials.selected_targets(), green)
    assert len(rep["copied"]) == 1 and rep["copied"][0] == f"VR {sphere.name}", rep
    assert sphere.material_slots[0].material != mat and _base(sphere.material_slots[0].material) == _r3((*green, 1.0))
    assert _base(mat) == _r3((*blue, 1.0)), "the unselected cube must keep its colour"

    # 4. shared material, ALL its users selected -> edited in place, still shared
    shared = bpy.data.materials.new("Shared")
    for ob in (cube, sphere):
        ob.data.materials.clear()
        ob.data.materials.append(shared)
        ob.select_set(True)
    n = len(bpy.data.materials)
    rep = materials.apply_color(materials.selected_targets(), red)
    assert rep["edited"] == ["Shared"] and len(bpy.data.materials) == n, rep
    assert cube.material_slots[0].material == sphere.material_slots[0].material == shared

    # 5. several slots: every slot painted
    cube.data.materials.clear()
    cube.data.materials.append(bpy.data.materials.new("A"))
    cube.data.materials.append(bpy.data.materials.new("B"))
    materials.apply_color([cube], blue)
    assert [_base(s.material) for s in cube.material_slots] == [_r3((*blue, 1.0))] * 2

    # 6. a texture on Base Color is unplugged (image node kept) so the colour shows
    tex_mat = bpy.data.materials.new("Textured")
    materials._ensure_principled(tex_mat)
    tree = tex_mat.node_tree
    img_node = tree.nodes.new("ShaderNodeTexImage")
    img_node.image = bpy.data.images.new("T", 4, 4)
    tree.links.new(img_node.outputs["Color"], materials._principled(tex_mat).inputs["Base Color"])
    cube.data.materials.clear()
    cube.data.materials.append(tex_mat)
    for ob in bpy.context.view_layer.objects:
        ob.select_set(ob == cube)
    rep = materials.apply_color(materials.selected_targets(), green)
    assert rep["unplugged"] == ["Textured"], rep
    assert not materials._principled(tex_mat).inputs["Base Color"].is_linked and img_node.name in tree.nodes
    assert "texture unplugged" in materials.describe(rep)

    # 7. a material without a Principled BSDF: its shader's Color is set (tree left as it is)
    emit = bpy.data.materials.new("Glow")
    materials._ensure_node_tree(emit)
    t = emit.node_tree
    t.nodes.clear()
    e = t.nodes.new("ShaderNodeEmission")
    o = t.nodes.new("ShaderNodeOutputMaterial")
    t.links.new(e.outputs[0], o.inputs["Surface"])
    materials.set_material_color(emit, red)
    assert _r3(e.inputs["Color"].default_value) == _r3((*red, 1.0)) and len(t.nodes) == 2

    # 8. Grease Pencil material: stroke + fill colour
    gp = bpy.data.materials.new("GP")
    bpy.data.materials.create_gpencil_data(gp)
    materials.set_material_color(gp, blue)
    assert _r3(gp.grease_pencil.color[:3]) == _r3(blue) and _r3(gp.grease_pencil.fill_color[:3]) == _r3(blue)

    # 9. curves (Freebird pen / pipe strokes are curve objects) are paintable
    cu = bpy.data.curves.new("Stroke", "CURVE")
    cob = bpy.data.objects.new("Stroke", cu)
    bpy.context.scene.collection.objects.link(cob)
    rep = materials.apply_color([cob], red)
    assert rep["created"] == ["VR Stroke"] and _base(cob.material_slots[0].material) == _r3((*red, 1.0))

    run_unit_looks()
    print("=== VR STUDIO UNIT: PASS ===")


def _inp(mat, name):
    from vr_studio.materials import _principled

    v = _principled(mat).inputs[name].default_value
    return round(v, 3) if isinstance(v, float) else _r3(v)


def run_unit_looks():
    import bpy
    from vr_studio import looks, materials

    blue, red = _lin("#1E88E5"), _lin("#E53935")
    bpy.ops.mesh.primitive_cube_add(location=(0, 5, 0))
    ob = bpy.context.active_object
    ob.name = "LookBox"
    ob.data.materials.clear()

    # a Look on an object without material creates one; every Look is recognised again
    rep = materials.apply_look([ob], "Matte")
    mat = ob.material_slots[0].material
    assert rep["created"] == ["VR LookBox"] and materials.detect_look(mat) == "Matte"
    for name in looks.LOOK_NAMES:
        materials.apply_look([ob], name)
        assert materials.detect_look(mat) == name, (name, materials.detect_look(mat))

    # Color and Look are independent, in both orders
    materials.apply_color([ob], blue)
    for name in looks.LOOK_NAMES:
        materials.apply_look([ob], name)
        assert _base(mat) == _r3((*blue, 1.0)), name  # the colour survives every Look
        assert _r3(mat.diffuse_color[:3]) == _r3(blue)
    materials.apply_look([ob], "Glass")
    materials.apply_color([ob], red)
    assert materials.detect_look(mat) == "Glass" and _inp(mat, "Transmission Weight") == 1.0
    assert round(mat.diffuse_color[3], 2) == 0.35 and mat.use_raytrace_refraction  # see-through in Solid mode
    materials.apply_look([ob], "Matte")  # nothing of Glass is left behind
    assert _inp(mat, "Transmission Weight") == 0.0 and mat.diffuse_color[3] == 1.0 and not mat.use_raytrace_refraction
    assert _base(mat) == _r3((*red, 1.0))

    # Emission glows in the current colour, and follows a later colour change
    materials.apply_look([ob], "Emission")
    assert _inp(mat, "Emission Strength") == looks.EMISSION_STRENGTH and _inp(mat, "Emission Color") == _r3((*red, 1.0))
    materials.apply_color([ob], blue)
    assert _inp(mat, "Emission Color") == _r3((*blue, 1.0))
    materials.apply_look([ob], "Plastic")
    assert _inp(mat, "Emission Strength") == 0.0

    # Toon: its own node chain feeds the output, Principled kept (unplugged) as the colour holder
    materials.apply_look([ob], "Toon")
    tree = mat.node_tree
    out = next(n for n in tree.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output)
    assert out.inputs["Surface"].links[0].from_node.name == looks.TOON_PREFIX + "Emit"
    tint = tree.nodes[looks.TOON_PREFIX + "Tint"]
    b_col = next(s for s in tint.inputs if s.identifier == "B_Color")
    assert _r3(b_col.default_value) == _r3((*blue, 1.0))
    materials.apply_color([ob], red)  # a colour change reaches the toon tint
    assert _r3(b_col.default_value) == _r3((*red, 1.0)) and materials.detect_look(mat) == "Toon"
    ramp = tree.nodes[looks.TOON_PREFIX + "Bands"].color_ramp
    assert ramp.interpolation == "CONSTANT" and len(ramp.elements) == 3
    materials.apply_look([ob], "Clay")  # leaving Toon removes its nodes and plugs the Principled back in
    assert not any(n.name.startswith(looks.TOON_PREFIX) for n in tree.nodes)
    assert out.inputs["Surface"].links[0].from_node.type == "BSDF_PRINCIPLED" and _base(mat) == _r3((*red, 1.0))

    # a texture driving Roughness wins over the Look (only unplugged sockets are written)
    img = tree.nodes.new("ShaderNodeTexImage")
    tree.links.new(img.outputs["Color"], materials._principled(mat).inputs["Roughness"])
    materials.apply_look([ob], "Glossy")
    assert materials._principled(mat).inputs["Roughness"].is_linked and _inp(mat, "Coat Weight") == 1.0

    # a material built around another shader becomes a Principled material with that colour
    odd = bpy.data.materials.new("OnlyEmission")
    materials._ensure_node_tree(odd)
    t = odd.node_tree
    t.nodes.clear()
    e = t.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (*blue, 1.0)
    o = t.nodes.new("ShaderNodeOutputMaterial")
    t.links.new(e.outputs[0], o.inputs["Surface"])
    materials.set_material_look(odd, "Metallic")
    assert materials.detect_look(odd) == "Metallic" and _base(odd) == _r3((*blue, 1.0))
    assert o.inputs["Surface"].links[0].from_node.type == "BSDF_PRINCIPLED"

    # copy-on-write applies to Looks too
    bpy.ops.mesh.primitive_cube_add(location=(0, 8, 0))
    other = bpy.context.active_object
    other.data.materials.append(mat)
    rep = materials.apply_look([other], "Metallic")
    assert len(rep["copied"]) == 1 and materials.detect_look(mat) == "Glossy"
    # Grease Pencil materials keep their colour-only behaviour
    gp = bpy.data.materials.new("GPL")
    bpy.data.materials.create_gpencil_data(gp)
    assert materials.set_material_look(gp, "Metallic") is False


# ----------------------------------------------------------------------
def _freebird_dir():
    d = os.environ.get("FREEBIRD_XR_DIR")
    if d:
        return d
    d = os.path.expanduser("~/AppData/Roaming/Blender Foundation/Blender/5.2/scripts/addons/freebird_xr")
    if os.path.isdir(os.path.join(d, "bl_xr")):
        return d
    return None


def run_ui():
    """Build the real Studio area with Freebird's own UI code (bl_xr + Freebird's main menu),
    check where it sits next to the main menu, raycast tiles like the laser does, press them."""
    fb = _freebird_dir()
    if fb is None:
        print("=== VR STUDIO UI: SKIPPED (set FREEBIRD_XR_DIR to Freebird's freebird_xr folder) ===")
        return
    sys.path.insert(0, fb)
    import bpy
    from mathutils import Vector

    import bl_xr
    from bl_xr import Image
    from bl_xr.utils import raycast

    Image.base_dir = fb
    import freebird  # noqa: F401  (registers Freebird's settings the main menu reads)
    from freebird.ui import main_menu as mm

    import tempfile

    from vr_studio import area as area_mod
    from vr_studio import grab, materials
    from vr_studio.area import SIDE_GAP, StudioArea
    from vr_studio.color_section import SWATCH, ColorSection
    from vr_studio.look_section import TILE, LookSection

    # never read / write this PC's ~/.freebird/vr_studio_settings.json: a panel layout arranged
    # in VR there (COLOR in another column ...) would move the panels this test measures
    settings = os.path.join(tempfile.mkdtemp(), "vr_studio_settings.json")
    area_mod.LAYOUT_PATH = grab.SETTINGS_PATH = settings

    for ob in bpy.context.view_layer.objects:
        ob.select_set(ob.name == "Cube")
    bpy.context.view_layer.objects.active = bpy.data.objects["Cube"]
    bpy.data.objects["Cube"].data.materials.clear()

    area = StudioArea()
    color = area.add(ColorSection())
    look = area.add(LookSection())
    area.attach()
    assert area.node.parent is bl_xr.root and not color.node.style["visible"]
    area.toggle(color)
    area.toggle(look)
    assert color.visible and look.visible and len(color.tiles) == 32 and len(look.tiles) == 8
    # stacking: Color at the bottom, Look right above it
    assert color.node.position.y == 0 and abs(look.node.position.y - (color.height + 0.006)) < 1e-6

    # placement: RIGHT of Freebird's main menu (right-handed), bottom-aligned, slides past an open sub-menu
    for sub in list(mm.submenus.values()) + [mm.submenu_custom, mm.mirror_panel]:
        sub.style["visible"] = False
    left, right, bottom, others = area._menu_space()
    assert (round(left, 3), round(right, 3), round(bottom, 3)) == (0.0, 0.08, 0.051), (left, right, bottom)
    x = area._target_x(left, right, bottom, others)
    assert abs(x - (0.08 + SIDE_GAP)) < 1e-6, x
    mm.submenus["PEN"].style["visible"] = True  # Freebird's pen options open on the right
    x2 = area._target_x(*area._menu_space())
    assert abs(x2 - (0.2 + SIDE_GAP)) < 1e-4, x2
    mm.submenus["PEN"].style["visible"] = False
    mm.submenus["SELECT"].style["visible"] = True  # select options open on the LEFT: no need to move
    assert abs(area._target_x(*area._menu_space()) - x) < 1e-6
    mm.submenus["SELECT"].style["visible"] = False
    bl_xr.main_hand = "left"  # left-handed: mirrored, the area goes to the left of the menu
    assert area._target_x(*area._menu_space()) < 0
    bl_xr.main_hand = "right"

    def hit(tile, size):
        c = tile.local_to_world_point(Vector((size / 2, size / 2, 0)))
        node, _, _ = raycast(c + Vector((0, 0, 0.5)), Vector((0, 0, -1)), object_raycast=False, ui_raycast=True)
        return node

    yellow = color.tiles[18]
    assert yellow.label == "Yellow" and hit(yellow, SWATCH) is yellow
    metal = look.tiles[4]
    assert metal.look == "Metallic" and hit(metal, TILE) is metal, hit(metal, TILE)

    # Color, then Look, then Color: each keeps the other
    yellow.dispatch_event("pointer_main_enter", None)
    assert color.status.text == "Yellow" and "border" in yellow.style
    yellow.dispatch_event("pointer_main_press_end", None)
    yellow.dispatch_event("pointer_main_leave", None)
    mat = bpy.data.objects["Cube"].material_slots[0].material
    assert mat.name == "VR Cube" and _base(mat) == _r3((*yellow.linear, 1.0))
    assert color.last_message == "1 object, 1 new", color.last_message
    metal.dispatch_event("pointer_main_press_end", None)
    assert materials.detect_look(mat) == "Metallic" and _base(mat) == _r3((*yellow.linear, 1.0))
    area._refresh()
    assert metal.current and yellow.current and not look.tiles[0].current
    blue = color.tiles[21]
    blue.dispatch_event("pointer_main_press_end", None)
    assert materials.detect_look(mat) == "Metallic" and _base(mat) == _r3((*blue.linear, 1.0))
    area._refresh()
    assert blue.current and not yellow.current and metal.current

    # Flat / Smooth (bottom row of LOOK): shades the selected Cube, the tile follows the state
    flat, smooth = look.shade_tiles
    assert flat.shade == "FLAT" and smooth.shade == "SMOOTH" and hit(smooth, TILE) is smooth
    cube_me = bpy.data.objects["Cube"].data
    smooth.dispatch_event("pointer_main_press_end", None)
    assert all(p.use_smooth for p in cube_me.polygons) and look.last_message == "Smooth: 1 object", look.last_message
    area._refresh()
    assert smooth.current and not flat.current
    flat.dispatch_event("pointer_main_press_end", None)
    assert not any(p.use_smooth for p in cube_me.polygons)
    area._refresh()
    assert flat.current and not smooth.current and metal.current

    # VIEW: the headset's shading (XR session settings), not the desktop viewport's
    from vr_studio import view
    from vr_studio.view_section import ViewSection

    vs = area.add(ViewSection())
    area.toggle(vs)
    assert abs(vs.node.position.y - (color.height + look.height + 2 * 0.006)) < 1e-6  # stacked on top
    xr_shading = bpy.context.window_manager.xr_session_settings.shading
    desktop = [sp.shading.type for sc in bpy.data.screens for a in sc.areas if a.type == "VIEW_3D" for sp in a.spaces
               if sp.type == "VIEW_3D"]
    n_undo = len(bpy.data.materials)
    for tile, mode in zip(vs.tiles, ("WIREFRAME", "SOLID", "MATERIAL", "RENDERED")):
        assert hit(tile, TILE) is tile
        tile.dispatch_event("pointer_main_press_end", None)
        assert xr_shading.type == mode and view.get_vr_shading() == mode, (xr_shading.type, mode)
        area._refresh()
        assert [t.current for t in vs.tiles] == [t is tile for t in vs.tiles]
    assert vs.last_message.startswith("Rendered - very heavy in VR (") and vs.last_message.endswith(")"), \
        vs.last_message  # warns it is heavy and names the render engine
    after = [sp.shading.type for sc in bpy.data.screens for a in sc.areas if a.type == "VIEW_3D" for sp in a.spaces
             if sp.type == "VIEW_3D"]
    assert after == desktop, "the desktop 3D Viewport must keep its own shading"
    assert len(bpy.data.materials) == n_undo
    xr_shading.type = "SOLID"
    area._refresh()
    assert vs.tiles[1].current and not vs.tiles[3].current  # follows changes made elsewhere too

    # nothing selected -> only the pen's look changes, nothing created
    for ob in bpy.context.view_layer.objects:
        ob.select_set(False)
    n = len(bpy.data.materials)
    look.tiles[0].dispatch_event("pointer_main_press_end", None)
    assert look.last_message.startswith("Pen: ") and len(bpy.data.materials) == n, look.last_message

    _check_controller_look_and_offset(area, vs, hit)
    _check_picker(area, hit)

    # the plugin entry builds the same area with both sections
    import vr_studio

    vr_studio._on_xr_start(None, "fb.xr_start", None)
    assert set(vr_studio._sections) == {"color", "picker", "look", "view", "grab", "edit", "play"} and vr_studio._area.node.parent is bl_xr.root
    vr_studio._on_xr_end(None, "fb.xr_end", None)
    assert vr_studio._area.node.parent is None
    area.detach()
    print("=== VR STUDIO UI: PASS ===")


def _check_controller_look_and_offset(area, vs, hit):
    """VIEW: controller card Normal / See-through. GRAB: grab sphere offset. Settings go to a temp file."""
    import json
    import tempfile

    from bl_xr import Image, root, xr_session
    from mathutils import Quaternion, Vector

    from vr_studio import controller_look, grab
    from vr_studio.grab_section import GrabSection
    from vr_studio.look_section import TILE

    real_path = grab.SETTINGS_PATH
    grab.SETTINGS_PATH = os.path.join(tempfile.mkdtemp(), "vr_studio_settings.json")
    added = []
    try:
        # the cards may not exist in this test (Freebird's VR UI not enabled): stand-ins with the same ids
        cards = {}
        for node_id in controller_look.CARD_IDS:
            node = root.q(f"#{node_id}")
            if node is None:
                node = Image(id=node_id, width=0.1, height=0.1, intersects=None)
                root.append_child(node)
                added.append(node)
            cards[node_id] = node
        main = cards["controller_main_bg"]
        main.style["opacity"] = 0.7  # an inline value that must come back
        controller_look._see_through = None
        assert controller_look.get_see_through() is False

        tile = vs.controller_tile
        assert hit(tile, TILE) is tile
        tile.dispatch_event("pointer_main_press_end", None)
        assert vs.last_message == "Controller: See-through", vs.last_message
        for node in cards.values():
            assert node.get_computed_style("opacity") == 0.2 and node.get_computed_style("depth_test", True) is False
        assert tile.current and vs.controller_state.text == "See"
        assert json.load(open(grab.SETTINGS_PATH))["controller_see_through"] is True
        # left-handed switch swaps the textures between the cards, the look stays on both
        controller_look.apply()
        assert all(n.style["opacity"] == 0.2 for n in cards.values())
        tile.dispatch_event("pointer_main_press_end", None)
        assert vs.last_message == "Controller: Normal" and not tile.current
        assert main.style["opacity"] == 0.7 and "depth_test" not in main.style
        assert all("opacity" not in n.style for n in added if n is not main)
        # no cards at all: nothing happens, no error
        for node in added:
            root.remove_child(node)
        assert controller_look.set_see_through(True, save=False) == 0
        controller_look.set_see_through(False, save=False)

        # GRAB offset: nothing saved -> the middle-finger default; 0 = the grip pose, as before
        gs = area.add(GrabSection())
        grab._offset_cm = None
        assert grab.get_offset_cm() == grab.DEFAULT_OFFSET_CM == (-1.5, 2.0, -0.5)
        grab.set_offset_cm((0, 0, 0), save=False)
        grip = Vector((1.0, 2.0, 3.0))
        rot = Quaternion((0, 0, 1), 1.5707963)  # 90 degrees about Z: grip X -> world Y
        cls = type(xr_session)
        saved_props = {k: cls.__dict__[k] for k in ("controller_main_grip_position", "controller_main_grip_rotation",
                                                      "viewer_scale")}
        cls.controller_main_grip_position = property(lambda self: grip.copy())
        cls.controller_main_grip_rotation = property(lambda self: rot.copy())
        cls.viewer_scale = property(lambda self: 10.0)
        try:
            assert (grab.grab_center() - grip).length < 1e-6
            axis, minus, plus, zero = gs.offset_tiles
            plus.dispatch_event("pointer_main_press_end", None)
            plus.dispatch_event("pointer_main_press_end", None)  # X +1 cm
            axis.dispatch_event("pointer_main_press_end", None)
            axis.dispatch_event("pointer_main_press_end", None)
            minus.dispatch_event("pointer_main_press_end", None)  # Z -0.5 cm
            assert grab.get_offset_cm() == (1.0, 0.0, -0.5), grab.get_offset_cm()
            assert gs.last_message == "Z axis: x+1.0 y+0.0 z-0.5 cm", gs.last_message
            assert json.load(open(grab.SETTINGS_PATH))["grab_offset_cm"] == [1.0, 0.0, -0.5]
            # world scale 10: 1 cm on grip X -> 0.1 along world Y, -0.5 cm on Z -> -0.05
            d = grab.grab_center() - grip
            assert (d - Vector((0.0, 0.1, -0.05))).length < 1e-5, d
            grab._offset_cm = None  # read back from the file
            assert grab.get_offset_cm() == (1.0, 0.0, -0.5)
            gs.refresh(None)
            assert not zero.current
            zero.dispatch_event("pointer_main_press_end", None)  # Reset = the default, not 0
            assert grab.get_offset_cm() == (-1.5, 2.0, -0.5)
            d = grab.grab_center() - grip  # grip X -> world Y, grip Y -> world -X, Z stays
            assert (d - Vector((-0.2, -0.15, -0.05))).length < 1e-5, d
            gs.refresh(None)
            assert zero.current
            grab.set_offset_cm((99, -99, 0), save=False)
            assert grab.get_offset_cm() == (15.0, -15.0, 0.0)  # clamped
            grab.set_offset_cm((0, 0, 0), save=False)
        finally:
            for k, v in saved_props.items():
                setattr(cls, k, v)
    finally:
        for node in added:
            if node.parent is not None:
                node.parent.remove_child(node)
        grab.SETTINGS_PATH = real_path
        controller_look._see_through = None
        grab._offset_cm = None


def _check_picker(area, hit):
    """PICKER: saturation strip, hue x lightness map (laser drag), eyedropper. Colours selection + pen."""
    import bpy
    from mathutils import Vector

    from vr_studio import brush, picker_section
    from vr_studio.look_section import TILE
    from vr_studio.palette import srgb_to_linear
    from vr_studio.picker_section import L_MAX, L_MIN, STEPS, PickerSection

    ps = area.add(PickerSection())
    area.toggle(ps)
    assert len(ps.strip) == STEPS and ps.hex_text.text == "#FF0000"  # starts at pure red
    assert hit(ps.paint_tile, TILE) is ps.paint_tile and hit(ps.pick_tile, TILE) is ps.pick_tile
    cube = bpy.data.objects["Cube"]
    for ob in bpy.context.view_layer.objects:
        ob.select_set(ob == cube)

    # strip: 0 % saturation = grey, applied to the selection, its object colour and the pen
    ps.strip[0].dispatch_event("pointer_main_press_end", None)
    grey = srgb_to_linear((0.5, 0.5, 0.5))
    assert ps.hex_text.text == "#808080" and _base(cube.material_slots[0].material) == _r3((*grey, 1.0))
    assert _r3(cube.color[:3]) == _r3(grey) and brush.state["color_name"] == "#808080"
    assert ps.last_message.startswith("1 object"), ps.last_message
    assert ps.strip[0].current and not ps.strip[-1].current

    # map: pull the trigger at (u, v) and let go -> hue u, lightness v; coming from grey = full colour
    u, v = 0.5, 0.75
    m = ps.map
    point = ps.node.position + ps.body.position + m.position + Vector((u * m.w, v * m.h, 0.0))
    real = area._pointer_local
    area._pointer_local = lambda: point.copy()
    try:
        m.dispatch_event("pointer_main_press_start", None)
        assert ps.dragging
        m.dispatch_event("pointer_main_press_end", None)
    finally:
        area._pointer_local = real
    assert not ps.dragging and abs(ps.h - u) < 1e-6 and abs(ps.l - (L_MIN + (L_MAX - L_MIN) * v)) < 1e-6 and ps.s == 1.0
    lin = srgb_to_linear(ps.srgb())
    assert _base(cube.material_slots[0].material) == _r3((*lin, 1.0)) and brush.state["color"] == tuple(lin)

    # eyedropper: Pick, then the touched object's colour becomes the current colour + pen (selection unchanged)
    target = bpy.data.objects.new("PickMe", bpy.data.curves.new("PickMe", "CURVE"))
    bpy.context.scene.collection.objects.link(target)
    target.color = (*srgb_to_linear((0.2, 0.4, 0.6)), 1.0)
    assert _r3(picker_section.object_color(target)) == _r3(target.color[:3])  # no material: object colour
    before = _base(cube.material_slots[0].material)
    real_touch = picker_section.touched_object
    touching = [None]
    picker_section.touched_object = lambda: touching[0]
    try:
        ps.pick_tile.dispatch_event("pointer_main_press_end", None)
        assert ps.picking and ps.pick_tile.current
        ps.tick()  # touching nothing: still picking
        assert ps.picking
        touching[0] = target
        ps.tick()
    finally:
        picker_section.touched_object = real_touch
    assert not ps.picking and not ps.pick_tile.current
    assert ps.hex_text.text == "#336699" and brush.state["color_name"] == "#336699", ps.hex_text.text
    assert ps.last_message.startswith("Picked #336699"), ps.last_message
    assert _base(cube.material_slots[0].material) == before  # picking alone paints nothing
    ps.paint_tile.dispatch_event("pointer_main_press_end", None)  # Paint = colour the selection with it
    assert _base(cube.material_slots[0].material) == _r3((*srgb_to_linear((0.2, 0.4, 0.6)), 1.0))
    # a material's colour wins over the object colour
    assert _r3(picker_section.object_color(cube)) == _r3(srgb_to_linear((0.2, 0.4, 0.6)))
    bpy.data.objects.remove(target)
    area.toggle(ps)


def _check_fb_info():
    """Freebird reads fb_info with ast.literal_eval before importing: it must be a plain dict literal."""
    import ast

    path = os.path.join(os.path.dirname(HERE), "freebird_plugin", "vr_studio", "__init__.py")
    tree = ast.parse(open(path, encoding="utf-8").read())
    for st in tree.body:
        if isinstance(st, ast.Assign) and any(getattr(t, "id", None) == "fb_info" for t in st.targets):
            info = ast.literal_eval(st.value)
            assert isinstance(info, dict) and info.get("name"), info
            return info
    raise AssertionError("fb_info missing")


# ----------------------------------------------------------------------
def _args():
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]


def _child(mode, role):
    try:
        import bpy

        blender = bpy.app.binary_path
    except ImportError:
        blender = ""
    if blender:
        # through blender_runner: a failed assert exits 1 (Blender alone would exit 0)
        runner = os.path.join(HERE, "blender_runner.py")
        return [blender, "--background", "--factory-startup", "--python", runner, "--", __file__, mode, role]
    return [sys.executable, __file__, mode, role]


def main():
    args = _args()
    mode = args[0] if args else "unit"
    role = args[1] if len(args) > 1 else None
    if mode not in ("unit", "ui"):
        raise SystemExit(f"unknown mode {mode!r}: use unit | ui")
    if role == "-":
        return run_unit() if mode == "unit" else run_ui()
    print("fb_info:", _check_fb_info())
    for part in ("unit", "ui"):
        rc = subprocess.call(_child(part, "-"))
        if rc:
            sys.exit(rc)
        if part == mode:
            sys.exit(0)


if __name__ == "__main__":
    main()
