# SPDX-License-Identifier: GPL-2.0-or-later
"""Glowing outline on what the grab sphere touches (and on what you hold). LOCAL display only.

Inverted hull: each highlighted object is drawn once more, pushed out along its vertex normals
and with its front faces culled, in a flat colour, so only a rim around the silhouette shows.
Drawn from our own draw handler in the XR region (same place Freebird draws its VR UI). Meshes
are read in the update loop (never from the draw callback) and cached per object.
"""

import bpy

OUTLINE_COLOR = (1.0, 0.25, 0.25, 0.55)  # soft red, see-through: a hint, not a frame
WIDTH = 0.0008  # metres at viewer scale 1
MAX_VERTS = 300_000  # bigger meshes are not outlined (too slow to rebuild)
REBUILD_EVERY = 120  # frames: picks up edits (e.g. collab mesh sync) while highlighted

_handle = None
_targets = []  # names to outline this frame
_cache = {}  # name -> (key, batch)
_frame = 0
_shader = None


def set_targets(names):
    global _targets
    _targets = [n for n in names if n]


def _width_local(ob, viewer_scale):
    s = ob.matrix_world.to_scale()
    avg = (abs(s.x) + abs(s.y) + abs(s.z)) / 3.0 or 1.0
    return WIDTH * viewer_scale / avg


def smooth_normals(pos, tris):
    """Area-weighted normals shared by every vertex at the same position.
    Meshes with split corners (Freebird hulls, flat-shaded models) would otherwise push each
    face out on its own and the outline breaks into spikes."""
    import numpy as np

    p0, p1, p2 = pos[tris[:, 0]], pos[tris[:, 1]], pos[tris[:, 2]]
    fn = np.cross(p1 - p0, p2 - p0)  # length = 2 x area: bigger faces weigh more
    key = np.round(pos / 1e-5).astype(np.int64)
    _uniq, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    acc = np.zeros((inv.max() + 1, 3), dtype=np.float64)
    for k in range(3):
        np.add.at(acc, inv[tris[:, k]], fn)
    n = acc[inv]
    length = np.linalg.norm(n, axis=1, keepdims=True)
    return n / np.where(length > 1e-12, length, 1.0)


def _build(ob, w):
    import gpu
    import numpy as np
    from gpu_extras.batch import batch_for_shader

    global _shader
    if _shader is None:
        _shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    dg = bpy.context.evaluated_depsgraph_get()
    ob_eval = ob.evaluated_get(dg)
    me = ob_eval.to_mesh()
    try:
        n = len(me.vertices)
        if n == 0 or n > MAX_VERTS:
            return None
        me.calc_loop_triangles()
        co = np.empty(n * 3, dtype=np.float32)
        me.vertices.foreach_get("co", co)
        tri = np.empty(len(me.loop_triangles) * 3, dtype=np.int32)
        me.loop_triangles.foreach_get("vertices", tri)
        if len(tri) == 0:
            return None
        pos = co.reshape(-1, 3)
        tris = tri.reshape(-1, 3)
        pos = pos + smooth_normals(pos, tris) * w
        return batch_for_shader(_shader, "TRIS", {"pos": pos.astype(np.float32)}, indices=tris)
    finally:
        ob_eval.to_mesh_clear()


def update(viewer_scale):
    """Called every frame from the grab sphere's update: (re)build batches for the targets."""
    global _frame
    _frame += 1
    for name in list(_cache):
        if name not in _targets:
            del _cache[name]
    for name in _targets:
        ob = bpy.data.objects.get(name)
        if ob is None or ob.type not in ("MESH", "CURVE", "FONT", "SURFACE", "META"):
            _cache.pop(name, None)
            continue
        w = _width_local(ob, viewer_scale)
        key = (round(w, 6), ob.data.name if ob.data else "", _frame // REBUILD_EVERY)
        old = _cache.get(name)
        if old is not None and old[0] == key:
            continue
        try:
            _cache[name] = (key, _build(ob, w))
        except Exception as e:
            _cache[name] = (key, None)
            print(f"[vr_studio] outline {name}: {e}")


def _draw():
    if not _cache:
        return
    try:  # VIEW > Overlay OFF hides this too (it's an overlay)
        from .view import overlays_on

        if not overlays_on():
            return
    except Exception:
        pass
    try:
        import gpu

        gpu.state.depth_test_set("LESS_EQUAL")
        gpu.state.depth_mask_set(False)
        gpu.state.face_culling_set("FRONT")
        gpu.state.blend_set("ALPHA")
        _shader.bind()
        _shader.uniform_float("color", OUTLINE_COLOR)
        for name, (_key, batch) in _cache.items():
            ob = bpy.data.objects.get(name)
            if batch is None or ob is None:
                continue
            with gpu.matrix.push_pop():
                gpu.matrix.multiply_matrix(ob.matrix_world)
                batch.draw(_shader)
    except Exception as e:
        if _frame % 300 == 0:
            print(f"[vr_studio] outline draw: {e}")
    finally:
        try:
            gpu.state.face_culling_set("NONE")
            gpu.state.depth_mask_set(True)
            gpu.state.blend_set("NONE")
        except Exception:
            pass


def enable():
    global _handle
    if _handle is None:
        _handle = bpy.types.SpaceView3D.draw_handler_add(_draw, (), "XR", "POST_VIEW")


def disable():
    global _handle
    if _handle is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_handle, "XR")
        except Exception:
            pass
        _handle = None
    _cache.clear()
    _targets.clear()
