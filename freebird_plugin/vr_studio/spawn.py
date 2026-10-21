# SPDX-License-Identifier: GPL-2.0-or-later
"""New pudding: the Puddinger pudding (Puddinger/01_pudding/create_pudding.py), made right in
the hand. About 18 cm wide and 13 cm tall as you see it (follows the VR world scale), base at the
origin, already jiggly. Custard body + caramel top are two objects in one VR group (so the
caramel stays brown in Solid view's "Object" colour mode too); the group wobbles as one."""

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


def _mesh(name, first_ring, last_ring, bottom_cap, top_cap, material):
    """Rings first_ring..last_ring of the profile as one mesh (with optional caps)."""
    n = SEGMENTS
    verts = []
    rings = list(range(first_ring, last_ring + 1))
    for j in rings:
        r, z = PROFILE[j]
        for i in range(n):
            a = 2 * math.pi * i / n
            rr = r * (1 + .009 * math.cos(3 * a))  # slightly soft, organic silhouette
            zz = z - (.0015 * (.5 + .5 * math.sin(3 * a + .5)) if j == 7 else 0.0)
            verts.append((rr * math.cos(a), rr * math.sin(a), zz))
    faces = [tuple(reversed(range(n)))] if bottom_cap else []
    for k in range(len(rings) - 1):
        for i in range(n):
            faces.append((k * n + i, k * n + (i + 1) % n, (k + 1) * n + (i + 1) % n, (k + 1) * n + i))
    if top_cap:
        faces.append(tuple((len(rings) - 1) * n + i for i in range(n)))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.materials.append(material)
    for p in me.polygons:
        p.use_smooth = len(p.vertices) == 4
    me.update()
    return me


CUSTARD = (0.95, 0.64, 0.22)
CARAMEL = (.24, .055, .012)


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
    # two parts in a VR group: Solid view in "Object" colour mode shows one colour per object,
    # so the caramel needs its own object to stay brown there (the group wobbles as one pudding)
    custard = bpy.data.objects.new("Pudding", _mesh("Pudding", 0, CARAMEL_FROM, True, False,
                                                     _material("Custard", CUSTARD, .3)))
    caramel = bpy.data.objects.new("Pudding Caramel", _mesh("Pudding Caramel", CARAMEL_FROM, len(PROFILE) - 1,
                                                             False, True, _material("Caramel", CARAMEL, .24)))
    custard.color = (*CUSTARD, 1.0)
    caramel.color = (*CARAMEL, 1.0)
    base = hand - Vector((0, 0, 0.067 * scale))  # the hand in the middle of the pudding
    for ob in (custard, caramel):
        ob.scale = (scale, scale, scale)
        ob.location = base
        _link(ob)
        jiggle.make_jiggly(ob, level)
    bpy.context.view_layer.update()
    from .groups import make_group

    g = make_group([custard, caramel])  # selects the group
    jiggle.refresh()
    try:
        bpy.ops.ed.undo_push(message="VR new pudding")
    except Exception:
        pass
    return g or custard
