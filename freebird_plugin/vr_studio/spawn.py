# SPDX-License-Identifier: GPL-2.0-or-later
"""New pudding: the Puddinger pudding (Puddinger/01_pudding/create_pudding.py), made right in
the hand. About 18 cm wide and 13 cm tall as you see it (follows the VR world scale), base at the
origin, custard + caramel materials, already jiggly."""

import math

import bpy
from mathutils import Vector

# Puddinger's profile: (radius, height) in metres, bottom to top
PROFILE = [(.072, .002), (.083, .004), (.09, .012), (.091, .023), (.086, .043), (.079, .071), (.073, .102),
           (.070, .119), (.066, .128), (.059, .132), (.042, .134)]
SEGMENTS = 32
CARAMEL_FROM = 7  # rings from here up are caramel


def _material(name, color, roughness):
    m = bpy.data.materials.get(name)
    if m is not None:
        return m
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    bs = m.node_tree.nodes.get("Principled BSDF")
    if bs is not None:
        bs.inputs["Base Color"].default_value = (*color, 1)
        bs.inputs["Roughness"].default_value = roughness
    return m


def _mesh():
    n = SEGMENTS
    verts = []
    for j, (r, z) in enumerate(PROFILE):
        for i in range(n):
            a = 2 * math.pi * i / n
            rr = r * (1 + .009 * math.cos(3 * a))  # slightly soft, organic silhouette
            zz = z - (.0015 * (.5 + .5 * math.sin(3 * a + .5)) if j == 7 else 0.0)
            verts.append((rr * math.cos(a), rr * math.sin(a), zz))
    faces, mats = [tuple(reversed(range(n)))], [0]
    for j in range(len(PROFILE) - 1):
        for i in range(n):
            faces.append((j * n + i, j * n + (i + 1) % n, (j + 1) * n + (i + 1) % n, (j + 1) * n + i))
            mats.append(1 if j >= CARAMEL_FROM else 0)
    faces.append(tuple((len(PROFILE) - 1) * n + i for i in range(n)))
    mats.append(1)
    me = bpy.data.meshes.new("Pudding")
    me.from_pydata(verts, [], faces)
    me.materials.append(_material("Custard", (0.95, 0.64, 0.22), .3))
    me.materials.append(_material("Caramel", (.24, .055, .012), .24))
    for p, mi in zip(me.polygons, mats):
        p.material_index = mi
        p.use_smooth = len(p.vertices) == 4
    me.update()
    return me


def _link(ob):
    """Into Freebird's drawing collection when we know it, else the active collection."""
    try:
        from . import brush

        for fn in brush._patched.values():
            fn(ob)
            if ob.users_collection:
                return
    except Exception:
        pass
    (bpy.context.collection or bpy.context.scene.collection).objects.link(ob)


def new_pudding(level=2):
    from . import jiggle

    try:
        from bl_xr import xr_session

        from .grab import grab_center

        hand = Vector(grab_center())
        scale = float(xr_session.viewer_scale or 1.0)
    except Exception:
        hand, scale = bpy.context.scene.cursor.location.copy(), 1.0
    ob = bpy.data.objects.new("Pudding", _mesh())
    ob.scale = (scale, scale, scale)
    ob.location = hand - Vector((0, 0, 0.067 * scale))  # the hand in the middle of the pudding
    _link(ob)
    jiggle.make_jiggly(ob, level)
    jiggle.refresh()
    for o in bpy.context.view_layer.objects:
        if o is not None and o.select_get():
            o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    try:
        bpy.ops.ed.undo_push(message="VR new pudding")
    except Exception:
        pass
    return ob
